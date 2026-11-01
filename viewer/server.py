"""Loopback-only, read-only API and static Next.js viewer. No candidate imports."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
HEX = re.compile(r'[a-f0-9]{32}')
MAX_FILE = 16 * 1024 * 1024
EVENT_FIELDS = {
    'model': ('role', 'response'),
    'tool': ('name', 'arguments', 'result'),
    'fault_injected': ('name', 'condition', 'boundary'),
    'context_acquisition': ('attempt', 'log_ok'),
    'model_usage': ('role', 'model', 'usage'),
    'model_reservation': ('role', 'input_token_bound', 'output_limit', 'reserved_dollars'),
    'context_accounting': ('role', 'policy', 'expected_input_tokens', 'input_token_bound', 'output_limit'),
    'context_measurement': ('role', 'input_token_bound', 'actual_input_tokens', 'unused_reservation'),
    'run_stopped': ('status', 'error'),
    'local_error': ('status_code', 'category', 'sha256', 'bytes'),
}


class ViewerError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def bounded_read(path):
    with path.open('rb') as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ViewerError(413, 'Artifact exceeds the viewer size limit.')
    return data


def contained(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ViewerError(403, 'Artifact path is outside the configured directory.')
    return path


class Store:
    def __init__(self, export, study):
        self.study = Path(study).resolve()
        raw = bounded_read(Path(export))
        self.export_sha256 = hashlib.sha256(raw).hexdigest()
        self.data = json.loads(raw)
        if self.data.get('schema') != 'heldout-report-v1':
            raise ValueError('Expected a heldout-report-v1 export')
        self.trials = {}
        self.categories = {t['task']: t['category'] for t in self.data['manifest']['design']['tasks']}
        for trial in self.data['trials']:
            slot = trial['attempt_id']
            if not HEX.fullmatch(slot) or slot in self.trials:
                raise ValueError('Invalid or duplicate trial ID')
            self.trials[slot] = trial

    def trial(self, slot):
        if not HEX.fullmatch(slot) or slot not in self.trials:
            raise ViewerError(404, 'Trial not found.')
        return self.trials[slot]

    def run_directory(self, trial):
        if trial['outcome'] != 'finished':
            return None
        parts = trial['result_path'].split('/')
        if (len(parts) != 4 or parts[0] != 'executions' or parts[3] != 'result.json'
                or not HEX.fullmatch(parts[1]) or not HEX.fullmatch(parts[2])
                or parts[1] != trial['execution_id'] or parts[2] != trial['result']['id']):
            raise ViewerError(409, 'Published artifact identity is inconsistent.')
        directory = contained(self.study, '/'.join(parts[:3]))
        path = contained(self.study, trial['result_path'])
        if not path.is_file():
            return None
        if hashlib.sha256(bounded_read(path)).hexdigest() != trial['result_sha256']:
            raise ViewerError(409, 'Local result does not match the published record.')
        return directory

    def artifact(self, directory, name):
        return contained(self.study, (directory / name).relative_to(self.study))

    def index(self):
        rows = []
        for index, trial in enumerate(self.trials.values()):
            result = trial.get('result', {})
            rows.append({k: trial[k] for k in ('attempt_id', 'execution_id', 'task', 'architecture', 'condition', 'repetition')} | {
                'order': index + 1, 'category': self.categories.get(trial['task'], ''),
                'run_id': result.get('id'), 'status': result.get('status', trial['outcome']),
                'verified': result.get('verified_completion', False),
                'fault_triggered': result.get('fault_triggered', False),
                'usage_complete': result.get('usage_complete', False),
                'seconds': result.get('seconds'), 'tokens': result.get('tokens'),
                'model_requests': result.get('model_requests'), 'error': result.get('error')})
        return {'schema': 'viewer-v1', 'summary': self.data['summary'], 'trials': rows,
                'source_commit': self.data['manifest']['source_commit'],
                'export_sha256': self.export_sha256,
                'model': self.data['manifest']['design']['configuration']['provider_expected']['model'],
                'local_artifacts_present': self.study.is_dir()}

    def detail(self, slot):
        trial = self.trial(slot)
        directory = self.run_directory(trial)
        issue = None
        available = {'events': False, 'patch': False}
        if directory:
            available = {key: self.artifact(directory, name).is_file()
                         for key, name in (('events', 'events.jsonl'), ('patch', 'patch.diff'))}
            manifest = self.artifact(directory, 'manifest.json')
            if manifest.is_file():
                local = json.loads(bounded_read(manifest))
                if any(local.get(k) != trial[k] for k in ('task', 'architecture', 'condition')):
                    raise ViewerError(409, 'Local manifest identity does not match the trial.')
                issue = local.get('issue')
        return {'trial': trial, 'issue': issue, 'available': available,
                'integrity': 'result_hash_matched' if directory else 'local_result_unavailable',
                'artifact_note': 'Trace and patch are local artifacts; their own hashes are not in the published export.'}

    def events(self, slot):
        directory = self.run_directory(self.trial(slot))
        if not directory or not self.artifact(directory, 'events.jsonl').is_file():
            raise ViewerError(404, 'Local trace is unavailable in this checkout.')
        events = []
        for index, line in enumerate(bounded_read(self.artifact(directory, 'events.jsonl')).splitlines()):
            event = json.loads(line)
            kind = event.get('kind')
            if kind not in EVENT_FIELDS:
                continue
            projected = {k: event[k] for k in EVENT_FIELDS[kind] if k in event}
            if kind == 'model':
                response = event.get('response', {})
                projected['response'] = {k: response[k] for k in ('text', 'actions', 'usage', 'model') if k in response}
            events.append({'index': index, 'time': event.get('time'), 'kind': kind, **projected})
        return {'events': events, 'projection': 'visible_model_tools_and_accounting_only'}

    def patch(self, slot):
        directory = self.run_directory(self.trial(slot))
        if not directory or not self.artifact(directory, 'patch.diff').is_file():
            raise ViewerError(404, 'Local patch is unavailable in this checkout.')
        return {'patch': bounded_read(self.artifact(directory, 'patch.diff')).decode('utf-8')}


def create_server(store, static, port=8765):
    static = Path(static).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, content_type='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else json.dumps(body, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def do_POST(self):
            self.send(405, {'error': 'This viewer supports read-only GET and HEAD requests.'})

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            origins = {f'http://{host}:{self.server.server_port}' for host in ('127.0.0.1', 'localhost')}
            hosts = {f'{host}:{self.server.server_port}' for host in ('127.0.0.1', 'localhost')}
            if self.headers.get('Host') not in hosts or self.headers.get('Origin', next(iter(origins))) not in origins:
                self.send(403, {'error': 'Only local same-origin requests are supported.'})
                return
            try:
                path = unquote(urlsplit(self.path).path)
                if '\\' in path or '\x00' in path or any(p in ('.', '..') for p in path.split('/')):
                    raise ViewerError(403, 'Invalid path.')
                if path == '/api/study':
                    self.send(200, store.index())
                elif path == '/api/manifest':
                    self.send(200, store.data['manifest'])
                elif path.startswith('/api/trials/'):
                    segments = path.strip('/').split('/')
                    if len(segments) == 3:
                        self.send(200, store.detail(segments[2]))
                    elif len(segments) == 4 and segments[3] in ('events', 'patch'):
                        self.send(200, getattr(store, segments[3])(segments[2]))
                    else:
                        raise ViewerError(404, 'Endpoint not found.')
                elif path.startswith('/api/'):
                    raise ViewerError(404, 'Endpoint not found.')
                else:
                    relative = path.lstrip('/') or 'index.html'
                    file = contained(static, relative)
                    if file.is_dir():
                        file = contained(static, relative + '/index.html')
                    if not file.is_file() or file.suffix not in ('.html', '.js', '.css', '.json', '.ico', '.png', '.svg', '.woff', '.woff2'):
                        raise ViewerError(404, 'Viewer page not found. Build the frontend first.')
                    content_type = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
                    if file.suffix == '.js':
                        content_type = 'text/javascript'
                    self.send(200, bounded_read(file), content_type)
            except ViewerError as error:
                self.send(error.status, {'error': error.message})
            except (OSError, ValueError, KeyError, TypeError):
                self.send(409, {'error': 'Artifact could not be read or validated.'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, default=ROOT/'docs/studies/heldout-v1-results.json')
    parser.add_argument('--study-directory', type=Path, default=ROOT/'runs/heldout-v1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not (ROOT/'viewer/out/index.html').is_file():
        parser.error('Build the frontend first: cd viewer; npm ci; npm run build')
    server = create_server(Store(args.export, args.study_directory), ROOT/'viewer/out', args.port)
    print(f'Agent Reliability Lab: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
