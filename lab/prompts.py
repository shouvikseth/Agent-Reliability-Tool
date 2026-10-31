"""Versioned shared completion rules for every provider and architecture."""
COMPLETION_VERSION = 'completion-v5'
COMPLETION_RULES = '''Completion rules:
Actions are optional. Never repeat an action just to fill the array.
Return at most six actions per response. Every requested tool call counts,
including cached results. Passing tests on unchanged source may return cached results.
Do not rerun a passed test unless you made another edit or have new evidence.
The logs tool returns schema logs-v2: ok:true with content, or ok:false with
an error code and retryable flag. An invalid_log_response is a
response-decoding error, not application evidence. Retry logs if needed.
'''


def completion_for(role):
    rules = {
        'agent': '''You control the repair loop. Read the source, edit, test, then submit.
When finished, request the submit tool with all argument fields null.
Example final response: {"text":"Ready to grade.","actions":[{"name":"submit","arguments":{"path":null,"old":null,"new":null}}]}.
An empty action list does not finish your run. Submit explicitly when ready.
''',
        'revision': '''This is the final revision stage. You have one response.
If the patch needs no further edits or tests, return exactly
{"text":"No further changes needed.","actions":[]}.
Otherwise return only the necessary edits and, if appropriate, one test.
The orchestrator submits after this stage. Do not request submit.
''',
        'inspect': 'Read app.py now. The next stage will make the patch. Do not edit or submit.\n',
        'planner': 'Read app.py and propose an approach. The writer acts next. Do not edit or submit.\n',
        'patch': 'Make the necessary patch. The orchestrator tests it next. Do not submit.\n',
        'writer': 'Make the necessary patch; test if useful. A reviewer acts next. Do not submit.\n',
        'reviewer': 'Review the patch using visible history and tools. Test if needed. Do not repeat a passed test. A final revision stage follows.\n',
    }
    if role not in rules:
        raise ValueError('Unknown model stage: ' + role)
    return COMPLETION_RULES + rules[role]
