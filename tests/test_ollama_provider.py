import json
import httpx
import pytest
from lab.ollama_provider import OllamaModel
from lab.runtime import Budget, Tools, execute
from lab.tasks import TASKS, seed


@pytest.fixture
def tools(tmp_path):
    seed(TASKS[0], tmp_path / 'workspace')
    return Tools(tmp_path / 'workspace', tmp_path / 'events.jsonl', Budget(tokens=24000))


def transport_for(action='submit', seen=None, usage=True):
    def handler(request):
        if seen is not None:
            seen.append(request)
        assert request.url.host == '127.0.0.1'
        assert 'authorization' not in request.headers
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'qwen2.5-coder:7b', 'digest': 'sha256:fixture'}]})
        payload = json.loads(request.content)
        assert payload['stream'] is False
        assert payload['options']['num_ctx'] == 8192
        result = {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps({
            'text': 'Done', 'actions': [{'name': action, 'arguments': {'path': None, 'old': None, 'new': None}}]})}}
        if usage:
            result.update(prompt_eval_count=100, eval_count=20)
        return httpx.Response(200, json=result)
    return httpx.MockTransport(handler)


def test_local_run_needs_no_key_and_reports_no_api_fee(tools, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    seen = []
    model = OllamaModel(transport=transport_for(seen=seen))
    result = execute('single', model, TASKS[0].issue, tools)
    assert result['status'] == 'submitted'
    assert result['tokens'] == 120
    assert result['dollars'] == 0
    assert result['usage_complete']
    assert model.metadata()['model_digest'] == 'sha256:fixture'
    assert len(seen) == 2


def test_local_preflight_stops_before_network(tools):
    tools.budget.tokens = 1
    seen = []
    result = execute('single', OllamaModel(transport=transport_for(seen=seen)), 'issue', tools)
    assert result['status'] == 'budget_exhausted'
    assert seen == []


def test_local_missing_model_reports_pull_command(tools):
    model = OllamaModel(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'models': []})))
    result = execute('single', model, 'issue', tools)
    assert result['status'] == 'infrastructure_invalid'
    assert 'ollama pull qwen2.5-coder:7b' in result['error']
    assert result['model_requests'] == 0


def test_local_missing_usage_retains_reservation(tools):
    result = execute('single', OllamaModel(transport=transport_for(usage=False)), 'issue', tools)
    assert result['status'] == 'infrastructure_invalid'
    assert not result['usage_complete']
    assert result['uncertain_reserved_tokens'] > 0


def test_cloud_models_rejected():
    with pytest.raises(ValueError):
        OllamaModel('some-model:cloud')


def test_schema_prevents_edit_arguments_on_test():
    from lab.openai_provider import action_tool, decode_actions, ModelOutputError
    variants = action_tool({'test', 'replace'})['parameters']['properties']['actions']['items']['anyOf']
    test_schema = next(item for item in variants if item['properties']['name']['enum'] == ['test'])
    assert all(field == {'type': 'null'} for field in test_schema['properties']['arguments']['properties'].values())
    with pytest.raises(ModelOutputError):
        decode_actions(json.dumps({'text': 'test', 'actions': [{'name': 'test', 'arguments': {
            'path': 'app.py', 'old': 'before', 'new': 'after'}}]}), {'test'})


def test_local_transport_failure_is_actionable(tools):
    def fail(request):
        raise httpx.ConnectError('connection refused')
    result = execute('single', OllamaModel(transport=httpx.MockTransport(fail)), 'issue', tools)
    assert result['status'] == 'infrastructure_invalid'
    assert 'Install and start Ollama' in result['error']


def test_provider_sends_only_current_stage_completion_rules(tools):
    seen = []
    base = transport_for(seen=seen)
    def handler(request):
        response = base.handle_request(request)
        if request.url.path == '/api/chat':
            payload = json.loads(request.content)
            if 'Stage: revision' in payload['messages'][0]['content']:
                data = json.loads(response.content)
                data['message']['content'] = '{"text":"No further changes needed.","actions":[]}'
                return httpx.Response(200, json=data)
        return response
    model = OllamaModel(transport=httpx.MockTransport(handler))
    model.bind(tools)
    assert model.respond('agent', 'issue', [], allowed={'submit'})['actions'][0]['name'] == 'submit'
    assert model.respond('revision', 'issue', [], allowed={'test'})['actions'] == []
    prompts = [json.loads(request.content)['messages'][0]['content'] for request in seen if request.url.path == '/api/chat']
    assert 'No further changes needed' not in prompts[0]
    assert 'An empty action list does not finish' in prompts[0]
    assert 'No further changes needed' in prompts[1]
    assert 'Ready to grade' not in prompts[1]


def test_grammar_size_does_not_consume_local_prompt_reservation(tools):
    model = OllamaModel(transport=transport_for())
    model.bind(tools)
    model.respond('agent', 'issue', [], allowed={'list','read','logs','replace','test','submit'})
    events = [json.loads(line) for line in tools.events.read_text().splitlines()]
    accounting = next(event for event in events if event['kind'] == 'context_accounting')
    measurement = next(event for event in events if event['kind'] == 'context_measurement')
    assert accounting['input_token_bound'] < 3000
    assert measurement['actual_input_tokens'] == 100
    assert accounting['output_limit'] == model.max_output_tokens


def test_local_http_diagnostic_is_bounded_and_retains_usage_uncertainty(tools):
    base = transport_for()
    def handler(request):
        if request.url.path == '/api/chat':
            return httpx.Response(500, json={'error': 'runner crashed; private text must not be logged'})
        return base.handle_request(request)
    result = execute('single', OllamaModel(transport=httpx.MockTransport(handler)), 'issue', tools)
    assert result['status'] == 'infrastructure_invalid'
    assert 'HTTP 500 (runner)' in result['error']
    assert not result['usage_complete']
    assert 'private text' not in tools.events.read_text()
