import copy
import json
from types import SimpleNamespace
import pytest
from lab.policies import visible_history, MAX_ACTIONS
from lab.runtime import Budget, Tools, execute
from lab.tasks import TASKS, seed
from lab.openai_provider import decode_actions, ModelOutputError


@pytest.fixture
def tools(tmp_path):
    seed(TASKS[0], tmp_path / 'workspace')
    return Tools(tmp_path / 'workspace', tmp_path / 'events.jsonl', Budget())


def test_passed_tests_cached_only_for_identical_source(tools):
    calls = []
    tools.backend = SimpleNamespace(test=lambda *args: calls.append('executed') or {'exit_code': 0, 'output': 'passed'})
    tools.call('test')
    assert tools.call('test')['cached']
    path = tools.workspace / 'app.py'
    path.write_text(path.read_text() + '\n# changed\n')
    assert 'cached' not in tools.call('test')
    assert len(calls) == 2
    assert tools.calls == 3


def test_faulted_or_failed_tests_are_not_cached(tools):
    calls = []
    tools.fault = 'timeout'
    tools.backend = SimpleNamespace(test=lambda *args: calls.append('executed') or {'exit_code': 1, 'output': 'failed'})
    assert tools.call('test')['error'] == 'timeout_before_execution'
    tools.call('test')
    tools.call('test')
    assert len(calls) == 2
    assert tools.cached_tests == 0


def test_two_empty_agent_turns_stop_without_implicit_submission(tools):
    class Empty:
        def respond(self, role, issue, history, *, allowed):
            return {'text': 'done', 'actions': [], 'usage': {'tokens': 3, 'dollars': 0}}
    result = execute('single', Empty(), 'issue', tools)
    assert result['status'] == 'agent_error'
    assert result['tokens'] == 6
    assert not tools.submitted
    events = [json.loads(line) for line in tools.events.read_text().splitlines()]
    assert any(event['kind'] == 'runtime_feedback' for event in events)


def test_duplicate_read_compaction_preserves_original_and_latest_source():
    source = 'important candidate source\n' * 100
    history = [{'tool': 'read', 'arguments': {'path': 'app.py'}, 'result': source},
               {'tool': 'test', 'result': {'exit_code': 1, 'output': 'x'*3000 + 'failure'}},
               {'tool': 'read', 'arguments': {'path': 'app.py'}, 'result': source}]
    original = copy.deepcopy(history)
    compacted = visible_history(history)
    assert history == original
    assert 'duplicate_content_sha256' in compacted[0]['result']
    assert compacted[-1]['result'] == source
    assert compacted[1]['result']['exit_code'] == 1
    assert compacted[1]['result']['output'].endswith('failure')


def test_seven_action_batch_is_rejected_before_any_execution(tools):
    class Batch:
        def respond(self, role, issue, history, *, allowed):
            return {'text': '', 'actions': [{'name': 'test'}]*(MAX_ACTIONS+1), 'usage': {'tokens': 1, 'dollars': 0}}
    assert execute('single', Batch(), 'issue', tools)['status'] == 'agent_error'
    assert tools.calls == 0
    with pytest.raises(ModelOutputError):
        decode_actions(json.dumps({'text': '', 'actions': [{}]*(MAX_ACTIONS+1)}), {'test'})
