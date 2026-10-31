"""Replay an exact captured request locally; diagnostic only, never benchmark grading."""
import argparse
import hashlib
import json
from pathlib import Path
import httpx
from lab.request_capture import safe_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 5 or args.output.exists():
        parser.error('Use 1–5 repetitions and a new output file')
    data = args.request.read_bytes()
    payload = json.loads(data)
    if payload.get('model') != 'qwen2.5-coder:7b' or payload.get('stream') is not False:
        parser.error('Only local Qwen 7B nonstreaming captured requests are supported')
    with httpx.Client(base_url='http://127.0.0.1:11434', trust_env=False, timeout=90) as client:
        version = client.get('/api/version').json()
        for index in range(args.repetitions):
            response = client.post('/api/chat', content=data, headers={'Content-Type': 'application/json'})
            row = {'scope': 'diagnostic_only', 'attempt': index+1, 'request_sha256': hashlib.sha256(data).hexdigest(),
                   'server_version': version.get('version'), **safe_error(response)}
            if response.is_success:
                result = response.json()
                row.update(input_tokens=result.get('prompt_eval_count'), output_tokens=result.get('eval_count'), done_reason=result.get('done_reason'))
            with args.output.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
