"""Development runtime. Local execution is trusted-code only, not a sandbox."""
import difflib
import json
import subprocess
import sys
import time
import math
import hashlib
from lab.policies import EXECUTION_POLICY, MAX_ACTIONS
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Budget:
    tool_calls: int = 20
    seconds: float = 60
    tokens: int = 12000
    dollars: float = 1.0

    def __post_init__(self):
        if any(not math.isfinite(value) or value <= 0 for value in (self.tool_calls, self.seconds, self.tokens, self.dollars)):
            raise ValueError('All budgets must be finite and positive')


class BudgetExceeded(Exception):
    pass


class Tools:
    def __init__(self, workspace: Path, events: Path, budget: Budget, fault: str = "clean", backend=None):
        self.backend = backend
        self.workspace = workspace.resolve()
        self.events = events
        self.budget = budget
        self.fault = fault
        self.started = time.monotonic()
        self.calls = 0
        self.injected = False
        self.submitted = False
        self.original = (workspace / "app.py").read_text()
        self.passed_tests = {}
        self.cached_tests = 0

    def event(self, kind, **data):
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.time(), "kind": kind, **data}) + "\n")

    def remaining(self):
        return self.budget.seconds - (time.monotonic() - self.started)

    def path(self, name):
        path = (self.workspace / name).resolve()
        if not path.is_relative_to(self.workspace) or path.is_symlink():
            raise ValueError("Path escapes workspace")
        return path

    def call(self, name: str, **args):
        if self.submitted:
            raise ValueError("Run already submitted")
        if self.calls >= self.budget.tool_calls or self.remaining() <= 0:
            raise BudgetExceeded("Tool or wall-clock budget exhausted")
        self.calls += 1
        try:
            if not self.injected and ((self.fault == "timeout" and name == "test") or (self.fault == "malformed" and name == "logs")):
                self.injected = True
                result = {"error": "timeout_before_execution"} if name == "test" else "{malformed-response"
            elif name == "list":
                result = sorted(p.name for p in self.workspace.iterdir() if p.is_file())
            elif name in {"read", "logs"}:
                result = self.path("logs.txt" if name == "logs" else args["path"]).read_text()[:30000]
            elif name == "replace":
                if args["path"] != "app.py":
                    raise ValueError("Only app.py may be edited")
                path = self.path(args["path"])
                source = path.read_text()
                if not args["old"] or source.count(args["old"]) != 1:
                    raise ValueError("Replacement anchor must occur exactly once")
                path.write_text(source.replace(args["old"], args["new"]))
                result = {"edited": args["path"]}
            elif name == "test":
                key = hashlib.sha256((self.workspace / 'app.py').read_bytes()).hexdigest()
                if key in self.passed_tests:
                    self.cached_tests += 1
                    result = {**self.passed_tests[key], 'cached': True, 'source_sha256': key}
                else:
                    if self.backend is not None:
                        result = self.backend.test(self.workspace, self.remaining())
                    else:
                        process = subprocess.run([sys.executable, "-m", "pytest", "-q", "test_public.py"], cwd=self.workspace, capture_output=True, text=True, timeout=max(.01, self.remaining()))
                        result = {"exit_code": process.returncode, "output": (process.stdout + process.stderr)[-10000:]}
                    if result.get('exit_code') == 0:
                        self.passed_tests[key] = dict(result)
            elif name == "submit":
                self.submitted = True
                result = {"submitted": True}
            else:
                raise ValueError("Unknown tool")
            self.event("tool", name=name, arguments=args, result=result)
            return result
        except Exception as error:
            self.event("tool_error", name=name, arguments=args, error=str(error))
            raise

    def diff(self):
        return "".join(difflib.unified_diff(self.original.splitlines(True), (self.workspace / "app.py").read_text().splitlines(True), fromfile="a/app.py", tofile="b/app.py"))


class Model(Protocol):
    """Provider must return visible output and measured usage; never private reasoning."""
    def respond(self, role: str, issue: str, history: list, *, allowed: set[str]) -> dict: ...


def execute(architecture: str, model: Model, issue: str, tools: Tools):
    history = []
    tokens, dollars = 0, 0.0
    empty_turns = 0
    if hasattr(model, 'bind'):
        model.bind(tools)

    def outcome(status, **extra):
        usage = model.snapshot() if hasattr(model, 'snapshot') else {'tokens': tokens, 'dollars': dollars}
        return {'status': status, **usage, 'execution_policy': EXECUTION_POLICY,
                'cached_test_calls': tools.cached_tests, **extra}

    def step(role, allowed):
        nonlocal tokens, dollars, empty_turns
        if tools.remaining() <= 0:
            raise BudgetExceeded("Wall-clock budget exhausted")
        response = model.respond(role, issue, history, allowed=allowed)
        usage = response["usage"]
        tokens += usage["tokens"]
        dollars += usage["dollars"]
        tools.event("model", role=role, response=response)
        if tokens > tools.budget.tokens or dollars > tools.budget.dollars or tools.remaining() <= 0:
            raise BudgetExceeded("Model budget exhausted")
        history.append({"role": role, "response": response})
        actions = response.get('actions', [])
        if len(actions) > MAX_ACTIONS:
            raise ValueError('Response exceeds six-action limit')
        if role == 'agent' and not actions:
            empty_turns += 1
            if empty_turns >= 2:
                raise ValueError('Two consecutive empty agent turns without submission')
            feedback = {'error': 'No actions executed. Use tools to continue, or submit explicitly when ready.'}
            history.append({'tool': 'runtime_feedback', 'result': feedback})
            tools.event('runtime_feedback', result=feedback)
        else:
            empty_turns = 0
        for action in actions:
            if action["name"] not in allowed:
                raise ValueError(f"Tool forbidden in {role}: {action['name']}")
            try:
                result = tools.call(action["name"], **action.get("arguments", {}))
            except (ValueError, FileNotFoundError) as error:
                result = {'error': str(error)}
            history.append({"tool": action["name"], 'arguments': action.get('arguments', {}), "result": result})
        return response

    read = {"list", "read", "logs"}
    all_tools = read | {"replace", "test", "submit"}
    try:
        if architecture == "fixed":
            step("inspect", read)
            step("patch", {"replace"})
            history.append({"tool": "test", "result": tools.call("test")})
            step("revision", {"replace", "test"})
            tools.call("submit")
        elif architecture == "single":
            for _ in range(tools.budget.tool_calls + 1):
                step("agent", all_tools)
                if tools.submitted:
                    break
            if not tools.submitted:
                raise BudgetExceeded("Decision limit exhausted")
        elif architecture == "team":
            step("planner", read)
            step("writer", all_tools - {"submit"})
            step("reviewer", read | {"test"})
            step("revision", all_tools - {"submit"})
            tools.call("submit")
        else:
            raise ValueError("Unknown architecture")
        return outcome('submitted')
    except BudgetExceeded as error:
        tools.event('run_stopped', status='budget_exhausted', error=str(error))
        return outcome('budget_exhausted', error=str(error))
    except Exception as error:
        from lab.docker_backend import InfrastructureError
        from lab.openai_provider import ProviderError
        status = 'infrastructure_invalid' if isinstance(error, (InfrastructureError, ProviderError)) else 'agent_error'
        tools.event('run_stopped', status=status, error=str(error))
        return outcome(status, error=str(error))


class ScriptedModel:
    """Contract smoke fixture. No repair capability; never benchmark as an LLM."""
    def respond(self, role, issue, history, *, allowed=None):
        actions = [{"name": "read", "arguments": {"path": "app.py"}}] if role in {"inspect", "planner"} else []
        if role == "agent":
            actions = [{"name": "submit"}]
        return {"text": "Scripted no-op smoke fixture", "actions": actions, "usage": {"tokens": 0, "dollars": 0}}
