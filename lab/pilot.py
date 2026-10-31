"""Local-only development pilot; never schedules held-out or paid provider runs."""
import argparse
import contextlib
import io
import json
import random
import subprocess
import uuid
from pathlib import Path
from lab.cli import smoke
from lab.docker_backend import DockerBackend
from lab.ollama_provider import OllamaModel
from lab.prompts import COMPLETION_VERSION
from lab.runtime import Budget
from lab.policies import EXECUTION_POLICY, CONTEXT_POLICY
from lab.tasks import TASKS


def schedule(task_ids, repetitions, seed, condition='clean'):
    rng = random.Random(seed)
    rows = []
    for task_id in task_ids:
        for repetition in range(1, repetitions+1):
            architectures = ['fixed', 'single', 'team']
            rng.shuffle(architectures)
            fault = 'clean' if condition == 'clean' else ('timeout' if next(i for i,t in enumerate(TASKS) if t.id == task_id) < 4 else 'malformed')
            rows.extend({'task': task_id, 'repetition': repetition, 'architecture': architecture, 'condition': fault} for architecture in architectures)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', choices=[task.id for task in TASKS],
                        default=['pagination-offset', 'blank-title', 'repeat-close', 'request-conflict'])
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--output', type=Path, default=Path('runs'))
    parser.add_argument('--tokenizer-file', type=Path)
    parser.add_argument('--condition', choices=['clean', 'injected'], default='clean')
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 3 or len(set(args.tasks)) != len(args.tasks):
        parser.error('Use 1–3 repetitions and unique development task IDs')
    # Validate local assets before allocating a pilot directory.
    OllamaModel(tokenizer_file=args.tokenizer_file)
    backend = DockerBackend()
    directory = args.output / ('pilot-' + uuid.uuid4().hex)
    directory.mkdir(parents=True)
    rows = schedule(args.tasks, args.repetitions, args.seed, args.condition)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
    manifest = {'completion_version': COMPLETION_VERSION, 'commit': commit.stdout.strip(),
                'execution_policy': EXECUTION_POLICY, 'context_policy': CONTEXT_POLICY,
                'admission_policy': 'qwen-tokenizer-v1' if args.tokenizer_file else 'message-bytes-v2',
                'seed': args.seed, 'condition': args.condition, 'study': 'development_only',
                'image': backend.image, 'schedule': rows}
    (directory / 'schedule.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Pilot: ' + str(directory.resolve()), flush=True)
    for index, row in enumerate(rows, 1):
        task = next(task for task in TASKS if task.id == row['task'])
        with contextlib.redirect_stdout(io.StringIO()):
            result = smoke(directory, row['architecture'], row['condition'], backend,
                           model=OllamaModel(seed=args.seed, tokenizer_file=args.tokenizer_file), task=task,
                           budget=Budget(tool_calls=20, seconds=600, tokens=24000, dollars=.25))
        summary = {**row, 'id': result['id'], 'status': result['status'],
                   'verified_completion': result['verified_completion'], 'tokens': result['tokens'],
                   'seconds': result['seconds'], 'error': result.get('error'),
                   'fault_triggered': result['fault_triggered'],
                   'model_digest': result['provider']['model_digest']}
        with (directory / 'summary.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(summary) + '\n')
        print(f'{index}/{len(rows)} ' + json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
