import argparse
import json
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
import os
from dataclasses import asdict
from pathlib import Path
from lab.runtime import Budget, ScriptedModel, Tools, execute
from lab.tasks import TASKS, REGRESSION, seed, verifier
from lab.policies import EXECUTION_POLICY
from lab.log_contract import LOG_CONTRACT


def grade(task, source: Path, backend=None):
    if backend is not None:
        from lab.docker_backend import grade as docker_grade
        return docker_grade(task, source, backend)
    # Rebuild from canonical files: no candidate tests, configuration, or caches.
    with tempfile.TemporaryDirectory(prefix="lab-grade-") as directory:
        clean = Path(directory)
        shutil.copyfile(source, clean / "app.py")
        (clean / "test_verifier.py").write_text(verifier(task))
        (clean / "test_regression.py").write_text(REGRESSION)
        results = {}
        for name in ("verifier", "regression"):
            try:
                process = subprocess.run([sys.executable, "-m", "pytest", "-q", f"test_{name}.py"], cwd=clean, capture_output=True, text=True, timeout=30)
                results[name] = {"passed": process.returncode == 0, "exit_code": process.returncode, "output": process.stdout + process.stderr}
            except subprocess.TimeoutExpired:
                results[name] = {"passed": False, "exit_code": -1, "output": "Candidate verification timed out"}
        return results


def validate(backend=None):
    for task in TASKS:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            seed(task, workspace)
            broken = grade(task, workspace / "app.py", backend)
            source = (workspace / "app.py").read_text()
            (workspace / "app.py").write_text(source.replace(task.bad, task.good))
            fixed = grade(task, workspace / "app.py", backend)
            valid = not broken["verifier"]["passed"] and broken["verifier"]["exit_code"] == 1 and broken["regression"]["passed"] and all(result["passed"] for result in fixed.values())
            print(json.dumps({"task": task.id, "valid": valid}))
            if not valid:
                print(json.dumps({"broken": broken, "fixed": fixed}, indent=2))
                return 1
    return 0


def smoke(output: Path, architecture, fault, backend=None, *, model=None, task=None, budget=None):
    output.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    run = output / run_id
    workspace = run / "workspace"
    task = task or TASKS[0]
    model = model or ScriptedModel()
    budget = budget or Budget()
    seed(task, workspace)
    started = time.monotonic()
    tools = Tools(workspace, run / "events.jsonl", budget, fault, backend=backend)
    metadata = model.metadata() if hasattr(model, 'metadata') else {'provider': 'scripted'}
    (run / 'manifest.json').write_text(json.dumps({'task': task.id, 'issue': task.issue, 'architecture': architecture,
        'condition': fault, 'budget': asdict(budget), 'provider': metadata,
        'execution_policy': EXECUTION_POLICY,
        'log_contract': LOG_CONTRACT,
        'image': backend.image if backend else None}, indent=2), encoding='utf-8')
    result = execute(architecture, model, task.issue, tools)
    if hasattr(model, 'metadata'):
        metadata = model.metadata()
        manifest_path = run / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['provider'] = metadata
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (run / "patch.diff").write_text(tools.diff())
    # Durable evidence survives a grader/control-plane crash. This is not a grade.
    (run / 'execution.json').write_text(json.dumps({**result, 'provider': metadata,
        'task': task.id, 'architecture': architecture, 'condition': fault,
        'submitted': tools.submitted, 'verified_completion': False}, indent=2), encoding='utf-8')
    try:
        verification = grade(task, workspace / "app.py", backend) if tools.submitted else None
    except Exception as error:
        from lab.docker_backend import InfrastructureError
        if not isinstance(error, InfrastructureError):
            raise
        verification = None
        result.update(status='infrastructure_invalid', error=str(error))
    result.update(backend='docker' if backend else 'local', image=backend.image if backend else None)
    result.update(id=run_id, task=task.id, architecture=architecture, condition=fault, fixture=isinstance(model, ScriptedModel), provider=metadata, budget=asdict(budget), tool_calls=tools.calls, fault_triggered=tools.injected, seconds=time.monotonic()-started, verification=verification, verified_completion=bool(result['status'] == 'submitted' and tools.submitted and verification and all(v["passed"] for v in verification.values())))
    (run / "result.json").write_text(json.dumps(result, indent=2))
    with sqlite3.connect(output / "results.sqlite3") as db:
        db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, result TEXT NOT NULL)")
        db.execute("INSERT INTO runs VALUES (?, ?)", (run_id, json.dumps(result)))
    print(json.dumps(result, indent=2))
    print('Saved run: ' + str(run.resolve()), file=sys.stderr)
    return result


def schedule(seed_value):
    rng = random.Random(seed_value)
    schedule_rows = []
    for task_index in range(12):
        for repetition in range(3):
            for condition in ("clean", "timeout" if task_index < 6 else "malformed"):
                architectures = ["fixed", "single", "team"]
                rng.shuffle(architectures)
                for architecture in architectures:
                    schedule_rows.append(dict(task=f"heldout-{task_index+1:02}", repetition=repetition+1, condition=condition, architecture=architecture))
    return schedule_rows


def main():
    parser = argparse.ArgumentParser(description="Agent Reliability Lab development pilot")
    parser.add_argument("command", choices=["validate", "smoke", "schedule", "run"])
    parser.add_argument("--output", type=Path, default=Path("runs"))
    parser.add_argument("--architecture", choices=["fixed", "single", "team"], default="single")
    parser.add_argument("--fault", choices=["clean", "timeout", "malformed"], default="clean")
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--backend", choices=["local", "docker"], default="local")
    parser.add_argument('--provider', choices=['openai', 'ollama'], default='openai')
    parser.add_argument('--model', default=None)
    parser.add_argument('--task', choices=[task.id for task in TASKS], default=TASKS[0].id)
    parser.add_argument('--max-tokens', type=int, default=24000)
    parser.add_argument('--max-dollars', type=float, default=.25)
    parser.add_argument('--max-seconds', type=float, default=180)
    parser.add_argument('--max-tool-calls', type=int, default=20)
    parser.add_argument('--max-output-tokens', type=int, default=None)
    parser.add_argument('--tokenizer-file', type=Path, help='Opt in to validated Qwen 7B tokenizer admission')
    args = parser.parse_args()
    model = None
    if args.command == 'run':
        if args.backend != 'docker':
            parser.error('Live provider runs require --backend docker')
        if args.provider == 'openai' and not os.environ.get('OPENAI_API_KEY'):
            parser.error('OPENAI_API_KEY is missing. Set it in this PowerShell session; never paste it into chat.')
        try:
            if args.provider == 'openai':
                if args.tokenizer_file:
                    parser.error('--tokenizer-file is for Ollama only')
                from lab.openai_provider import OpenAIModel, DEFAULT_MODEL
                model = OpenAIModel(args.model or DEFAULT_MODEL, args.max_output_tokens if args.max_output_tokens is not None else 2048)
            else:
                from lab.ollama_provider import OllamaModel, DEFAULT_MODEL
                model = OllamaModel(args.model or DEFAULT_MODEL, args.max_output_tokens if args.max_output_tokens is not None else 1024, seed=args.seed, tokenizer_file=args.tokenizer_file)
            budget = Budget(args.max_tool_calls, args.max_seconds, args.max_tokens, args.max_dollars)
        except (ValueError, OSError, ImportError) as error:
            parser.error(str(error))
    backend = None
    if args.backend == 'docker' and args.command != 'schedule':
        from lab.docker_backend import DockerBackend
        backend = DockerBackend()
    if args.command == "validate":
        raise SystemExit(validate(backend))
    if args.command == "smoke":
        smoke(args.output, args.architecture, args.fault, backend)
    elif args.command == 'run':
        result = smoke(args.output, args.architecture, args.fault, backend, model=model,
                       task=next(task for task in TASKS if task.id == args.task), budget=budget)
        raise SystemExit(0 if result['verified_completion'] else 1)
    else:
        print(json.dumps({"status": "design_only_unavailable_heldout_tasks", "seed": args.seed, "runs": schedule(args.seed)}, indent=2))


if __name__ == "__main__":
    main()
