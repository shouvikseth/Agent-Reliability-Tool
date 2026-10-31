"""Account for every scheduled development trial; no statistical generalization."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import statistics


def summarize(schedule, rows, results):
    key = lambda row: (row['task'], row['repetition'], row['architecture'], row.get('condition', 'clean'))
    expected = Counter(key(row) for row in schedule)
    observed = Counter(key(row) for row in rows)
    if expected != observed or any(count != 1 for count in observed.values()):
        raise ValueError('Schedule is incomplete, duplicated, or contains unexpected outcomes')
    if len({row['id'] for row in rows}) != len(rows) or set(results) != {row['id'] for row in rows}:
        raise ValueError('Run IDs or result records do not match scheduled outcomes')
    groups = {}
    for architecture in sorted({row['architecture'] for row in rows}):
        group = [results[row['id']] for row in rows if row['architecture'] == architecture]
        successes = sum(result['verified_completion'] for result in group)
        submitted = [result for result in group if result.get('verification') is not None]
        complete_usage = all(result.get('usage_complete', True) for result in group)
        known_cost = sum(result.get('known_dollars', result.get('dollars') or 0) for result in group)
        durations = [result['seconds'] for result in group]
        success_durations = [result['seconds'] for result in group if result['verified_completion']]
        regressions = sum(not result['verification']['regression']['passed'] for result in submitted)
        groups[architecture] = {
            'scheduled': len(group), 'verified': successes, 'completion_percent': successes/len(group)*100,
            'statuses': dict(Counter(result['status'] for result in group)),
            'submitted_and_graded': len(submitted),
            'regression_failures': regressions,
            'regression_percent_of_graded': regressions/len(submitted)*100 if submitted else None,
            'median_seconds_all_outcomes': statistics.median(durations),
            'min_seconds': min(durations), 'max_seconds': max(durations),
            'median_seconds_successful': statistics.median(success_durations) if success_durations else None,
            'budget_exhausted': sum(result['status']=='budget_exhausted' for result in group),
            'reported_tokens': sum(result['tokens'] for result in group),
            'model_requests': sum(result.get('model_requests', 0) for result in group),
            'uncertain_reserved_tokens': sum(result.get('uncertain_reserved_tokens', 0) for result in group),
            'usage_complete': complete_usage,
            'known_api_dollars': known_cost,
            'api_cost_per_success': known_cost/successes if successes and complete_usage else None,
            'cached_test_calls': sum(result.get('cached_test_calls', 0) for result in group),
            'faults_assigned': sum(result.get('condition', 'clean') != 'clean' for result in group),
            'faults_triggered': sum(result.get('fault_triggered', False) for result in group),
        }
    consistency = {}
    for task in sorted({row['task'] for row in rows}):
        consistency[task] = {}
        for architecture in groups:
            subset = [results[row['id']] for row in rows if row['task'] == task and row['architecture'] == architecture]
            consistency[task][architecture] = {'successes': sum(result['verified_completion'] for result in subset), 'repetitions': len(subset)}
    return {'scheduled': len(schedule), 'recorded': len(rows), 'architectures': groups, 'task_consistency': consistency}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pilot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; preserve previous reports')
    manifest = json.loads((args.pilot/'schedule.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (args.pilot/'summary.jsonl').read_text(encoding='utf-8').splitlines()]
    results = {}
    for row in rows:
        if not re.fullmatch('[a-f0-9]{32}', row['id']):
            raise ValueError('Invalid run ID')
        result = json.loads((args.pilot/row['id']/'result.json').read_text(encoding='utf-8'))
        if result['id'] != row['id'] or result['task'] != row['task'] or result['architecture'] != row['architecture']:
            raise ValueError('Result identity mismatch')
        if result.get('condition','clean') != row.get('condition','clean'):
            raise ValueError('Result fault condition mismatch')
        results[row['id']] = result
    summary = summarize(manifest['schedule'], rows, results)
    args.output.write_text(json.dumps({'scope': 'development_only', 'manifest': manifest,
        'summary': summary, 'trials': [{**row, 'result': results[row['id']]} for row in rows]}, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
