"""Local request artifacts and bounded server diagnostics; never capture headers."""
import hashlib
import json
from pathlib import Path


def serialize_request(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def save_request(directory, index, payload):
    directory = Path(directory) / 'requests'
    directory.mkdir(exist_ok=True)
    data = serialize_request(payload)
    path = directory / f'request-{index:04d}.json'
    path.write_bytes(data)
    return data, {'artifact': 'requests/' + path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def safe_error(response):
    text = response.text.lower()
    phrases = ('token repeat limit reached', 'out of memory', 'context length', 'input length', 'unexpected end of json input',
               'error parsing tool call', 'invalid json schema', 'failed to parse',
               'unexpected eof', 'runner', 'grammar', 'connection')
    return {'status': response.status_code, 'category': next((phrase for phrase in phrases if phrase in text), 'unclassified'),
            'response_sha256': hashlib.sha256(response.content).hexdigest(), 'response_bytes': len(response.content)}
