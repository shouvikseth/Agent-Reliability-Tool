"""Versioned shared completion rules for every provider and architecture."""
COMPLETION_VERSION = 'completion-v2'
COMPLETION_RULES = '''Completion rules:
Actions are optional. Never repeat an action just to fill the array.
If revision has no further edits or tests to perform, return exactly
{"text":"No further changes needed.","actions":[]}.
Do not rerun a passed test unless you made another edit or have new evidence.
For fixed/team, the orchestrator submits after revision; do not request submit.
For single agent, request submit when the patch is ready.
'''
