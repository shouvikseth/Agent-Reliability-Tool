"""Author-only task construction. Never mount this module in a task container."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    split: str
    issue: str
    good: str
    bad: str
    check: str
    logs: str = 'Synthetic issue tracker development log. See issue description for reproduction.\n'


TASKS = [
    Task("pagination-final", "pagination", "development", "Listing a page skips its final issue. Return every requested row.", "for row in rows]", "for row in rows[:-1]]", "assert len(client.get('/issues?limit=3').json()) == 3"),
    Task("pagination-offset", "pagination", "development", "A nonzero offset starts one record too late.", "(state, state, limit, offset)", "(state, state, limit, offset + 1)", "assert client.get('/issues?offset=1&limit=1').json()[0]['id'] == 2"),
    Task("blank-title", "validation", "development", "Whitespace-only titles must be rejected with status 422.", "if not title:", "if title is None:", "assert client.post('/issues', json={'title': '   '}).status_code == 422"),
    Task("missing-issue", "transitions", "development", "Closing an unknown issue must return 404.", "raise HTTPException(404, \"Issue not found\")", "raise HTTPException(400, \"Issue not found\")", "assert client.post('/issues/999/close').status_code == 404"),
    Task("repeat-close", "transitions", "development", "Closing an already closed issue must return 409.", "if row[0] == \"closed\":", "if row[0] == \"never\":", "client.post('/issues/1/close'); assert client.post('/issues/1/close').status_code == 409"),
    Task("request-replay", "duplicates", "development", "Replaying the same request key must return the original issue.", "if prior:", "if False and prior:", "a=client.post('/issues?request_key=x', json={'title':'same'}); b=client.post('/issues?request_key=x', json={'title':'same'}); assert a.json() == b.json()"),
    Task("request-conflict", "duplicates", "development", "Reusing a key for different input must return 409.", "if prior[0] != title:", "if False:", "client.post('/issues?request_key=x', json={'title':'one'}); assert client.post('/issues?request_key=x', json={'title':'two'}).status_code == 409"),
    Task("filter-state", "filtering", "development", "Filtering for closed issues must exclude open issues.", "(state, state, limit, offset)", "(None, state, limit, offset)", "client.post('/issues/1/close'); assert len(client.get('/issues?state=closed').json()) == 1"),
    Task('log-limit-zero', 'validation', 'development',
         'A pagination validation incident was reported. Read the supplied diagnostic logs using the logs tool to identify the failing request and expected API behavior, then repair it.',
         'limit: int = Query(10, ge=1, le=100)', 'limit: int = Query(10, ge=0, le=100)',
         "assert client.get('/issues?limit=0').status_code == 422; assert client.get('/issues?limit=1').status_code == 200",
         'Synthetic client incident: GET /issues?limit=0 returned HTTP 200. API contract: limit must be an integer from 1 through 100; invalid limit must return 422. Control: GET /issues?limit=1 returned 200.\n'),
    Task('log-title-length', 'validation', 'development',
         'A client cannot create a valid issue after a validation change. Read the supplied diagnostic logs using the logs tool for the request boundary and API contract, then repair the defect.',
         'max_length=200', 'max_length=20',
         "assert client.post('/issues', json={'title':'x'*21}).status_code == 201; assert client.post('/issues', json={'title':'x'*200}).status_code == 201; assert client.post('/issues', json={'title':'x'*201}).status_code == 422",
         'Synthetic client incident: POST /issues with a nonblank 21-character title returned HTTP 422. API contract permits titles of 1 through 200 characters; a valid creation returns 201. A 201-character title must return 422.\n'),
]

REGRESSION = '''from fastapi.testclient import TestClient
from app import create_app

def test_regression():
    with TestClient(create_app()) as client:
        assert client.get('/issues').json() == []
        assert client.post('/issues', json={'title':'hello'}).status_code == 201
        assert client.post('/issues', json={}).status_code == 422
        assert client.post('/issues/1/close').status_code == 200
'''


def verifier(task: Task) -> str:
    return '''from fastapi.testclient import TestClient
from app import create_app

def test_defect():
    with TestClient(create_app()) as client:
        for title in ['a', 'b', 'c']:
            client.post('/issues', json={'title':title})
        ''' + task.check + '\n'


def seed(task: Task, workspace: Path):
    source = (Path(__file__).resolve().parent.parent / "target_app" / "app.py").read_text()
    if source.count(task.good) != 1:
        raise ValueError(f"Seed anchor must be unique: {task.id}")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "app.py").write_text(source.replace(task.good, task.bad))
    (workspace / "test_public.py").write_text(REGRESSION)
    (workspace / "logs.txt").write_text(task.logs)
