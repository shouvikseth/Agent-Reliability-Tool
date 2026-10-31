import hashlib
import json
import httpx
from lab.request_capture import save_request, safe_error


def test_exact_wire_bytes_are_saved_without_headers(tmp_path):
    data, metadata = save_request(tmp_path, 1, {'messages': [{'content': 'café'}]})
    assert (tmp_path / metadata['artifact']).read_bytes() == data
    assert metadata['sha256'] == hashlib.sha256(data).hexdigest()
    assert json.loads(data)['messages'][0]['content'] == 'café'


def test_server_message_and_secrets_do_not_enter_diagnostic():
    response = httpx.Response(500, json={'error': 'error parsing tool call sk-secret private data'})
    diagnostic = safe_error(response)
    assert diagnostic['category'] == 'error parsing tool call'
    assert 'sk-secret' not in json.dumps(diagnostic)
    assert 'private data' not in json.dumps(diagnostic)


def test_repetition_abort_has_a_specific_category():
    assert safe_error(httpx.Response(500,json={'error':'prediction aborted, token repeat limit reached'}))['category'] == 'token repeat limit reached'
