from types import SimpleNamespace
import pytest
from lab.runtime import Tools, Budget, execute, acquire_fixed_context, ContextAcquisitionError
from lab.tasks import TASKS, seed


@pytest.fixture
def tools(tmp_path):
    seed(TASKS[-1],tmp_path/'workspace')
    return Tools(tmp_path/'workspace',tmp_path/'events.jsonl',Budget())


def test_clean_inspection_supplies_source_and_logs(tools):
    history=[]
    acquire_fixed_context(tools,history)
    assert tools.calls==2
    assert history[0]['tool']=='read' and 'create_app' in history[0]['result']
    assert history[1]['result']['ok'] is True


def test_retryable_log_fault_retries_once_with_shared_budget(tools):
    tools.fault='malformed';history=[]
    acquire_fixed_context(tools,history)
    assert tools.calls==3
    assert [entry['result']['ok'] for entry in history[1:]]==[False,True]


def test_permanent_boundary_error_stops_after_two_attempts(tools,monkeypatch):
    monkeypatch.setattr('lab.runtime.log_response',lambda wire:{'schema':'logs-v2','ok':False,'error':{'code':'invalid_log_response','retryable':True}})
    with pytest.raises(ContextAcquisitionError):
        acquire_fixed_context(tools,[])
    assert tools.calls==3


def test_inspection_budget_exhaustion_prevents_model_request(tools):
    tools.budget.tool_calls=1
    class NoModel:
        def respond(self,*args,**kwargs): raise AssertionError('No request expected')
    assert execute('fixed',NoModel(),'issue',tools)['status']=='budget_exhausted'
    assert tools.calls==1


def test_fixed_flow_has_only_patch_and_revision_model_stages(tools):
    tools.fault='malformed'
    tools.backend=SimpleNamespace(test=lambda *args:{'exit_code':0,'output':'passed'})
    stages=[]
    class Model:
        def respond(self,role,issue,history,*,allowed):
            stages.append(role)
            if role=='patch':
                assert any(entry.get('tool')=='read' for entry in history)
                assert any(entry.get('tool')=='logs' and entry['result'].get('ok') is True for entry in history)
            return {'text':'no edits','actions':[],'usage':{'tokens':1,'dollars':0}}
    result=execute('fixed',Model(),'issue',tools)
    assert result['status']=='submitted'
    assert stages==['patch','revision'] and result['tokens']==2
    assert tools.calls==5  # source, faulty logs, retry, public test, submit
