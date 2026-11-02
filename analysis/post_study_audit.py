"""Post-study audit of the frozen evaluation. Never rewrites its results or ledger.

profile reads saved traces. differential compares final sources with the reference
inside Docker. sensitivity generates separate clean-condition trials through Ollama;
they are labeled sidecar evidence, never held-out replacements or tuning input.
"""
import argparse
from collections import Counter, defaultdict
import contextlib
import hashlib
import io
import json
from math import comb
from pathlib import Path
import sys
import tempfile

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LONG = 'x'*200
BATTERY = [
    *[('POST', '/issues', {'title': title}) for title in 'abc'],
    *[('POST', '/issues', {'title': f't{i}'}) for i in range(12)],
    *[('GET', '/issues' + query, None) for query in (
        '', '?limit=0', '?limit=1', '?limit=2', '?limit=10', '?limit=100', '?limit=101', '?limit=-1',
        '?limit=abc', '?offset=0', '?offset=-1', '?offset=5', '?offset=10', '?offset=14', '?offset=100',
        '?offset=1&limit=2', '?state=open', '?state=closed', '?state=bad')],
    ('POST', '/issues', {'title': '  pad  '}), ('POST', '/issues', {'title': '   '}),
    ('POST', '/issues', {'title': ''}), ('POST', '/issues', {}),
    ('POST', '/issues', {'title': LONG}), ('POST', '/issues', {'title': LONG+'y'}),
    ('POST', '/issues', {'title': '  '+LONG[:198]+'  '}),
    ('POST', '/issues?request_key=k1', {'title': 'one'}), ('POST', '/issues?request_key=k1', {'title': 'one'}),
    ('POST', '/issues?request_key=k1', {'title': 'two'}), ('POST', '/issues?request_key=K1', {'title': 'one'}),
    ('POST', '/issues?request_key=k2', {'title': 'one'}), ('POST', '/issues?request_key=', {'title': 'e'}),
    ('POST', '/issues?request_key=', {'title': 'e'}), ('POST', '/issues?request_key=', {'title': 'f'}),
    ('POST', '/issues?request_key=k1', {'title': '  one  '}),
    ('POST', '/issues/2/close', None), ('POST', '/issues/2/close', None), ('POST', '/issues/999/close', None),
    ('POST', '/issues/0/close', None), ('POST', '/issues/abc/close', None), ('POST', '/issues/3/close', None),
    *[('GET', '/issues' + query, None) for query in (
        '?state=closed', '?state=open&limit=3', '?state=open&limit=3&offset=2', '?limit=100&offset=0')],
]


def load(directory):
    data = json.loads((ROOT/'docs/studies/heldout-v1-results.json').read_text(encoding='utf-8'))
    rows = []
    for trial in data['trials']:
        run = (Path(directory)/trial['result_path']).parent
        rows.append({**{k: trial[k] for k in ('task', 'architecture', 'condition', 'repetition')},
                     'verified': trial['result']['verified_completion'], 'status': trial['result']['status'],
                     'error': trial['result'].get('error'), 'source': (run/'workspace/app.py').read_text(encoding='utf-8'),
                     'patch': (run/'patch.diff').read_text(encoding='utf-8'),
                     'events': [json.loads(line) for line in (run/'events.jsonl').read_text(encoding='utf-8').splitlines()]})
    return rows


def sign_test(left, right):
    wins = sum(left[t] and not right[t] for t in left)
    losses = sum(right[t] and not left[t] for t in left)
    total = wins+losses
    p = min(1, 2*sum(comb(total, i) for i in range(min(wins, losses)+1))/2**total) if total else 1
    return {'wins': wins, 'losses': losses, 'two_sided_p': round(p, 4)}


def profile(directory, _=None):
    rows = load(directory)
    cells, pairs = defaultdict(list), defaultdict(lambda: defaultdict(int))
    tests = Counter()
    green_failures = 0
    for row in rows:
        cells[(row['task'], row['architecture'], row['condition'])].append(row['patch'])
        pairs[(row['task'], row['architecture'])][row['condition']] += row['verified']
        results = [e['result'] for e in row['events'] if e['kind'] == 'tool' and e['name'] == 'test']
        tests.update('fault' if 'error' in r else 'cached' if r.get('cached') else f"exit_{r['exit_code']}" for r in results)
        green_failures += bool(row['status'] == 'submitted' and not row['verified']
                               and any(r.get('exit_code') == 0 for r in results))
    architectures = ('fixed', 'single', 'team')
    tasks = sorted({row['task'] for row in rows})
    solved = {a: {t: sum(r['verified'] for r in rows if (r['task'], r['architecture'], r['condition']) == (t, a, 'clean')) >= 2
                  for t in tasks} for a in architectures}
    reference = (ROOT/'target_app/app.py').read_text()
    flips = [{'task': t, 'architecture': a, 'verified': dict(c)} for (t, a), c in pairs.items() if len(set(c.values())) > 1]
    return {'cells': len(cells), 'cells_with_identical_patches': sum(len(set(v)) == 1 for v in cells.values()),
            'task_architecture_pairs': len(pairs), 'outcome_changed_by_fault': flips,
            'test_tool_results': dict(tests), 'failed_grading_after_green_public_test': green_failures,
            'clean_tasks_solved': {a: sum(s.values()) for a, s in solved.items()},
            'clean_sign_tests': {'fixed_vs_team': sign_test(solved['fixed'], solved['team']),
                                 'fixed_vs_single': sign_test(solved['fixed'], solved['single']),
                                 'team_vs_single': sign_test(solved['team'], solved['single'])},
            'failed_with_reference_source': [{k: r[k] for k in ('task', 'architecture', 'condition', 'repetition', 'error')}
                                             for r in rows if not r['verified'] and r['source'] == reference]}


def sweep(backend, source):
    from lab.docker_backend import CandidateError
    replies = []
    try:
        with backend.client(Path(source), timeout=60) as client:
            for method, path, body in BATTERY:
                response = client.request(method, path, body)
                replies.append((response.status_code, response.json() if response.status_code < 400 else None))
    except CandidateError as error:
        return {'crash': str(error), 'replies': replies}
    return {'crash': None, 'replies': replies}


def differential(directory, _=None):
    from lab.docker_backend import DockerBackend
    rows = [row for row in load(directory) if row['verified']]
    backend = DockerBackend()
    reference = sweep(backend, ROOT/'target_app/app.py')['replies']
    behavior = {}
    with tempfile.TemporaryDirectory(prefix='lab-audit-') as temporary:
        for source in {row['source'] for row in rows}:
            path = Path(temporary)/'app.py'
            path.write_text(source, encoding='utf-8')
            behavior[source] = sweep(backend, path)
    found, counts = [], Counter()
    for source, result in behavior.items():
        changes = [{'request': f'{BATTERY[i][0]} {BATTERY[i][1]}', 'reference': reference[i][0], 'candidate': reply[0]}
                   for i, reply in enumerate(result['replies']) if reply != reference[i]]
        matched = [row for row in rows if row['source'] == source]
        if changes or result['crash']:
            counts.update(row['architecture'] for row in matched)
            found.append({'sha256': hashlib.sha256(source.encode()).hexdigest(), 'trials': len(matched),
                          'tasks': sorted({row['task'] for row in matched}), 'crash': result['crash'], 'changes': changes})
    return {'requests': len(BATTERY), 'verified_trials': len(rows), 'unique_sources': len(behavior),
            'verified_trials_differing': dict(counts), 'differences': found}


class Temperature(httpx.AsyncBaseTransport):
    def __init__(self, value):
        self.value = value

    async def handle_async_request(self, request):
        body = await request.aread()
        if request.url.path == '/api/chat':
            data = json.loads(body)
            data['options']['temperature'] = self.value
            body = json.dumps(data).encode()
        async with httpx.AsyncClient(trust_env=False, timeout=None) as client:
            response = await client.request(request.method, str(request.url), content=body,
                                            headers={'Content-Type': 'application/json'})
        return httpx.Response(response.status_code, content=response.content, headers={'content-type': 'application/json'})


def sensitivity(work, tokenizer_file):
    from lab.cli import smoke
    from lab.docker_backend import DockerBackend
    from lab.heldout import HELDOUT_TASKS
    from lab.ollama_provider import OllamaModel
    from lab.runtime import Budget
    backend = DockerBackend()
    rows = []
    for plan, temperature, seed in (('replay', 0, 20261030), ('seed-only', 0, 1), ('t0.2', .2, 11), ('t0.2', .2, 12), ('t0.2', .2, 13)):
        for task in HELDOUT_TASKS:
            for architecture in ('fixed', 'single', 'team'):
                model = OllamaModel(tokenizer_file=tokenizer_file, seed=seed, transport=Temperature(temperature))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = smoke(Path(work), architecture, 'clean', backend, model=model, task=task,
                                   budget=Budget(20, 600, 24000, .25))
                rows.append({'plan': plan, 'temperature': temperature, 'seed': seed, 'task': task.id,
                             'architecture': architecture, 'verified': result['verified_completion'],
                             'status': result['status'], 'error': result.get('error')})
                print(len(rows), plan, task.id, architecture, rows[-1]['verified'], flush=True)
    return summarize(rows)


def summarize(rows):
    totals = Counter((r['plan'], r['seed'], r['architecture']) for r in rows)
    wins = Counter((r['plan'], r['seed'], r['architecture']) for r in rows if r['verified'])
    return {'clean_trials': len(rows), 'status': dict(Counter(r['status'] for r in rows)),
            'verified': [{'plan': p, 'seed': s, 'architecture': a, 'verified': wins[(p, s, a)], 'trials': n}
                         for (p, s, a), n in sorted(totals.items(), key=str)], 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['profile', 'differential', 'sensitivity'])
    parser.add_argument('path', type=Path, help='Study directory, or an empty work directory for sensitivity')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tokenizer-file', type=Path)
    args = parser.parse_args()
    if args.command == 'sensitivity' and args.tokenizer_file is None:
        parser.error('sensitivity requires --tokenizer-file')
    section = {'profile': profile, 'differential': differential, 'sensitivity': sensitivity}[args.command](args.path, args.tokenizer_file)
    audit = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {'schema': 'heldout-audit-v1'}
    audit[args.command] = section
    args.output.write_text(json.dumps(audit, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
