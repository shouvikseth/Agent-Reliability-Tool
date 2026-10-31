"""Frozen local study preparation and append-only attempt accounting."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import tempfile
import uuid

import httpx

from lab.heldout import HELDOUT_TASKS, configuration, schedule, task_fingerprints


ROOT = Path(__file__).resolve().parent.parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def code_fingerprints():
    paths = sorted([*ROOT.glob('lab/*.py'), *ROOT.glob('target_app/*.py'),
                    *ROOT.glob('docker/*'), ROOT/'pyproject.toml'])
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
            for p in paths if p.is_file()}


def check_design(design):
    if design.get('status') != 'mechanically_validated_design':
        raise ValueError('Study requires a successful mechanical validation artifact')
    if design.get('configuration') != configuration() or design.get('schedule') != schedule():
        raise ValueError('Validated configuration or schedule differs from current design')
    rows = design.get('tasks', [])
    if [r['task'] for r in rows] != [t.id for t in HELDOUT_TASKS]:
        raise ValueError('Validated task catalog differs')
    for task, row in zip(HELDOUT_TASKS, rows):
        if not all(row.get(k) == v for k,v in task_fingerprints(task).items()):
            raise ValueError('Task fingerprint differs: ' + task.id)
        if not (row.get('valid') is True and row['broken']['verifier']['passed'] is False
                and row['broken']['verifier']['exit_code'] == 1 and row['broken']['regression']['passed'] is True
                and all(row['reference'][key]['passed'] is True for key in ('verifier','regression'))):
            raise ValueError('Invalid mechanical checks: ' + task.id)


def provider_preflight(tokenizer_file, *, transport=None):
    """Only loopback metadata endpoints; never /api/chat or paid services."""
    from lab.ollama_provider import OllamaModel
    model = OllamaModel(tokenizer_file=tokenizer_file)
    with httpx.Client(base_url='http://127.0.0.1:11434', trust_env=False,
                      transport=transport, timeout=15) as client:
        tags = client.get('/api/tags'); tags.raise_for_status()
        entries = [m for m in tags.json().get('models', []) if m.get('name') == model.model]
        if len(entries) != 1:
            raise ValueError('Expected exactly one installed model tag')
        shown = client.post('/api/show', json={'model':model.model}); shown.raise_for_status()
        model.counter.verify(entries[0].get('digest'), shown.json().get('template',''))
        version = client.get('/api/version'); version.raise_for_status()
        if not isinstance(version.json().get('version'), str) or not version.json()['version']:
            raise ValueError('Ollama version unavailable')
    return {'model_digest':entries[0]['digest'], 'tokenizer':model.counter.metadata(),
            'ollama_version':version.json()['version']}


def preflight(design, tokenizer_file):
    from lab.docker_backend import DockerBackend, docker
    from lab.tasks import REGRESSION
    check_design(design)
    provider = provider_preflight(tokenizer_file)
    backend = DockerBackend(design['image'])
    if backend.image != design['image']:
        raise ValueError('Docker image fingerprint differs')
    # Trusted reference only: a health check, never a held-out model attempt.
    with tempfile.TemporaryDirectory(prefix='lab-preflight-') as directory:
        workspace = Path(directory)
        (workspace/'app.py').write_text((ROOT/'target_app/app.py').read_text())
        (workspace/'test_public.py').write_text(REGRESSION)
        if backend.test(workspace, 30).get('exit_code') != 0:
            raise ValueError('Docker reference health check failed')
    return {'checked_at':now(), 'image':backend.image, **provider,
            'environment':{'python':platform.python_version(), 'platform':platform.platform(),
                           'docker_engine':docker('version','--format','{{.Server.Version}}'),
                           'packages':{name:importlib.metadata.version(name) for name in
                                       ('fastapi','starlette','anyio','httpx','pytest','tokenizers')}}}


@contextmanager
def runner_lock(directory):
    """Kernel-owned lock is released on process death; stale files are harmless."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'runner.lock').open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError('Study is already locked by another runner') from None
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError('Study is already locked by another runner') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Ledger:
    """Transactional starts and final events; one execution per scheduled slot."""
    def __init__(self, directory, manifest):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.manifest = manifest
        self.db = sqlite3.connect(self.directory/'attempts.sqlite3', timeout=5)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), manifest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS slots (id TEXT PRIMARY KEY, position INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, slot TEXT UNIQUE NOT NULL REFERENCES slots(id), started TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, execution TEXT NOT NULL REFERENCES attempts(id),
                kind TEXT NOT NULL CHECK(kind IN ('started','finished','interrupted')), at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_start ON events(execution) WHERE kind='started';
            CREATE UNIQUE INDEX IF NOT EXISTS one_final ON events(execution) WHERE kind IN ('finished','interrupted');
        ''')
        for table in ('metadata','slots','attempts','events'):
            for verb in ('UPDATE','DELETE'):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{verb} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only ledger'); END")
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                existing = self.db.execute('SELECT manifest FROM metadata WHERE id=1').fetchone()
                if existing is None:
                    self.db.execute('INSERT INTO metadata VALUES (1,?)',(canonical(manifest),))
                    for index, slot in enumerate(manifest['design']['schedule']):
                        self.db.execute('INSERT INTO slots VALUES (?,?,?)',(slot['attempt_id'],index,canonical(slot)))
                elif existing[0] != canonical(manifest):
                    raise ValueError('Ledger is bound to another frozen manifest')
        except BaseException:
            self.db.close()
            raise

    @classmethod
    def open_existing(cls, directory, manifest):
        ledger = cls.__new__(cls)
        ledger.directory, ledger.manifest = Path(directory), manifest
        uri = (ledger.directory/'attempts.sqlite3').resolve().as_uri() + '?mode=ro'
        ledger.db = sqlite3.connect(uri,uri=True)
        if ledger.db.execute('SELECT manifest FROM metadata WHERE id=1').fetchone() != (canonical(manifest),):
            ledger.close()
            raise ValueError('Ledger is bound to another frozen manifest')
        return ledger

    def close(self):
        self.db.close()

    def pending(self):
        return [json.loads(r[0]) for r in self.db.execute(
            'SELECT payload FROM slots WHERE id NOT IN (SELECT slot FROM attempts) ORDER BY position')]

    def begin(self, slot_id):
        execution = uuid.uuid4().hex
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('INSERT INTO attempts VALUES (?,?,?)',(execution,slot_id,now()))
            self.db.execute('INSERT INTO events(execution,kind,at,payload) VALUES (?,?,?,?)',
                            (execution,'started',now(),canonical({'configuration_sha256':digest(self.manifest)})))
        return execution

    def final(self, execution, kind, payload):
        if kind not in ('finished','interrupted'):
            raise ValueError('Invalid final event')
        with self.db:
            self.db.execute('INSERT INTO events(execution,kind,at,payload) VALUES (?,?,?,?)',
                            (execution,kind,now(),canonical(payload)))

    def finish(self, execution, result_path, *, recovered=False):
        path = Path(result_path).resolve()
        base = (self.directory/'executions'/execution).resolve()
        if (not base.is_relative_to(self.directory.resolve()) or not path.is_relative_to(base)
                or path.name != 'result.json' or not re.fullmatch('[a-f0-9]{32}',path.parent.name)):
            raise ValueError('Result must belong to the recorded execution directory')
        raw = path.read_bytes()
        result = json.loads(raw)
        record = self.db.execute('SELECT s.payload FROM slots s JOIN attempts a ON a.slot=s.id WHERE a.id=?',(execution,)).fetchone()
        if record is None:
            raise ValueError('Unknown execution')
        slot = json.loads(record[0])
        if any(result.get(k) != slot[k] for k in ('task','architecture','condition')) or result.get('id') != path.parent.name:
            raise ValueError('Result identity mismatch')
        if result.get('fixture') is not False or result.get('backend') != 'docker' or result.get('image') != self.manifest['design']['image']:
            raise ValueError('Result execution provenance differs')
        config = self.manifest['design']['configuration']
        if result.get('budget') != config['budget'] or result.get('execution_policy') != config['execution_policy']:
            raise ValueError('Result configuration differs')
        if result.get('status') not in ('submitted','agent_error','budget_exhausted','infrastructure_invalid'):
            raise ValueError('Unknown result status')
        verification = result.get('verification')
        verified = (result['status']=='submitted' and isinstance(verification,dict)
                    and set(verification)=={'verifier','regression'}
                    and all(v.get('passed') is True and v.get('exit_code')==0 for v in verification.values()))
        if result.get('verified_completion') is not verified:
            raise ValueError('Completion flag contradicts independent checks')
        self.final(execution,'finished',{'result':result, 'result_path':path.relative_to(self.directory.resolve()).as_posix(),
                                       'result_sha256':hashlib.sha256(raw).hexdigest(),'recovered':recovered})

    def reconcile(self):
        """Only call while holding runner_lock; no live process may be reconciled."""
        active = [r[0] for r in self.db.execute("SELECT id FROM attempts WHERE id NOT IN (SELECT execution FROM events WHERE kind IN ('finished','interrupted'))")]
        for execution in active:
            paths = list((self.directory/'executions'/execution).glob('*/result.json'))
            if len(paths)==1:
                self.finish(execution,paths[0],recovered=True)
            elif paths:
                raise ValueError('Multiple result artifacts for one execution; manual investigation required')
            else:
                artifacts = [{'path':p.relative_to(self.directory).as_posix(),
                              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                             for p in (self.directory/'executions'/execution).glob('*/execution.json')]
                self.final(execution,'interrupted',{'reason':'no_durable_final_result','usage_complete':False,
                                                   'verified_completion':False,'automatic_retry':False,
                                                   'partial_execution_artifacts':artifacts})

    def summary(self):
        counts = Counter()
        statuses = Counter()
        for kind, payload in self.db.execute("SELECT kind,payload FROM events WHERE kind!='started'"):
            data = json.loads(payload)
            counts[kind] += 1
            if kind=='finished':
                statuses[data['result']['status']] += 1
                counts['verified'] += data['result']['verified_completion']
                counts['incomplete_usage'] += data['result'].get('usage_complete') is not True
            else:
                counts['incomplete_usage'] += 1
        started = self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        scheduled = self.db.execute('SELECT COUNT(*) FROM slots').fetchone()[0]
        return {'scheduled':scheduled,'started':started,'pending':scheduled-started,
                'active':started-counts['finished']-counts['interrupted'],
                'finished':counts['finished'],'interrupted':counts['interrupted'],
                'verified':counts['verified'],'statuses':dict(statuses),
                'incomplete_usage':counts['incomplete_usage'],'excluded':0,
                'denominator':scheduled}


def prepare(design_path, directory, tokenizer_file):
    directory = Path(directory)
    if directory.exists():
        raise ValueError('Study directory already exists; never overwrite a frozen study')
    if subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip():
        raise ValueError('Commit changes before freezing the runnable study')
    design = json.loads(Path(design_path).read_text(encoding='utf-8'))
    observed = preflight(design,tokenizer_file)
    manifest = {'schema':'heldout-study-v1','prepared_at':now(),
                'source_commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
                'code_sha256':code_fingerprints(), 'design_sha256':digest(design),
                'design':design, 'preflight':observed, 'automatic_retries':False,
                'primary_analysis':'all_scheduled_slots_no_exclusions'}
    directory.mkdir(parents=True)
    with (directory/'manifest.json').open('x',encoding='utf-8') as output:
        output.write(json.dumps(manifest,indent=2)+'\n')
        output.flush(); os.fsync(output.fileno())
    ledger = Ledger(directory,manifest)
    try:
        return ledger.summary()
    finally:
        ledger.close()


def load(directory):
    manifest = json.loads((Path(directory)/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'heldout-study-v1' or digest(manifest['design']) != manifest['design_sha256']:
        raise ValueError('Manifest design digest differs')
    check_design(manifest['design'])
    if manifest['code_sha256'] != code_fingerprints():
        raise ValueError('Runtime source differs from the frozen study')
    return manifest


def run(directory, tokenizer_file, limit):
    from lab.cli import smoke
    from lab.docker_backend import DockerBackend
    from lab.ollama_provider import OllamaModel
    from lab.runtime import Budget
    if limit < 1:
        raise ValueError('Limit must be positive')
    if not (Path(directory)/'attempts.sqlite3').is_file():
        raise ValueError('Prepare a study before running it')
    with runner_lock(directory):
        manifest = load(directory)
        current = preflight(manifest['design'],tokenizer_file)
        if {k:v for k,v in current.items() if k!='checked_at'} != {k:v for k,v in manifest['preflight'].items() if k!='checked_at'}:
            raise ValueError('Live environment differs from preparation')
        ledger = Ledger(directory,manifest)
        try:
            ledger.reconcile()
            backend = DockerBackend(manifest['design']['image'])
            for slot in ledger.pending()[:limit]:
                execution = ledger.begin(slot['attempt_id'])
                output = Path(directory)/'executions'/execution
                # A crash leaves a durable start. Resume reconciles instead of rerunning it.
                result = smoke(output,slot['architecture'],slot['condition'],backend,
                               model=OllamaModel(tokenizer_file=tokenizer_file),
                               task=next(t for t in HELDOUT_TASKS if t.id==slot['task']),
                               budget=Budget(**manifest['design']['configuration']['budget']))
                ledger.finish(execution,output/result['id']/'result.json')
                print(json.dumps(ledger.summary()),flush=True)
            return ledger.summary()
        finally:
            ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','status','reconcile','run'])
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--design',type=Path,default=ROOT/'docs/studies/heldout-v1-validation.json')
    parser.add_argument('--tokenizer-file',type=Path)
    parser.add_argument('--limit',type=int,default=1,help='Maximum new attempts; failures are never retried')
    args = parser.parse_args()
    if args.command in ('prepare','run') and args.tokenizer_file is None:
        parser.error('--tokenizer-file is required')
    if args.command=='prepare':
        result = prepare(args.design,args.directory,args.tokenizer_file)
    elif args.command=='run':
        result = run(args.directory,args.tokenizer_file,args.limit)
    else:
        if not (args.directory/'attempts.sqlite3').is_file():
            parser.error('Study ledger does not exist')
        if args.command=='status':
            ledger = Ledger.open_existing(args.directory,load(args.directory))
            try:
                result = ledger.summary()
            finally:
                ledger.close()
        else:
            with runner_lock(args.directory):
                ledger = Ledger(args.directory,load(args.directory))
                try:
                    ledger.reconcile()
                    result = ledger.summary()
                finally:
                    ledger.close()
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
