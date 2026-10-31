"""Disposable, network-disabled containers; no host bind mounts or hidden tests."""
import json
import queue
import subprocess
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager

IMAGE = 'agent-reliability-lab:dev'


class InfrastructureError(RuntimeError):
    pass


class CandidateError(RuntimeError):
    pass


def docker(*args, timeout=30):
    try:
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InfrastructureError(str(error)) from error
    if result.returncode:
        raise InfrastructureError((result.stderr or result.stdout)[-4000:])
    return result.stdout.strip()


class DockerBackend:
    def __init__(self, image=IMAGE):
        # Resolve a mutable tag once; all containers use the same immutable local ID.
        self.image = docker('image', 'inspect', image, '--format', '{{.Id}}')
        self.inputs = {}
        self.owner = uuid.uuid4().hex

    @contextmanager
    def container(self, source, mode, public=None):
        name = 'reliability-lab-' + uuid.uuid4().hex
        created = False
        if source.is_symlink() or not source.is_file():
            raise ValueError('Candidate must be a regular file')
        data = source.read_bytes()
        if len(data) > 1000000:
            raise ValueError('Candidate exceeds 1 MB')
        self.inputs[name] = json.dumps({'app.py': data.decode('utf-8'), 'test_public.py': public}) + '\n'
        try:
            docker('create', '--name', name, '--label', 'agent-reliability-lab=true',
                   '--label', 'agent-reliability-lab-owner=' + self.owner,
                   '--interactive', '--init', '--network', 'none', '--read-only',
                   '--user', '10001:10001', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges=true', '--pids-limit', '64',
                   '--memory', '256m', '--memory-swap', '256m', '--cpus', '1',
                   '--ulimit', 'nofile=128:128', '--log-driver', 'none',
                   '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777',
                   '--env', 'HTTP_PROXY=', '--env', 'HTTPS_PROXY=', '--env', 'ALL_PROXY=',
                   '--env', 'http_proxy=', '--env', 'https_proxy=', '--env', 'all_proxy=',
                   self.image, mode)
            created = True
            yield name
        finally:
            self.inputs.pop(name, None)
            if created:
                docker('rm', '--force', name)

    def test(self, workspace, timeout):
        from lab.tasks import REGRESSION
        deadline = time.monotonic() + timeout
        with self.container(workspace / 'app.py', 'test', REGRESSION) as name:
            # Drain continuously but retain only a bounded tail in host memory.
            tail = deque(maxlen=4)
            process = subprocess.Popen(['docker', 'start', '--attach', '--interactive', name], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            def drain():
                while chunk := process.stdout.read(4096):
                    tail.append(chunk)
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            timed_out = False
            try:
                process.stdin.write(self.inputs[name].encode('utf-8'))
                process.stdin.close()
                process.wait(timeout=max(.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                if process.poll() is None:
                    subprocess.run(['docker', 'kill', name], capture_output=True, timeout=10)
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=2)
                process.stdout.close()
            if timed_out:
                return {'exit_code': -1, 'output': 'Candidate test timed out', 'timed_out': True}
            text = b''.join(tail)[-10000:].decode('utf-8', errors='replace')
            state = json.loads(docker('inspect', name))[0]['State']
            if state.get('Error'):
                raise InfrastructureError(state['Error'])
            return {'exit_code': state['ExitCode'], 'output': text, 'oom_killed': state['OOMKilled']}

    @contextmanager
    def client(self, source, timeout=20):
        deadline = time.monotonic() + timeout
        with self.container(source, 'api') as name:
            process = subprocess.Popen(['docker', 'start', '--attach', '--interactive', name],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, encoding='utf-8', errors='replace', bufsize=1)
            messages = queue.Queue(maxsize=16)
            stop = threading.Event()
            def read():
                while not stop.is_set():
                    line = process.stdout.readline(200001)
                    if not line:
                        break
                    try:
                        messages.put(line, timeout=.1)
                    except queue.Full:
                        break
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            client = RemoteClient(process, messages, deadline)
            try:
                process.stdin.write(self.inputs[name])
                process.stdin.flush()
                if client.receive() != {'ready': True}:
                    raise CandidateError('Invalid application startup response')
                yield client
            finally:
                stop.set()
                subprocess.run(['docker', 'kill', name], capture_output=True, timeout=10)
                process.kill() if process.poll() is None else None
                process.wait(timeout=5)
                reader.join(timeout=2)
                process.stdin.close()
                process.stdout.close()


class RemoteClient:
    def __init__(self, process, messages, deadline):
        self.process, self.messages, self.deadline = process, messages, deadline

    def receive(self):
        while time.monotonic() < self.deadline:
            try:
                line = self.messages.get(timeout=min(.1, max(.001, self.deadline-time.monotonic())))
                return json.loads(line)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise CandidateError('Application exited before responding')
            except (ValueError, TypeError) as error:
                raise CandidateError('Invalid application protocol') from error
        raise CandidateError('Application deadline exceeded')

    def request(self, method, path, json=None):
        try:
            self.process.stdin.write(__import__('json').dumps({'method': method, 'path': path, 'json': json}) + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise CandidateError('Application connection closed') from error
        payload = self.receive()
        return Response(payload)

    def get(self, path):
        return self.request('GET', path)

    def post(self, path, json=None):
        return self.request('POST', path, json)


class Response:
    def __init__(self, payload):
        try:
            self.status_code = int(payload['status_code'])
            self.body = payload['body']
        except (KeyError, ValueError, TypeError) as error:
            raise CandidateError('Invalid HTTP response envelope') from error

    def json(self):
        return json.loads(self.body)


def grade(task, source, backend):
    results = {}
    for kind in ('verifier', 'regression'):
        try:
            with backend.client(source) as client:
                if kind == 'verifier':
                    for title in ['a', 'b', 'c']:
                        client.post('/issues', json={'title': title})
                    # Author-owned checks execute on the orchestrator, never candidate code.
                    exec(task.check, {'client': client})
                else:
                    assert client.get('/issues').json() == []
                    assert client.post('/issues', json={'title': 'hello'}).status_code == 201
                    assert client.post('/issues', json={}).status_code == 422
                    assert client.post('/issues/1/close').status_code == 200
            results[kind] = {'passed': True, 'exit_code': 0, 'output': 'External API checks passed'}
        except InfrastructureError:
            raise
        except (AssertionError, CandidateError, ValueError, KeyError, IndexError, TypeError) as error:
            results[kind] = {'passed': False, 'exit_code': 1, 'output': type(error).__name__ + ': ' + str(error)}
    return results
