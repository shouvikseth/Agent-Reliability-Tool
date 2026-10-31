"""Versioned log response boundary and recoverable protocol errors."""
import json

LOG_CONTRACT = 'logs-v2'


def log_response(wire):
    try:
        value = json.loads(wire)
        if not isinstance(value, dict) or set(value) != {'schema', 'ok', 'content'}:
            raise ValueError()
        if value['schema'] != LOG_CONTRACT or value['ok'] is not True or not isinstance(value['content'], str):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        return {'schema': LOG_CONTRACT, 'ok': False,
                'error': {'code': 'invalid_log_response', 'retryable': True,
                          'message': 'Log response could not be decoded or validated. Retry logs within budget.'}}


def encode_log(content):
    return json.dumps({'schema': LOG_CONTRACT, 'ok': True, 'content': content})
