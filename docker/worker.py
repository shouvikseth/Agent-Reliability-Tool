"""Public runner only. No hidden tests or reference solutions in this image."""
import contextlib
import json
import os
import sys

os.mkdir('/tmp/work')
files = json.loads(sys.stdin.readline())
for name in ('app.py', 'test_public.py'):
    if files.get(name) is not None:
        with open('/tmp/work/' + name, 'w', encoding='utf-8') as stream:
            stream.write(files[name])
del files
os.chdir('/tmp/work')
sys.path.insert(0, '/tmp/work')
if sys.argv[1] == 'test':
    import pytest
    raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', 'test_public.py']))

protocol = sys.stdout
with contextlib.redirect_stdout(sys.stderr):
    from fastapi.testclient import TestClient
    from app import create_app
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        protocol.write('{"ready":true}\n')
        protocol.flush()
        for line in sys.stdin:
            request = json.loads(line)
            response = client.request(request['method'], request['path'], json=request.get('json'))
            payload = {'status_code': response.status_code, 'body': response.text[:100000]}
            protocol.write(json.dumps(payload) + '\n')
            protocol.flush()
