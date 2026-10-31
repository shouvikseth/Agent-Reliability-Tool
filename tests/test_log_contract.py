import json
import pytest
from lab.log_contract import log_response, encode_log
from lab.runtime import Tools, Budget
from lab.tasks import TASKS, seed


@pytest.mark.parametrize('wire', ['{malformed-response', '[]', '{}',
    '{"schema":"logs-v2","ok":1,"content":"text"}',
    '{"schema":"logs-v2","ok":true,"content":17}'])
def test_invalid_wire_or_schema_returns_recoverable_error(wire):
    result=log_response(wire)
    assert result['ok'] is False
    assert result['error']['code']=='invalid_log_response'
    assert result['error']['retryable'] is True


def test_fault_once_then_successful_log_retry(tmp_path):
    task=TASKS[-1]
    seed(task,tmp_path/'workspace')
    tools=Tools(tmp_path/'workspace',tmp_path/'events.jsonl',Budget(),fault='malformed')
    assert not tools.call('logs')['ok']
    response=tools.call('logs')
    assert response==log_response(encode_log(task.logs))
    assert response['ok']
    assert tools.injected and tools.calls==2
    events=[json.loads(line) for line in tools.events.read_text().splitlines()]
    assert sum(event['kind']=='fault_injected' for event in events)==1


def test_log_fixtures_include_reproduction_but_not_reference_patch(tmp_path):
    for task in TASKS[-2:]:
        seed(task,tmp_path/task.id)
        text=(tmp_path/task.id/'logs.txt').read_text()
        assert 'API contract' in text
        assert task.good not in text and task.bad not in text
