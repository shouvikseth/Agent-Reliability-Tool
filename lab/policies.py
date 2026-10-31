"""Versioned shared execution and deterministic context policies."""
import hashlib
import json

EXECUTION_POLICY = 'bounded-actions-v3/logs-v2'
CONTEXT_POLICY = 'visible-history-v1'
MAX_ACTIONS = 6


def visible_history(history):
    """Keep all actions and statuses; shorten commentary and duplicate file data.

    Full originals remain in the append-only trace. Never summarize candidate
    source/patch text with a model, and never change the caller's history.
    """
    visible = []
    seen = set()
    for item in reversed(history):
        if 'response' in item:
            response = item['response']
            visible.append({'role': item['role'], 'text': response['text'][:160], 'actions': response['actions']})
        else:
            entry = dict(item)
            value = entry.get('result')
            if entry.get('tool') in {'read', 'logs'} and isinstance(value, str):
                digest = hashlib.sha256(value.encode()).hexdigest()
                if digest in seen:
                    entry['result'] = {'duplicate_content_sha256': digest, 'note': 'Full content occurs later in this history'}
                seen.add(digest)
            if entry.get('tool') == 'test' and isinstance(value, dict) and isinstance(value.get('output'), str):
                entry['result'] = {**value, 'output': value['output'][-2000:]}
            visible.append(entry)
    return list(reversed(visible))


def history_size(history):
    return len(json.dumps(history, ensure_ascii=False, separators=(',', ':')).encode())
