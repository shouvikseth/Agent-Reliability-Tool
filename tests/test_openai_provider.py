import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from lab.openai_provider import OpenAIModel, ProviderError, ModelOutputError, decode_actions
from lab.runtime import Budget, BudgetExceeded, Tools, execute
from lab.tasks import TASKS, seed


def action(name, **arguments):
    return {'name': name, 'arguments': {key: arguments.get(key) for key in ('path', 'old', 'new')}}


def response(actions=(), status='completed', raw=None):
    return NS(id='resp_fixture', model='pinned-fixture', status=status,
              usage=NS(input_tokens=100, output_tokens=20, input_tokens_details=NS(cached_tokens=40)),
              output=[NS(type='function_call', name='respond', arguments=raw or json.dumps({'text': 'Visible status', 'actions': list(actions)}))])


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.count_calls, self.create_calls = [], []
        self.delay = 0
        self.responses = NS(input_tokens=NS(count=self.count), create=self.create)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def count(self, **kwargs):
        self.count_calls.append(kwargs)
        return NS(input_tokens=100)

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        await asyncio.sleep(self.delay)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def tools(tmp_path):
    seed(TASKS[0], tmp_path / 'workspace')
    return Tools(tmp_path / 'workspace', tmp_path / 'events.jsonl', Budget())


def model_with(client, tools):
    model = OpenAIModel(client_factory=lambda: client)
    model.bind(tools)
    return model


def test_request_contract_and_cached_cost(tools):
    client = FakeClient([response([action('read', path='app.py')])])
    model = model_with(client, tools)
    result = model.respond('agent', 'issue', [], allowed={'read'})
    assert result['actions'] == [{'name': 'read', 'arguments': {'path': 'app.py'}}]
    request = client.create_calls[0]
    assert request['store'] is False
    assert request['service_tier'] == 'default'
    assert request['max_output_tokens'] == 2048
    assert request['parallel_tool_calls'] is False
    assert 'store' not in client.count_calls[0]
    for key, value in client.count_calls[0].items():
        if key != 'timeout':
            assert request[key] == value
    assert result['usage']['dollars'] == pytest.approx((60*.75 + 40*.075 + 20*4.5)/1000000)
    assert model.snapshot()['usage_complete']
    assert model.snapshot()['tokens'] == 120


@pytest.mark.parametrize('budget', [Budget(tokens=100), Budget(dollars=.00001)])
def test_preflight_blocks_generation(tools, budget):
    tools.budget = budget
    client = FakeClient([])
    model = model_with(client, tools)
    with pytest.raises(BudgetExceeded):
        model.respond('agent', 'issue', [], allowed={'submit'})
    assert client.create_calls == []


def test_output_limit_shrinks_to_remaining_tokens(tools):
    tools.budget = Budget(tokens=150)
    client = FakeClient([response([action('submit')])])
    model = model_with(client, tools)
    model.respond('agent', 'issue', [], allowed={'submit'})
    assert client.create_calls[0]['max_output_tokens'] == 50
    with pytest.raises(BudgetExceeded):
        model.respond('agent', 'issue', [], allowed={'submit'})
    assert len(client.create_calls) == 1


def test_incomplete_usage_is_kept(tools):
    client = FakeClient([response(status='incomplete')])
    model = model_with(client, tools)
    result = execute('single', model, 'issue', tools)
    assert result['status'] == 'agent_error'
    assert result['tokens'] == 120
    assert result['dollars'] > 0
    assert not tools.submitted


def test_failure_retains_reservation_without_logging_secret(tools):
    client = FakeClient([RuntimeError('sk-secret-must-not-be-logged')])
    model = model_with(client, tools)
    result = execute('single', model, 'issue', tools)
    assert result['status'] == 'infrastructure_invalid'
    assert result['dollars'] is None
    assert not result['usage_complete']
    assert result['uncertain_reserved_tokens'] == 2148
    assert 'sk-secret' not in tools.events.read_text()
    assert len(client.create_calls) == 1


@pytest.mark.parametrize('code', ['insufficient_quota', 'rate_limit_exceeded', 'credit_balance_exhausted'])
def test_limit_diagnostics_preserve_only_known_codes(tools, code):
    error = RuntimeError('sk-secret raw server response')
    error.status_code = 429
    error.body = {'error': {'code': code, 'message': 'sk-secret'}}
    model = model_with(FakeClient([error]), tools)
    result = execute('single', model, 'issue', tools)
    assert 'code=' + code in result['error']
    assert 'sk-secret' not in tools.events.read_text()


def test_arbitrary_provider_code_is_not_logged(tools):
    error = RuntimeError('sk-secret')
    error.status_code = 429
    error.code = 'sk-secret'
    result = execute('single', model_with(FakeClient([error]), tools), 'issue', tools)
    assert 'unrecognized limit code' in result['error']
    assert 'sk-secret' not in tools.events.read_text()


def test_deadline_cancels_request_and_keeps_reservation(tools):
    tools.budget.seconds = .1
    client = FakeClient([response()])
    client.delay = 1
    model = model_with(client, tools)
    result = execute('single', model, 'issue', tools)
    assert result['status'] == 'budget_exhausted'
    assert not result['usage_complete']
    assert not tools.submitted


@pytest.mark.parametrize('actions', [
    [action('replace', path='app.py', old='a', new='b')],
    [action('submit'), action('read', path='app.py')],
    [action('read', path='app.py', old='unexpected')],
])
def test_invalid_actions_rejected(actions):
    with pytest.raises(ModelOutputError):
        decode_actions(json.dumps({'text': '', 'actions': actions}), {'read', 'submit'})


def test_shared_usage_across_team_roles(tools, monkeypatch):
    monkeypatch.setattr(tools, 'backend', NS(test=lambda *args: {'exit_code': 0, 'output': 'fixture'}))
    client = FakeClient([response(), response(), response(), response()])
    model = model_with(client, tools)
    result = execute('team', model, 'issue', tools)
    assert result['status'] == 'submitted'
    assert result['tokens'] == 480
    assert result['model_requests'] == 4
    assert len(client.count_calls) == 4


def test_missing_key_fails_without_request(tools, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    model = OpenAIModel()
    model.bind(tools)
    with pytest.raises(ProviderError, match='not set'):
        model.respond('agent', 'issue', [], allowed={'submit'})
    assert model.requests == 0


def test_cli_rejects_live_local_execution(monkeypatch, capsys):
    from lab.cli import main
    monkeypatch.setattr('sys.argv', ['lab', 'run', '--backend', 'local'])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert 'require --backend docker' in capsys.readouterr().err


def test_installed_sdk_http_contract(tools):
    openai = pytest.importorskip('openai')
    httpx = pytest.importorskip('httpx2')
    requests = []
    def transport(request):
        body = json.loads(request.content)
        requests.append((request.url.path, body))
        if request.url.path.endswith('/input_tokens'):
            return httpx.Response(200, json={'object': 'response.input_tokens', 'input_tokens': 100})
        return httpx.Response(200, json={
            'id': 'resp_mock', 'object': 'response', 'created_at': 0,
            'model': body['model'], 'status': 'completed',
            'output': [{'type': 'function_call', 'name': 'respond', 'call_id': 'call_mock',
                        'arguments': json.dumps({'text': 'Done', 'actions': [action('submit')]})}],
            'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120,
                      'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}},
        })
    model = OpenAIModel(client_factory=lambda: openai.AsyncOpenAI(
        api_key='fake-test-key', max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))))
    result = execute('single', model, 'issue', tools)
    assert result['status'] == 'submitted'
    assert result['tokens'] == 120
    assert [path for path, _ in requests] == ['/v1/responses/input_tokens', '/v1/responses']
