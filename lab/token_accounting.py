"""Offline Qwen chat token-count diagnostic; not the active admission policy."""
import argparse
import hashlib
import json
from pathlib import Path

TOKENIZER_SHA256 = 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539'
TOKENIZER_REVISION = 'c03e6d358207e414f1eca0bb1891e29f1db0e242'
MODEL_DIGEST = 'dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364'
TEMPLATE_SHA256 = '1e65450c30670713aa47fe23e8b9662bdf4065e81cc8e3cbfaa98924fcc0d320'


class QwenCounter:
    def __init__(self, path):
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != TOKENIZER_SHA256:
            raise ValueError('Tokenizer differs from the validated pinned file')
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_str(data.decode('utf-8'))

    def count(self, messages):
        rendered = render_qwen(messages)
        if not rendered.isascii():
            raise ValueError('Non-ASCII tokenization is not validated against Ollama; use byte admission')
        return len(self.tokenizer.encode(rendered, add_special_tokens=False).ids)

    def verify(self, digest, template):
        if digest != MODEL_DIGEST or hashlib.sha256(template.encode()).hexdigest() != TEMPLATE_SHA256:
            raise ValueError('Installed model/template differs from validated tokenizer configuration')

    def metadata(self):
        return {'tokenizer_sha256': TOKENIZER_SHA256, 'tokenizer_revision': TOKENIZER_REVISION,
                'template_sha256': TEMPLATE_SHA256, 'safety_margin_tokens': 64}


def render_qwen(messages):
    """Validated for our system+user, no-tools Qwen2.5 Coder 7B template only."""
    if [message.get('role') for message in messages] != ['system', 'user']:
        raise ValueError('Diagnostic supports exactly one system and one user message')
    return ''.join('<|im_start|>'+message['role']+'\n'+message['content']+'<|im_end|>\n'
                   for message in messages) + '<|im_start|>assistant\n'


def count_qwen(messages, tokenizer_file):
    data = Path(tokenizer_file).read_bytes()
    if hashlib.sha256(data).hexdigest() != TOKENIZER_SHA256:
        raise ValueError('Tokenizer differs from the validated pinned file')
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_str(data.decode('utf-8'))
    return len(tokenizer.encode(render_qwen(messages), add_special_tokens=False).ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--tokenizer-file', type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.request.read_text(encoding='utf-8'))
    if payload.get('model') != 'qwen2.5-coder:7b' or payload.get('tools'):
        parser.error('Only the validated local Qwen 7B no-tools request layout is supported')
    print(json.dumps({'input_tokens': count_qwen(payload['messages'], args.tokenizer_file),
                      'tokenizer_sha256': TOKENIZER_SHA256, 'scope': 'diagnostic_only'}))


if __name__ == '__main__':
    main()
