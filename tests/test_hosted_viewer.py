"""The hosted snapshot must agree with the local API without publishing local artifacts."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from viewer.server import Store


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
    for slot in store.trials:
        detail = json.loads((tmp_path / 'trials' / f'{slot}.json').read_text())
        expected = store.detail(slot)
        detail.pop('artifact_note')
        expected.pop('artifact_note')
        assert detail == expected
    assert len(list(tmp_path.rglob('*.json'))) == len(store.trials) + 2
    assert not list(tmp_path.rglob('events*'))
    assert not list(tmp_path.rglob('patch*'))
