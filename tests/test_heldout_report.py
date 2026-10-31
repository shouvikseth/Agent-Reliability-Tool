import copy
import hashlib
import json
import sqlite3

import pytest

from analysis.heldout_report import canonical, report, sha, summarize


@pytest.fixture
def evidence(tmp_path):
    slots=[{'attempt_id':str(i),'task':'heldout-01','architecture':'fixed',
            'repetition':1,'condition':'clean' if i==0 else 'timeout'} for i in range(2)]
    design={'schedule':slots}
    manifest={'schema':'heldout-study-v1','design':design,'design_sha256':sha(canonical(design).encode())}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    db=sqlite3.connect(tmp_path/'attempts.sqlite3')
    db.executescript('''CREATE TABLE metadata(id,manifest); CREATE TABLE slots(position,payload);
        CREATE TABLE attempts(id,slot,started); CREATE TABLE events(seq,execution,kind,payload);''')
    db.execute('INSERT INTO metadata VALUES (1,?)',(canonical(manifest),))
    paths=[]
    for index,slot in enumerate(slots):
        execution=f'{index:032x}'
        run_id=f'{index+2:032x}'
        result={**slot,'id':run_id,'status':'submitted','verified_completion':index==0,
                'verification':{'verifier':{'passed':index==0,'exit_code':index},
                                'regression':{'passed':True,'exit_code':0}},
                'seconds':index+1,'tokens':10,'model_requests':2,'usage_complete':True,
                'dollars':0,'fault_triggered':index==1}
        path=tmp_path/'executions'/execution/run_id/'result.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(result))
        paths.append(path)
        db.execute('INSERT INTO slots VALUES (?,?)',(index,json.dumps(slot)))
        db.execute('INSERT INTO attempts VALUES (?,?,?)',(execution,slot['attempt_id'],'time'))
        db.execute('INSERT INTO events VALUES (?,?,?,?)',(index*2,execution,'started',json.dumps({'configuration_sha256':sha(canonical(manifest).encode())})))
        db.execute('INSERT INTO events VALUES (?,?,?,?)',(index*2+1,execution,'finished',json.dumps({
            'result':result,'result_path':path.relative_to(tmp_path).as_posix(),
            'result_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'recovered':False})))
    db.commit()
    yield tmp_path,db,paths
    db.close()


def test_complete_report_counts_failures_and_fault_exposure(evidence):
    directory,db,_=evidence
    before=db.execute('SELECT COUNT(*) FROM events').fetchone()
    result=report(directory)
    all_results=result['summary']['all']
    assert all_results['scheduled']==2 and all_results['verified']==1
    assert all_results['completion_percent']==50 and all_results['excluded']==0
    assert all_results['faults_assigned']==all_results['faults_triggered']==1
    assert all_results['reported_tokens']==20 and all_results['usage_complete']
    assert result['summary']['architectures']['fixed']['clean']['verified']==1
    assert result['summary']['architectures']['fixed']['assigned_fault']['verified']==0
    assert db.execute('SELECT COUNT(*) FROM events').fetchone()==before


@pytest.mark.parametrize('damage',['pending','active','duplicate','modified_result','changed_manifest','wrong_configuration'])
def test_report_refuses_incomplete_or_conflicting_evidence(evidence,damage):
    directory,db,paths=evidence
    if damage=='pending': db.execute("DELETE FROM attempts WHERE slot='1'")
    if damage=='active': db.execute("DELETE FROM events WHERE seq=3")
    if damage=='duplicate': db.execute('INSERT INTO events SELECT seq+10,execution,kind,payload FROM events WHERE seq=3')
    if damage=='modified_result': paths[0].write_text('{}')
    if damage=='changed_manifest':
        manifest=json.loads((directory/'manifest.json').read_text())
        manifest['design']['schedule'][0]['task']='tampered'
        (directory/'manifest.json').write_text(json.dumps(manifest))
    if damage=='wrong_configuration':
        db.execute("UPDATE events SET payload='{}' WHERE kind='started'")
    db.commit()
    with pytest.raises(ValueError): report(directory)


def test_interrupted_slot_is_kept_in_denominator_with_unknown_usage(evidence):
    directory,db,_=evidence
    payload={'verified_completion':False,'usage_complete':False,'automatic_retry':False}
    db.execute("UPDATE events SET kind='interrupted',payload=? WHERE seq=3",(json.dumps(payload),))
    db.commit()
    result=report(directory)
    assert result['summary']['all']['scheduled']==2
    assert result['summary']['all']['interrupted']==1
    assert result['summary']['all']['verified']==1
    assert not result['summary']['all']['usage_complete']
    assert result['summary']['all']['api_cost_per_verified_success'] is None


def test_summaries_separate_architectures_conditions_and_regressions(evidence):
    directory,_,_=evidence
    trials=report(directory)['trials']
    other=copy.deepcopy(trials[1])
    other['architecture']='team'
    other['result']['verification']['regression']['passed']=False
    stats=summarize(trials+[other])
    assert stats['architectures']['team']['all']['regression_failures']==1
    assert stats['architectures']['fixed']['all']['regression_failures']==0
    assert stats['task_consistency']['heldout-01']['team']['timeout']=={'scheduled':1,'verified':0}
