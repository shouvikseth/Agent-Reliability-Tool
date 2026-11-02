"""The hosted snapshot must agree with the published report and evidence, never raw requests."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from viewer.server import EVENT_FIELDS, Store


@pytest.mark.skipif(not shutil.which('node'), reason='Node is required for the hosted exporter')
def test_hosted_export_matches_published_api(tmp_path):
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path.as_uri() + '/'
    script = (root / 'viewer/scripts/export-hosted.mjs').as_uri()
    subprocess.run(['node', '--input-type=module', '-e',
                    f'import {{ exportHosted }} from {json.dumps(script)}; '
                    f'await exportHosted(new URL({json.dumps(destination)}));'], check=True)
    store = Store(root / 'docs/studies/heldout-v1-results.json', tmp_path / 'missing')
    hosted = json.loads((tmp_path / 'study.json').read_text())
    assert hosted.pop('hosting') == 'static'
    assert hosted == store.index()
    assert json.loads((tmp_path / 'manifest.json').read_text()) == store.data['manifest']
    evidence = json.loads((root / 'docs/studies/heldout-v1-evidence.json').read_text(encoding='utf-8'))
    assert evidence['export_sha256'] == store.export_sha256
    for slot, trial in store.trials.items():
        saved = evidence['trials'][slot]
        detail = json.loads((tmp_path / 'trials' / f'{slot}.json').read_text())
        assert detail['trial'] == trial and detail['issue'] == saved['issue']
        assert detail['available'] == {'events': True, 'patch': True}
        assert saved['result_sha256'] == trial['result_sha256']
        events = json.loads((tmp_path / 'trials' / slot / 'events.json').read_text())['events']
        assert events == saved['events'] and {e['kind'] for e in events} <= set(EVENT_FIELDS)
        assert json.loads((tmp_path / 'trials' / slot / 'patch.json').read_text())['patch'] == saved['patch']
    assert len(list(tmp_path.rglob('*.json'))) == 3*len(store.trials) + 2
    assert not list(tmp_path.rglob('request*'))
