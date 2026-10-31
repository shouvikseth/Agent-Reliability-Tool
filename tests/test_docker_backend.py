"""Opt-in integration tests; never silently substitute host execution."""
import json
import os
import subprocess
from pathlib import Path
import pytest
from lab.docker_backend import CandidateError, DockerBackend, docker, grade
from lab.tasks import TASKS, seed

pytestmark = pytest.mark.skipif(os.environ.get('LAB_DOCKER_TESTS') != '1', reason='Set LAB_DOCKER_TESTS=1 after building the image')


@pytest.fixture
def backend():
    return DockerBackend()


def test_container_restrictions_and_cleanup(backend, tmp_path):
    seed(TASKS[0], tmp_path)
    marker = tmp_path / 'host-secret.txt'
    marker.write_text('must never be copied')
    with backend.container(tmp_path / 'app.py', 'api') as name:
        info = json.loads(docker('inspect', name))[0]
        assert info['HostConfig']['NetworkMode'] == 'none'
        assert info['HostConfig']['ReadonlyRootfs'] is True
        assert info['HostConfig']['Memory'] == 256 * 1024 * 1024
        assert info['HostConfig']['PidsLimit'] == 64
        assert info['Config']['User'] == '10001:10001'
        assert not info['Mounts']
        assert info['HostConfig']['CapDrop'] == ['ALL']
    assert subprocess.run(['docker', 'inspect', name], capture_output=True).returncode != 0


def test_broken_and_fixed_are_graded_externally(backend, tmp_path):
    task = TASKS[0]
    seed(task, tmp_path)
    broken = grade(task, tmp_path / 'app.py', backend)
    assert not broken['verifier']['passed']
    assert broken['regression']['passed']
    source = tmp_path / 'app.py'
    source.write_text(source.read_text().replace(task.bad, task.good))
    assert all(row['passed'] for row in grade(task, source, backend).values())
    assert backend.test(tmp_path, 10)['exit_code'] == 0


def test_host_files_and_author_assets_absent(backend, tmp_path):
    source = tmp_path / 'app.py'
    source.write_text('''import os, pathlib, socket
from fastapi import FastAPI
def create_app():
    app = FastAPI()
    @app.get('/probe')
    def probe():
        try:
            pathlib.Path('/opt/escape').write_text('escape')
            readonly = False
        except OSError:
            readonly = True
        try:
            socket.create_connection(('1.1.1.1', 443), timeout=.2)
            network = True
        except OSError:
            network = False
        return {'uid': os.getuid(), 'readonly': readonly, 'network': network,
                'input': sorted(p.name for p in pathlib.Path('/tmp/work').iterdir()),
                'socket': pathlib.Path('/var/run/docker.sock').exists()}
    return app
''')
    with backend.client(source) as client:
        assert client.get('/probe').json() == {'uid': 10001, 'readonly': True, 'network': False, 'input': ['app.py'], 'socket': False}


def test_hanging_candidate_is_stopped_and_cleaned(backend, tmp_path):
    source = tmp_path / 'app.py'
    source.write_text('while True: pass\n')
    label = 'label=agent-reliability-lab-owner=' + backend.owner
    before = set(docker('ps', '-aq', '--filter', label).split())
    with pytest.raises(CandidateError, match='deadline'):
        with backend.client(source, timeout=1):
            pytest.fail('Hung import must not become ready')
    assert backend.test(tmp_path, .5)['timed_out']
    after = set(docker('ps', '-aq', '--filter', label).split())
    assert after == before


def test_mocked_openai_repair_through_docker(backend, tmp_path):
    from test_openai_provider import FakeClient, action, response
    from lab.openai_provider import OpenAIModel
    from lab.runtime import Budget, Tools, execute
    task = TASKS[0]
    seed(task, tmp_path / 'workspace')
    tools = Tools(tmp_path / 'workspace', tmp_path / 'events.jsonl', Budget(), backend=backend)
    fixture = FakeClient([
        response([action('read', path='app.py')]),
        response([action('replace', path='app.py', old=task.bad, new=task.good), action('test')]),
        response([action('submit')]),
    ])
    model = OpenAIModel(client_factory=lambda: fixture)
    result = execute('single', model, task.issue, tools)
    assert result['status'] == 'submitted'
    assert result['tokens'] == 360
    assert tools.diff()
    assert all(check['passed'] for check in grade(task, tools.workspace / 'app.py', backend).values())


@pytest.mark.parametrize('task', TASKS[-2:], ids=lambda task:task.id)
def test_log_development_seeds_and_reference_fixes(backend,tmp_path,task):
    seed(task,tmp_path)
    source=tmp_path/'app.py'
    broken=grade(task,source,backend)
    assert not broken['verifier']['passed'] and broken['regression']['passed']
    source.write_text(source.read_text().replace(task.bad,task.good))
    assert all(check['passed'] for check in grade(task,source,backend).values())
