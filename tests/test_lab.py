import json
from pathlib import Path
import pytest
from lab.cli import schedule
from lab.runtime import Budget, BudgetExceeded, ScriptedModel, Tools, execute
from lab.tasks import TASKS, seed


@pytest.fixture
def tools(tmp_path):
    seed(TASKS[0], tmp_path / "workspace")
    return Tools(tmp_path / "workspace", tmp_path / "events.jsonl", Budget())


def test_escape_rejected(tools):
    with pytest.raises(ValueError):
        tools.call("read", path="../events.jsonl")


def test_timeout_occurs_before_execution_once(tools, monkeypatch):
    tools.fault = "timeout"
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        class Result:
            returncode = 0
            stdout = "passed"
            stderr = ""
        return Result()
    monkeypatch.setattr("lab.runtime.subprocess.run", run)
    assert tools.call("test") == {"error": "timeout_before_execution"}
    assert calls == []
    assert tools.call("test")["exit_code"] == 0
    assert len(calls) == 1


def test_budget_counts_failed_tools(tools):
    tools.budget.tool_calls = 1
    with pytest.raises(ValueError):
        tools.call("unknown")
    with pytest.raises(BudgetExceeded):
        tools.call("list")


def test_submission_terminal(tools):
    tools.call("submit")
    with pytest.raises(ValueError):
        tools.call("replace", path="app.py", old="x", new="y")


@pytest.mark.parametrize("architecture", ["fixed", "single", "team"])
def test_architecture_contract(tools, architecture):
    result = execute(architecture, ScriptedModel(), "issue", tools)
    assert result["status"] == "submitted"
    assert tools.submitted
    assert tools.diff() == ""
    assert all(json.loads(line)["kind"] in {"tool", "model"} for line in tools.events.read_text().splitlines())


def test_schedule_balanced():
    rows = schedule(42)
    assert len(rows) == 216
    assert rows == schedule(42)
    assert all(sum(row["architecture"] == architecture for row in rows) == 72 for architecture in ["fixed", "single", "team"])
    for task in {row["task"] for row in rows}:
        assert len({row["condition"] for row in rows if row["task"] == task}) == 2


@pytest.mark.parametrize('architecture', ['fixed', 'team'])
def test_no_change_revision_preserves_patch_and_submits(tools, architecture):
    from types import SimpleNamespace
    calls = []
    tools.backend = SimpleNamespace(test=lambda *args: calls.append('test') or {'exit_code': 0, 'output': 'passed'})
    class Model:
        def respond(self, role, issue, history, *, allowed):
            actions = []
            if role in {'patch', 'writer'}:
                actions = [{'name': 'replace', 'arguments': {'path': 'app.py', 'old': TASKS[0].bad, 'new': TASKS[0].good}}]
            elif role == 'reviewer':
                actions = [{'name': 'test'}]
            elif role == 'revision':
                assert calls == ['test']
                assert TASKS[0].bad not in (tools.workspace / 'app.py').read_text()
            return {'text': 'No further changes needed.', 'actions': actions, 'usage': {'tokens': 0, 'dollars': 0}}
    result = execute(architecture, Model(), 'issue', tools)
    assert result['status'] == 'submitted'
    assert tools.submitted
    assert calls == ['test']
    assert tools.calls == 3  # edit, one test, orchestrator submission
