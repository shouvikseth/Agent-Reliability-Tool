"""Read-only accounting of a frozen study; separate from evaluation runtime."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import statistics


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metrics(trials):
    results=[t['result'] for t in trials if t['outcome']=='finished']
    verified=[r for r in results if r['verified_completion']]
    graded=[r for r in results if r.get('verification') is not None]
    durations=[r['seconds'] for r in results]
    complete=len(results)==len(trials) and all(r.get('usage_complete') is True for r in results)
    known_dollars=sum(r.get('known_dollars',r.get('dollars') or 0) for r in results)
    regression_failures=sum(r['verification']['regression']['passed'] is False for r in graded)
    return {'scheduled':len(trials),'finished':len(results),
            'interrupted':sum(t['outcome']=='interrupted' for t in trials),
            'verified':len(verified),'completion_percent':100*len(verified)/len(trials) if trials else None,
            'statuses':dict(Counter(r['status'] for r in results)),
            'independently_graded':len(graded),
            'regression_failures':regression_failures,
            'regression_percent_of_graded':100*regression_failures/len(graded) if graded else None,
            'budget_exhausted':sum(r['status']=='budget_exhausted' for r in results),
            'infrastructure_invalid':sum(r['status']=='infrastructure_invalid' for r in results),
            'faults_assigned':sum(t['condition']!='clean' for t in trials),
            'faults_triggered':sum(bool(r.get('fault_triggered')) for r in results),
            'fault_exposure_unknown':sum(t['outcome']=='interrupted' and t['condition']!='clean' for t in trials),
            'reported_tokens':sum(r['tokens'] for r in results),
            'uncertain_reserved_tokens':sum(r.get('uncertain_reserved_tokens',0) for r in results),
            'model_requests':sum(r.get('model_requests',0) for r in results),
            'usage_complete':complete,
            'usage_incomplete_outcomes':sum(r.get('usage_complete') is not True for r in results)+sum(t['outcome']=='interrupted' for t in trials),
            'known_api_dollars':known_dollars,
            'api_cost_per_verified_success':known_dollars/len(verified) if verified and complete else None,
            'timed_outcomes':len(durations),
            'median_seconds_all_recorded':statistics.median(durations) if durations else None,
            'min_seconds':min(durations) if durations else None,
            'max_seconds':max(durations) if durations else None,
            'median_seconds_successful':statistics.median(r['seconds'] for r in verified) if verified else None,
            'excluded':0}


def summarize(trials):
    architectures={}
    for architecture in sorted({t['architecture'] for t in trials}):
        rows=[t for t in trials if t['architecture']==architecture]
        architectures[architecture]={'all':metrics(rows),
            'clean':metrics([t for t in rows if t['condition']=='clean']),
            'assigned_fault':metrics([t for t in rows if t['condition']!='clean']),
            'by_condition':{condition:metrics([t for t in rows if t['condition']==condition])
                            for condition in sorted({t['condition'] for t in rows})}}
    tasks={}
    for task in sorted({t['task'] for t in trials}):
        tasks[task]={}
        for architecture in architectures:
            rows=[t for t in trials if t['task']==task and t['architecture']==architecture]
            tasks[task][architecture]={condition:{
                'scheduled':sum(t['condition']==condition for t in rows),
                'verified':sum(t['outcome']=='finished' and t['result']['verified_completion']
                               for t in rows if t['condition']==condition)}
                for condition in sorted({t['condition'] for t in rows})}
    return {'all':metrics(trials),'architectures':architectures,'task_consistency':tasks}


def report(directory):
    directory=Path(directory).resolve()
    manifest_bytes=(directory/'manifest.json').read_bytes()
    manifest=json.loads(manifest_bytes)
    if manifest.get('schema')!='heldout-study-v1':
        raise ValueError('Unsupported study manifest')
    if sha(canonical(manifest['design']).encode())!=manifest['design_sha256']:
        raise ValueError('Frozen design digest mismatch')
    with sqlite3.connect((directory/'attempts.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        if db.execute('SELECT manifest FROM metadata WHERE id=1').fetchone()!=(canonical(manifest),):
            raise ValueError('Manifest differs from the ledger')
        slots=[json.loads(r[0]) for r in db.execute('SELECT payload FROM slots ORDER BY position')]
        attempts=db.execute('SELECT id,slot,started FROM attempts').fetchall()
        events=db.execute('SELECT execution,kind,payload FROM events ORDER BY seq').fetchall()
    if slots!=manifest['design']['schedule'] or len({s['attempt_id'] for s in slots})!=len(slots):
        raise ValueError('Schedule differs from frozen design')
    executions={slot:(execution,started) for execution,slot,started in attempts}
    if len(executions)!=len(attempts) or set(executions)!={s['attempt_id'] for s in slots}:
        raise ValueError('Study has unstarted, duplicated, or unexpected slots')
    starts=Counter()
    finals={}
    for execution,kind,payload in events:
        if execution not in {a[0] for a in attempts}:
            raise ValueError('Event belongs to an unknown execution')
        if kind=='started':
            starts[execution]+=1
            if json.loads(payload).get('configuration_sha256')!=sha(canonical(manifest).encode()):
                raise ValueError('Attempt configuration digest differs')
        elif kind in ('finished','interrupted'):
            if execution in finals:
                raise ValueError('Multiple terminal events for an execution')
            finals[execution]=(kind,json.loads(payload))
        else:
            raise ValueError('Unknown ledger event')
    if any(starts[a[0]]!=1 or a[0] not in finals for a in attempts):
        raise ValueError('Study contains unfinished or invalid attempt records')
    trials=[]
    for slot in slots:
        execution,started=executions[slot['attempt_id']]
        kind,payload=finals[execution]
        trial={**slot,'execution_id':execution,'started_at':started,'outcome':kind}
        if kind=='finished':
            path=(directory/payload['result_path']).resolve()
            base=directory/'executions'/execution
            if (not re.fullmatch('[a-f0-9]{32}',execution) or not path.is_relative_to(base)
                    or path.name!='result.json' or not re.fullmatch('[a-f0-9]{32}',path.parent.name)):
                raise ValueError('Invalid result artifact path')
            raw=path.read_bytes()
            result=json.loads(raw)
            if sha(raw)!=payload['result_sha256'] or result!=payload['result']:
                raise ValueError('Result artifact differs from durable outcome')
            if result['id']!=path.parent.name or any(result[k]!=slot[k] for k in ('task','architecture','condition')):
                raise ValueError('Result identity mismatch')
            verification=result.get('verification')
            passed=(result['status']=='submitted' and isinstance(verification,dict)
                    and set(verification)=={'verifier','regression'}
                    and all(v.get('passed') is True and v.get('exit_code')==0 for v in verification.values()))
            if result['verified_completion'] is not passed:
                raise ValueError('Completion flag contradicts independent checks')
            trial.update(result=result,result_sha256=payload['result_sha256'],
                         result_path=payload['result_path'],recovered=payload['recovered'])
        else:
            if payload.get('verified_completion') is not False or payload.get('usage_complete') is not False:
                raise ValueError('Interrupted attempt claims completion or complete usage')
            trial['interruption']=payload
        trials.append(trial)
    return {'scope':'heldout_evaluation','schema':'heldout-report-v1',
            'exported_at':datetime.now(timezone.utc).isoformat(),
            'analysis_source_sha256':sha(Path(__file__).read_text(encoding='utf-8').encode()),
            'frozen_manifest_sha256':sha(manifest_bytes),'manifest':manifest,
            'summary':summarize(trials),'trials':trials}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve prior exports')
    result=report(args.directory)
    with args.output.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['summary']['all'],indent=2))


if __name__=='__main__':
    main()
