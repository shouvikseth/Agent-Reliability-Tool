"""Author-only held-out cases and mechanical validation; never generates model requests."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import subprocess
import tempfile
import uuid

from lab.tasks import Task, REGRESSION, seed, verifier


def case(number, category, issue, good, bad, check, logs):
    return Task(f'heldout-{number:02}', category, 'heldout', issue, good, bad, check,
                'Synthetic API contract incident: ' + logs + '\n')


HELDOUT_TASKS = [
    case(1, 'pagination', 'Pages must return issues in ascending creation ID order.',
         'ORDER BY id LIMIT', 'ORDER BY id DESC LIMIT',
         "assert [r['id'] for r in client.get('/issues?limit=2').json()] == [1,2]; assert [r['id'] for r in client.get('/issues?offset=1&limit=2').json()] == [2,3]",
         'GET /issues?limit=2 returned newest IDs first; the contract requires oldest IDs first.'),
    case(2, 'pagination', 'An explicit page limit must cap the number of returned issues.',
         '(state, state, limit, offset)', '(state, state, limit + 1, offset)',
         "assert [r['id'] for r in client.get('/issues?limit=1').json()] == [1]; assert [r['id'] for r in client.get('/issues?offset=1&limit=1').json()] == [2]",
         'GET /issues?limit=1 returned two issues. A page must contain at most the requested limit.'),
    case(3, 'pagination', 'Omitting limit must return up to ten issues, with correct subsequent offsets.',
         'limit: int = Query(10, ge=1, le=100)', 'limit: int = Query(1, ge=1, le=100)',
         "[client.post('/issues', json={'title':str(i)}) for i in range(9)]; assert [r['id'] for r in client.get('/issues').json()] == list(range(1,11)); assert [r['id'] for r in client.get('/issues?offset=10').json()] == [11,12]",
         'GET /issues without a limit returned one item from twelve. The default page size is ten.'),
    case(4, 'validation', 'Negative pagination offsets must be rejected without changing stored issues.',
         'offset: int = Query(0, ge=0)', 'offset: int = Query(0, ge=-1)',
         "assert client.get('/issues?offset=-1').status_code == 422; assert client.get('/issues?offset=0').status_code == 200; assert len(client.get('/issues').json()) == 3",
         'GET /issues?offset=-1 returned 200. The contract requires offset >= 0, otherwise 422.'),
    case(5, 'validation', 'The maximum permitted pagination limit is 100, inclusive.',
         'limit: int = Query(10, ge=1, le=100)', 'limit: int = Query(10, ge=1, le=101)',
         "assert client.get('/issues?limit=101').status_code == 422; assert client.get('/issues?limit=100').status_code == 200",
         'GET /issues?limit=101 was accepted. Limits 1 through 100 are valid; larger limits require 422.'),
    case(6, 'validation', 'Nonblank titles must be trimmed in both creation responses and stored records.',
         'title = body.title.strip()', 'title = body.title',
         "r=client.post('/issues', json={'title':'  padded  '}); assert r.status_code == 201; assert r.json()['title'] == 'padded'; assert client.get('/issues?offset=3').json()[0]['title'] == 'padded'",
         'Creating title "  padded  " preserved surrounding spaces. Responses and storage must use "padded".'),
    case(7, 'transitions', 'A successful close must persist the selected issue state for later reads.',
         "UPDATE issues SET state = 'closed' WHERE id = ?", 'UPDATE issues SET state = state WHERE id = ?',
         "assert client.post('/issues/2/close').status_code == 200; assert client.get('/issues?offset=1&limit=1').json()[0]['state'] == 'closed'",
         'POST /issues/2/close returned 200, but a subsequent GET still showed issue 2 as open.'),
    case(8, 'transitions', 'Closing one issue must leave every other issue open.',
         "UPDATE issues SET state = 'closed' WHERE id = ?", "UPDATE issues SET state = 'closed' WHERE id >= ?",
         "assert client.post('/issues/2/close').status_code == 200; assert [(r['id'],r['state']) for r in client.get('/issues').json()] == [(1,'open'),(2,'closed'),(3,'open')]",
         'Closing issue 2 also changed issue 3. Only the requested issue may change state.'),
    case(9, 'transitions', 'A close response must identify the requested issue and report its actual closed state.',
         'return {"id": issue_id, "state": "closed"}', 'return {"id": issue_id, "state": "open"}',
         "r=client.post('/issues/3/close'); assert r.status_code == 200; assert r.json() == {'id':3,'state':'closed'}; assert client.get('/issues?offset=2').json()[0]['state'] == 'closed'",
         'Closing issue 3 persisted closed state but returned state open. The response must agree with storage.'),
    case(10, 'duplicates', 'Request keys are case-sensitive opaque values; differently cased keys must remain independent.',
         'title = body.title.strip()', 'request_key = request_key.lower() if request_key is not None else None\n        title = body.title.strip()',
         "a=client.post('/issues?request_key=Case', json={'title':'upper'}); b=client.post('/issues?request_key=case', json={'title':'lower'}); assert a.status_code == b.status_code == 201; assert a.json()['id'] != b.json()['id']; assert len(client.get('/issues').json()) == 5",
         'Keys Case and case were conflated. Request keys are case-sensitive and must create separate issues.'),
    case(11, 'duplicates', 'An explicitly empty request key must retain idempotency; only an absent key disables it.',
         'if request_key is not None:\n                db.execute("INSERT INTO requests', 'if request_key:\n                db.execute("INSERT INTO requests',
         "a=client.post('/issues?request_key=', json={'title':'empty key'}); b=client.post('/issues?request_key=', json={'title':'empty key'}); assert a.status_code == b.status_code == 201; assert a.json() == b.json(); assert len(client.get('/issues').json()) == 4",
         'Replaying an explicitly empty key created another issue. Empty string is a valid key, distinct from no key.'),
    case(12, 'duplicates', 'Distinct request keys must not retrieve or conflict with each other records.',
         'SELECT title, issue_id FROM requests WHERE key = ?', 'SELECT title, issue_id FROM requests WHERE key = ? OR 1=1',
         "a=client.post('/issues?request_key=first', json={'title':'one'}); b=client.post('/issues?request_key=second', json={'title':'two'}); assert a.status_code == b.status_code == 201; assert a.json()['id'] != b.json()['id']; assert client.post('/issues?request_key=second', json={'title':'two'}).json() == b.json(); assert len(client.get('/issues').json()) == 5",
         'A new key second retrieved the record for key first. Each key must resolve only its own record.'),
]


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def task_fingerprints(task):
    source = (Path(__file__).resolve().parent.parent/'target_app/app.py').read_text()
    if source.count(task.good) != 1:
        raise ValueError('Nonunique seed anchor: ' + task.id)
    return {'definition_sha256': fingerprint(json.dumps(asdict(task), sort_keys=True).encode()),
            'seed_sha256': fingerprint(source.replace(task.good, task.bad).encode()),
            'reference_sha256': fingerprint(source.encode()),
            'verifier_sha256': fingerprint(verifier(task).encode()),
            'public_test_sha256': fingerprint(REGRESSION.encode())}


def schedule(seed_value=20261030):
    """Balanced design only. Attempt IDs identify slots, not completed executions."""
    rng = random.Random(seed_value)
    rows = []
    for index, task in enumerate(HELDOUT_TASKS):
        # Alternate 2:1 and 1:2 within categories: six of each fault overall.
        fault = 'timeout' if index % 6 in (0,1,3) else 'malformed'
        for repetition in range(1,4):
            for condition in ('clean', fault):
                architectures = ['fixed','single','team']
                rng.shuffle(architectures)
                for architecture in architectures:
                    identity = f'heldout-design-v1:{seed_value}:{task_fingerprints(task)["definition_sha256"]}:{repetition}:{condition}:{architecture}'
                    rows.append({'attempt_id': uuid.uuid5(uuid.NAMESPACE_URL, identity).hex,
                                 'task':task.id, 'repetition':repetition,
                                 'condition':condition, 'architecture':architecture})
    return rows


def configuration():
    from lab.ollama_provider import OllamaModel
    from lab.policies import EXECUTION_POLICY
    from lab.token_accounting import MODEL_DIGEST, TOKENIZER_SHA256, TOKENIZER_REVISION, TEMPLATE_SHA256
    provider = OllamaModel().metadata()
    provider.update(model_digest=MODEL_DIGEST, admission_policy='qwen-tokenizer-v1',
                    tokenizer={'tokenizer_sha256':TOKENIZER_SHA256, 'tokenizer_revision':TOKENIZER_REVISION,
                               'template_sha256':TEMPLATE_SHA256, 'safety_margin_tokens':64})
    provider.pop('fingerprint_verified')
    return {'provider_expected':provider, 'execution_policy':EXECUTION_POLICY,
            'budget':{'tool_calls':20,'seconds':600,'tokens':24000,'dollars':0.25},
            'seed':20261030, 'architectures':['fixed','single','team'],
            'model_preflight_required':True}


def validate(backend):
    from lab.cli import grade
    rows = []
    for task in HELDOUT_TASKS:
        with tempfile.TemporaryDirectory(prefix='lab-heldout-') as directory:
            workspace = Path(directory)
            seed(task, workspace)
            broken = grade(task, workspace/'app.py', backend)
            candidate = workspace/'app.py'
            candidate.write_text(candidate.read_text().replace(task.bad, task.good))
            reference = grade(task, candidate, backend)
        valid = (not broken['verifier']['passed'] and broken['verifier']['exit_code']==1
                 and broken['regression']['passed'] and all(r['passed'] for r in reference.values()))
        rows.append({'task':task.id, 'category':task.category, 'valid':valid,
                     **task_fingerprints(task), 'broken':broken, 'reference':reference})
        print(json.dumps({'task':task.id,'valid':valid}), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserve validation evidence')
    dirty = subprocess.run(['git','status','--porcelain'],capture_output=True,text=True,check=True).stdout
    if dirty.strip():
        parser.error('Commit the source and documentation before recording validation provenance')
    from lab.docker_backend import DockerBackend
    backend = DockerBackend()
    rows = validate(backend)
    commit = subprocess.run(['git','rev-parse','HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    result = {'status':'mechanically_validated_design' if all(r['valid'] for r in rows) else 'validation_failed',
              'execution_ready':False, 'model_evaluation_runs':0,
              'source_commit':commit, 'image':backend.image, 'tasks':rows,
              'configuration':configuration(),
              'fingerprint_encoding':'UTF-8 text normalized to LF',
              'category_counts':dict(Counter(t.category for t in HELDOUT_TASKS)),
              'schedule':schedule()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x',encoding='utf-8') as output:
        output.write(json.dumps(result,indent=2)+'\n')
    raise SystemExit(0 if all(r['valid'] for r in rows) else 1)


if __name__ == '__main__':
    main()
