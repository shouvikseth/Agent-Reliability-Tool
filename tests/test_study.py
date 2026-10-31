import copy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

from lab import study


@pytest.fixture
def frozen(tmp_path):
    design = json.loads((study.ROOT/'docs/studies/heldout-v1-validation.json').read_text())
    manifest = {'schema':'heldout-study-v1','design':design,'design_sha256':study.digest(design),
                'code_sha256':study.code_fingerprints(),'preflight':{'checked_at':'before','image':design['image']}}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    ledger = study.Ledger(tmp_path,manifest)
    yield tmp_path,manifest,ledger
    ledger.close()


def save_result(directory, manifest, slot, *, status='submitted', verified=False):
    run_id = 'a'*32
    result = {**{k:slot[k] for k in ('task','architecture','condition')},'id':run_id,
              'fixture':False,'backend':'docker','image':manifest['design']['image'],
              **{k:manifest['design']['configuration'][k] for k in ('budget','execution_policy')},
              'status':status,'verified_completion':verified, 'usage_complete':True,
              'verification':{'verifier':{'passed':verified,'exit_code':0 if verified else 1},
                              'regression':{'passed':True,'exit_code':0}} if status=='submitted' else None}
    path=Path(directory)/run_id/'result.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(result))
    return path,result


def test_starts_are_durable_and_final_failures_are_never_pending(frozen):
    directory, manifest, ledger=frozen
    slot=ledger.pending()[0]
    execution=ledger.begin(slot['attempt_id'])
    other=study.Ledger.open_existing(directory,manifest)
    try:
        assert other.summary()['active']==1
        assert other.summary()['pending']==215
    finally:
        other.close()
    path,_=save_result(directory/'executions'/execution,manifest,slot,status='agent_error')
    ledger.finish(execution,path)
    assert ledger.summary()['statuses']=={'agent_error':1}
    assert ledger.summary()['excluded']==0
    assert slot not in ledger.pending()
    with pytest.raises(sqlite3.IntegrityError):
        ledger.begin(slot['attempt_id'])
    with pytest.raises(sqlite3.IntegrityError):
        ledger.finish(execution,path)
    assert ledger.summary()['started']==1


def test_reconcile_recovers_final_artifact_and_preserves_incomplete_attempt(frozen):
    directory,manifest,ledger=frozen
    first,second=ledger.pending()[:2]
    a,b=ledger.begin(first['attempt_id']),ledger.begin(second['attempt_id'])
    save_result(directory/'executions'/a,manifest,first,verified=True)
    partial=directory/'executions'/b/'partial'
    partial.mkdir(parents=True)
    (partial/'execution.json').write_text('{"verified_completion":false}')
    ledger.reconcile()
    assert ledger.summary() == {'scheduled':216,'started':2,'pending':214,'active':0,
        'finished':1,'interrupted':1,'verified':1,'statuses':{'submitted':1},
        'incomplete_usage':1,'excluded':0,'denominator':216}
    events={kind:json.loads(payload) for kind,payload in ledger.db.execute("SELECT kind,payload FROM events WHERE kind!='started'")}
    assert events['finished']['recovered'] is True
    assert events['interrupted']['automatic_retry'] is False
    ledger.reconcile()
    assert ledger.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]==4
    assert (partial/'execution.json').is_file()


@pytest.mark.parametrize('change', ['identity','fixture','configuration','false_success','outside'])
def test_mismatched_artifacts_cannot_become_outcomes(frozen,change):
    directory,manifest,ledger=frozen
    slot=ledger.pending()[0]
    execution=ledger.begin(slot['attempt_id'])
    path,result=save_result(directory/'executions'/execution,manifest,slot)
    if change=='identity': result['task']='wrong'
    if change=='fixture': result['fixture']=True
    if change=='configuration': result['budget']={}
    if change=='false_success': result['verified_completion']=True
    path.write_text(json.dumps(result))
    if change=='outside':
        path,_=save_result(directory/'elsewhere',manifest,slot)
    with pytest.raises(ValueError): ledger.finish(execution,path)
    assert ledger.summary()['active']==1
    assert ledger.summary()['finished']==0


def test_ledger_is_append_only_and_rejects_other_manifest(frozen):
    directory,manifest,ledger=frozen
    execution=ledger.begin(ledger.pending()[0]['attempt_id'])
    for table in ('metadata','slots','attempts','events'):
        with pytest.raises(sqlite3.IntegrityError,match='append-only'):
            ledger.db.execute(f'DELETE FROM {table}')
        ledger.db.rollback()
    changed=copy.deepcopy(manifest)
    changed['source_commit']='different'
    with pytest.raises(ValueError,match='another frozen'):
        study.Ledger(directory,changed)
    assert ledger.summary()['started']==1


def test_runner_lock_prevents_concurrent_reconciliation_and_status_remains_readable(frozen):
    directory,manifest,ledger=frozen
    with study.runner_lock(directory):
        with pytest.raises(ValueError,match='already locked'):
            with study.runner_lock(directory): pass
        reader=study.Ledger.open_existing(directory,manifest)
        try: assert reader.summary()['pending']==216
        finally: reader.close()


def test_manifest_load_rejects_source_and_design_drift(frozen,monkeypatch):
    directory,manifest,_=frozen
    assert study.load(directory)==manifest
    monkeypatch.setattr(study,'code_fingerprints',lambda:{})
    with pytest.raises(ValueError,match='Runtime source'): study.load(directory)
    manifest['design']['schedule'][0]['task']='tampered'
    (directory/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='design digest'): study.load(directory)


@pytest.mark.parametrize('bad_digest',[False,True])
def test_provider_preflight_uses_only_local_metadata_and_rejects_mismatch(monkeypatch,bad_digest):
    class Counter:
        def __init__(self,path): pass
        def verify(self,digest,template):
            if (digest,template)!=('pinned','expected'): raise ValueError('fingerprint differs')
        def metadata(self): return {'tokenizer':'pinned'}
    monkeypatch.setattr('lab.token_accounting.QwenCounter',Counter)
    calls=[]
    def handler(request):
        assert request.url.host=='127.0.0.1'
        calls.append(request.url.path)
        payload={'/api/tags':{'models':[{'name':'qwen2.5-coder:7b','digest':'wrong' if bad_digest else 'pinned'}]},
                 '/api/show':{'template':'expected'},'/api/version':{'version':'test'}}
        assert request.url.path in payload
        return httpx.Response(200,json=payload[request.url.path])
    if bad_digest:
        with pytest.raises(ValueError,match='fingerprint'):
            study.provider_preflight('unused',transport=httpx.MockTransport(handler))
    else:
        assert study.provider_preflight('unused',transport=httpx.MockTransport(handler))['model_digest']=='pinned'
        assert calls==['/api/tags','/api/show','/api/version']


def test_run_resumes_pending_only_and_reconciles_crash_after_saved_result(frozen,monkeypatch):
    directory,manifest,ledger=frozen
    monkeypatch.setattr(study,'preflight',lambda *args:manifest['preflight'])
    monkeypatch.setattr('lab.docker_backend.DockerBackend',lambda image:SimpleNamespace(image=image))
    monkeypatch.setattr('lab.ollama_provider.OllamaModel',lambda **kwargs:object())
    monkeypatch.setattr(study,'configuration',lambda:manifest['design']['configuration'])
    calls=[]
    def smoke(output,architecture,condition,backend,*,model,task,budget):
        assert ledger.summary()['active']==1  # start is committed before work
        slot=next(row for row in manifest['design']['schedule'] if row['task']==task.id and row['architecture']==architecture and row['condition']==condition)
        _,result=save_result(output,manifest,slot,status='agent_error')
        calls.append(task.id)
        if len(calls)==1: raise KeyboardInterrupt()
        return result
    monkeypatch.setattr('lab.cli.smoke',smoke)
    with pytest.raises(KeyboardInterrupt): study.run(directory,'unused',1)
    assert ledger.summary()['active']==1
    summary=study.run(directory,'unused',1)
    assert len(calls)==2
    assert summary['started']==summary['finished']==2
    assert summary['pending']==214 and summary['active']==0
    assert summary['statuses']=={'agent_error':2}
    assert json.loads(ledger.db.execute("SELECT payload FROM events WHERE kind='finished' ORDER BY seq").fetchone()[0])['recovered']


def test_run_rejects_environment_drift_before_starting_attempt(frozen,monkeypatch):
    directory,manifest,ledger=frozen
    monkeypatch.setattr(study,'preflight',lambda *args:{**manifest['preflight'],'environment':'changed'})
    with pytest.raises(ValueError,match='environment differs'): study.run(directory,'unused',1)
    assert ledger.summary()['started']==0


def test_failed_or_changed_validation_artifact_cannot_prepare(frozen):
    _,manifest,_=frozen
    design=copy.deepcopy(manifest['design'])
    design['tasks'][0]['reference']['verifier']['passed']=False
    with pytest.raises(ValueError,match='mechanical checks'): study.check_design(design)
