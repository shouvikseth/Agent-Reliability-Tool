import hashlib
import json
import threading

import httpx
import pytest

from viewer.server import Store, ViewerError, contained, create_server


@pytest.fixture
def fixture(tmp_path):
    slot, execution, run = 'a'*32, 'b'*32, 'c'*32
    directory=tmp_path/'study'/'executions'/execution/run
    directory.mkdir(parents=True)
    result={'id':run,'task':'heldout-01','architecture':'fixed','condition':'clean',
            'status':'submitted','verified_completion':True,'usage_complete':True,
            'fault_triggered':False,'seconds':1,'tokens':42,'model_requests':2}
    (directory/'result.json').write_text(json.dumps(result))
    (directory/'manifest.json').write_text(json.dumps({**result,'issue':'A visible issue.'}))
    events=[{'time':1,'kind':'model','role':'patch','response':{'text':'<script>untrusted text</script>',
             'actions':[], 'reasoning':'not a supported visible field'}, 'private':'do not expose'},
            {'time':2,'kind':'tool','name':'read','arguments':{'path':'app.py'},'result':'source text'},
            {'time':3,'kind':'local_request','artifact':'requests/request-0001.json','secret':'not served'},
            {'time':4,'kind':'fault_injected','name':'logs','condition':'malformed','boundary':'decode'}]
    (directory/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    (directory/'patch.diff').write_text('--- a/app.py\n+++ b/app.py\n-old\n+new\n')
    trial={'attempt_id':slot,'execution_id':execution,'result_path':f'executions/{execution}/{run}/result.json',
           'result_sha256':hashlib.sha256((directory/'result.json').read_bytes()).hexdigest(),
           'task':'heldout-01','architecture':'fixed','condition':'clean','repetition':1,
           'outcome':'finished','result':result}
    export={'schema':'heldout-report-v1','summary':{},'manifest':{'source_commit':'1234567',
            'design':{'tasks':[{'task':'heldout-01','category':'pagination'}],
                      'configuration':{'provider_expected':{'model':'test-model'}}}},'trials':[trial]}
    path=tmp_path/'export.json'
    path.write_text(json.dumps(export))
    static=tmp_path/'static'
    static.mkdir()
    (static/'index.html').write_text('<html>Viewer</html>')
    return tmp_path, path, directory, static, trial


def test_saved_outcome_and_optional_evidence(fixture):
    root,path,directory,_,trial=fixture
    store=Store(path,root/'study')
    assert len(store.index()['trials'])==1
    detail=store.detail(trial['attempt_id'])
    assert detail['issue']=='A visible issue.'
    assert detail['integrity']=='result_hash_matched'
    assert detail['available']=={'events':True,'patch':True}
    assert store.patch(trial['attempt_id'])['patch'].splitlines()[-1]=='+new'
    missing=Store(path,root/'missing')
    assert missing.index()['trials'][0]['verified']
    assert missing.detail(trial['attempt_id'])['available']=={'events':False,'patch':False}
    with pytest.raises(ViewerError) as caught: missing.events(trial['attempt_id'])
    assert caught.value.status==404


def test_trace_projects_only_visible_events_and_fields(fixture):
    root,path,_,_,trial=fixture
    events=Store(path,root/'study').events(trial['attempt_id'])['events']
    assert [e['kind'] for e in events]==['model','tool','fault_injected']
    assert events[0]['response']['text']=='<script>untrusted text</script>'
    assert 'reasoning' not in events[0]['response'] and 'private' not in events[0]
    assert 'requests/request' not in json.dumps(events)


@pytest.mark.parametrize('damage',['result','manifest','path'])
def test_mismatched_artifacts_are_not_presented_as_verified(fixture,damage):
    root,path,directory,_,trial=fixture
    if damage=='result': (directory/'result.json').write_text('{}')
    if damage=='manifest': (directory/'manifest.json').write_text('{}')
    if damage=='path':
        data=json.loads(path.read_text());data['trials'][0]['result_path']='../outside/result.json'
        path.write_text(json.dumps(data))
    with pytest.raises(ViewerError) as caught: Store(path,root/'study').detail(trial['attempt_id'])
    assert caught.value.status==409


def test_paths_and_unknown_ids_are_rejected(fixture):
    root,path,_,_,_=fixture
    store=Store(path,root/'study')
    with pytest.raises(ViewerError): contained(root,'../outside')
    for value in ('../result.json','a'*32+'x','0'*32):
        with pytest.raises(ViewerError) as caught: store.detail(value)
        assert caught.value.status==404


def test_http_is_loopback_read_only_same_origin_and_nonmutating(fixture):
    root,path,directory,static,trial=fixture
    before={p:p.read_bytes() for p in directory.iterdir()}
    server=create_server(Store(path,root/'study'),static,0)
    assert server.server_address[0]=='127.0.0.1'
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}',trust_env=False) as client:
            response=client.get('/')
            assert response.status_code==200 and 'Viewer' in response.text
            assert response.headers['x-content-type-options']=='nosniff'
            assert 'frame-ancestors' in response.headers['content-security-policy']
            assert client.get('/api/study').json()['trials'][0]['verified']
            assert client.get(f"/api/trials/{trial['attempt_id']}/events").status_code==200
            assert client.head('/api/study').content==b''
            for method in ('POST','PUT','DELETE','PATCH','OPTIONS'):
                assert client.request(method,'/api/study').status_code==405
            assert client.get('/api/study',headers={'Origin':'https://elsewhere.test'}).status_code==403
            assert client.get('/api/study',headers={'Host':'elsewhere.test'}).status_code==403
            assert client.get('/%2e%2e/secret.json').status_code==403
            assert client.get('/x%5cy').status_code==403
            assert client.get('/x%00y').status_code==403
            assert client.get('/api/trials/unknown').status_code==404
            assert client.get('/requests/request-0001.json').status_code==404
            assert client.get('/api/rerun').status_code==404
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)
    assert before=={p:p.read_bytes() for p in directory.iterdir()}
