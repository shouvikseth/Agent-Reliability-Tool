import sqlite3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


class IssueInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def create_app(database: str = ":memory:") -> FastAPI:
    app = FastAPI(title="Reliability Lab issue tracker")
    db = sqlite3.connect(database, check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS issues (id INTEGER PRIMARY KEY, title TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'open')")
    db.execute("CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, title TEXT NOT NULL, issue_id INTEGER NOT NULL)")
    app.state.db = db

    @app.post("/issues", status_code=201)
    def create_issue(body: IssueInput, request_key: str | None = None):
        title = body.title.strip()
        if not title:
            raise HTTPException(422, "Title cannot be blank")
        with db:
            if request_key is not None:
                prior = db.execute("SELECT title, issue_id FROM requests WHERE key = ?", (request_key,)).fetchone()
                if prior:
                    if prior[0] != title:
                        raise HTTPException(409, "Request key reused with different input")
                    return {"id": prior[1], "title": title}
            cursor = db.execute("INSERT INTO issues(title) VALUES (?)", (title,))
            issue_id = cursor.lastrowid
            if request_key is not None:
                db.execute("INSERT INTO requests VALUES (?, ?, ?)", (request_key, title, issue_id))
        return {"id": issue_id, "title": title}

    @app.get("/issues")
    def list_issues(offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100), state: str | None = None):
        if state is not None and state not in {"open", "closed"}:
            raise HTTPException(422, "Invalid state")
        rows = db.execute("SELECT id, title, state FROM issues WHERE (? IS NULL OR state = ?) ORDER BY id LIMIT ? OFFSET ?", (state, state, limit, offset)).fetchall()
        return [{"id": row[0], "title": row[1], "state": row[2]} for row in rows]

    @app.post("/issues/{issue_id}/close")
    def close_issue(issue_id: int):
        with db:
            row = db.execute("SELECT state FROM issues WHERE id = ?", (issue_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Issue not found")
            if row[0] == "closed":
                raise HTTPException(409, "Issue already closed")
            db.execute("UPDATE issues SET state = 'closed' WHERE id = ?", (issue_id,))
        return {"id": issue_id, "state": "closed"}

    return app
