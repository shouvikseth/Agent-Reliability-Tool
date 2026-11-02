"""Publish allowlisted visible traces and patches; raw model requests stay local."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from viewer.server import Store


def evidence(export, directory):
    store = Store(export, directory)
    trials = {}
    for slot in store.trials:
        detail = store.detail(slot)
        if not all(detail['available'].values()):
            raise ValueError('Missing local evidence for trial ' + slot)
        events, patch = store.events(slot)['events'], store.patch(slot)['patch']
        trials[slot] = {'issue': detail['issue'], 'result_sha256': detail['trial']['result_sha256'],
                        'events': events, 'patch': patch}
    # Normalize line endings: Git checkouts of the report differ by platform.
    digest = hashlib.sha256(Path(export).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    return {'schema': 'heldout-evidence-v1', 'export_sha256': digest,
            'projection': 'visible_model_tools_and_accounting_only', 'trials': trials}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--export', type=Path, default=ROOT/'docs/studies/heldout-v1-results.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve prior exports')
    data = json.dumps(evidence(args.export, args.directory), separators=(',', ':'), allow_nan=False) + '\n'
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(data)
    print(hashlib.sha256(data.encode()).hexdigest())


if __name__ == '__main__':
    main()
