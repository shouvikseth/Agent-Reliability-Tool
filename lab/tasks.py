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


TASKS = [
    Task("pagination-final", "pagination", "development", "Listing a page skips its final issue. Return every requested row.", "for row in rows]", "for row in rows[:-1]]", "assert len(client.get('/issues?limit=3').json()) == 3"),
    Task("pagination-offset", "pagination", "development", "A nonzero offset starts one record too late.", "(state, state, limit, offset)", "(state, state, limit, offset + 1)", "assert client.get('/issues?offset=1&limit=1').json()[0]['id'] == 2"),
    Task("blank-title", "validation", "development", "Whitespace-only titles must be rejected with status 422.", "if not title:", "if title is None:", "assert client.post('/issues', json={'title': '   '}).status_code == 422"),
    Task("missing-issue", "transitions", "development", "Closing an unknown issue must return 404.", "raise HTTPException(404, \"Issue not found\")", "raise HTTPException(400, \"Issue not found\")", "assert client.post('/issues/999/close').status_code == 404"),
    Task("repeat-close", "transitions", "development", "Closing an already closed issue must return 409.", "if row[0] == \"closed\":", "if row[0] == \"never\":", "client.post('/issues/1/close'); assert client.post('/issues/1/close').status_code == 409"),
    Task("request-replay", "duplicates", "development", "Replaying the same request key must return the original issue.", "if prior:", "if False and prior:", "a=client.post('/issues?request_key=x', json={'title':'same'}); b=client.post('/issues?request_key=x', json={'title':'same'}); assert a.json() == b.json()"),
    Task("request-conflict", "duplicates", "development", "Reusing a key for different input must return 409.", "if prior[0] != title:", "if False:", "client.post('/issues?request_key=x', json={'title':'one'}); assert client.post('/issues?request_key=x', json={'title':'two'}).status_code == 409"),
    Task("filter-state", "filtering", "development", "Filtering for closed issues must exclude open issues.", "(state, state, limit, offset)", "(None, state, limit, offset)", "client.post('/issues/1/close'); assert len(client.get('/issues?state=closed').json()) == 1"),
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
    (workspace / "logs.txt").write_text("Synthetic issue tracker development log. See issue description for reproduction.\n")
