import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agents import AGENT_REGISTRY


TERMINAL_TASK_STATUSES = {"done", "failed", "cancelled"}


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = str(path)
        self._lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS agents (
                    agent_key TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    system_prompt TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    agent_key TEXT NOT NULL UNIQUE,
                    memory_summary TEXT NOT NULL DEFAULT '',
                    last_used_at TEXT NOT NULL,
                    FOREIGN KEY(agent_key) REFERENCES agents(agent_key)
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    root_command TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_output TEXT,
                    blocked_question TEXT,
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    parent_task_id TEXT,
                    agent_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    original_input_text TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    raw_output TEXT,
                    structured_output_json TEXT,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(parent_task_id) REFERENCES tasks(id),
                    FOREIGN KEY(agent_key) REFERENCES agents(agent_key)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT,
                    level TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    agent_key TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id),
                    FOREIGN KEY(agent_key) REFERENCES agents(agent_key),
                    FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_run_created ON tasks(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_events_run_created ON events(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_agent_messages_run_created ON agent_messages(run_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_agent_messages_task_created ON agent_messages(task_id, created_at);
                """
            )
            for agent in AGENT_REGISTRY.values():
                connection.execute(
                    """
                    INSERT INTO agents(agent_key, display_name, system_prompt)
                    VALUES(?, ?, ?)
                    ON CONFLICT(agent_key) DO UPDATE SET
                        display_name = excluded.display_name,
                        system_prompt = excluded.system_prompt
                    """,
                    (agent.key, agent.display_name, agent.system_prompt),
                )
            connection.commit()

    def _new_id(self) -> str:
        return uuid.uuid4().hex

    def create_run(self, user_input: str, root_command: str = "/pm") -> str:
        run_id = self._new_id()
        created_at = utcnow()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(id, root_command, user_input, status, created_at) VALUES(?, ?, ?, ?, ?)",
                (run_id, root_command, user_input, "queued", created_at),
            )
            connection.commit()
        self.create_event(run_id, None, "info", "run_created", f"Created run for {root_command} request.")
        return run_id

    def create_task(self, run_id: str, parent_task_id: str | None, agent_key: str, title: str, input_text: str) -> str:
        task_id = self._new_id()
        created_at = utcnow()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks(id, run_id, parent_task_id, agent_key, title, status, original_input_text, input_text, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, run_id, parent_task_id, agent_key, title, "queued", input_text, input_text, created_at),
            )
            connection.commit()
        self.create_event(run_id, task_id, "info", "task_created", f"Queued {agent_key} task: {title}")
        return task_id

    def create_event(self, run_id: str, task_id: str | None, level: str, kind: str, message: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events(id, run_id, task_id, level, kind, message, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (self._new_id(), run_id, task_id, level, kind, message, utcnow()),
            )
            connection.commit()

    def list_runs(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._task_row_to_dict(row)

    def get_tasks_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at ASC", (run_id,)).fetchall()
        return [task for row in rows if (task := self._task_row_to_dict(row)) is not None]

    def get_tasks_for_run_grouped(self, run_id: str) -> list[dict[str, Any]]:
        tasks = self.get_tasks_for_run(run_id)
        by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for task in tasks:
            by_parent.setdefault(task["parent_task_id"], []).append(task)
        for task in tasks:
            task["children"] = by_parent.get(task["id"], [])
        return by_parent.get(None, [])

    def get_children(self, task_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY created_at ASC", (task_id,)).fetchall()
        return [task for row in rows if (task := self._task_row_to_dict(row)) is not None]

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM events WHERE run_id = ? ORDER BY created_at DESC", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_agent_message(
        self,
        run_id: str,
        task_id: str,
        agent_key: str,
        session_id: str,
        direction: str,
        content: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO agent_messages(id, run_id, task_id, agent_key, session_id, direction, content, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (self._new_id(), run_id, task_id, agent_key, session_id, direction, content, utcnow()),
            )
            connection.commit()

    def list_agent_messages_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_messages WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_next_queued_task(self) -> dict[str, Any] | None:
        with self._lock:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
                if row is None:
                    return None
                connection.execute(
                    "UPDATE tasks SET status = ? WHERE id = ?",
                    ("running", row["id"]),
                )
                connection.execute(
                    "UPDATE runs SET status = ? WHERE id = ? AND status != 'done'",
                    ("running", row["run_id"]),
                )
                connection.commit()
        return self.get_task(row["id"])

    def set_task_waiting(self, task_id: str, raw_output: str, structured_output: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, raw_output = ?, structured_output_json = ? WHERE id = ?",
                ("waiting_for_children", raw_output, json.dumps(structured_output), task_id),
            )
            connection.commit()

    def mark_task_done(self, task_id: str, raw_output: str, structured_output: dict[str, Any]) -> None:
        finished_at = utcnow()
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, raw_output = ?, structured_output_json = ?, finished_at = ? WHERE id = ?",
                ("done", raw_output, json.dumps(structured_output), finished_at, task_id),
            )
            connection.commit()

    def mark_task_failed(self, task_id: str, message: str) -> None:
        finished_at = utcnow()
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, raw_output = ?, finished_at = ? WHERE id = ?",
                ("failed", message, finished_at, task_id),
            )
            connection.commit()

    def mark_task_blocked(self, task_id: str, raw_output: str, structured_output: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, raw_output = ?, structured_output_json = ? WHERE id = ?",
                ("blocked_on_user", raw_output, json.dumps(structured_output), task_id),
            )
            connection.commit()

    def prepare_task_resume(self, task_id: str, input_text: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, input_text = ? WHERE id = ?",
                ("queued", input_text, task_id),
            )
            connection.commit()

    def retry_task(self, task_id: str) -> str:
        task = self.get_task(task_id)
        if task is None:
            raise ValueError("Task not found")
        if task["status"] not in {"failed", "done", "blocked_on_user"}:
            raise ValueError("Only failed, done, or blocked tasks can be retried")
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, input_text = original_input_text, raw_output = NULL, structured_output_json = NULL, finished_at = NULL WHERE id = ?",
                ("queued", task_id),
            )
            parent_task_id = task["parent_task_id"]
            while parent_task_id is not None:
                connection.execute(
                    "UPDATE tasks SET status = ?, raw_output = NULL, structured_output_json = NULL, finished_at = NULL WHERE id = ?",
                    ("waiting_for_children", parent_task_id),
                )
                parent_row = connection.execute(
                    "SELECT parent_task_id FROM tasks WHERE id = ?",
                    (parent_task_id,),
                ).fetchone()
                parent_task_id = parent_row["parent_task_id"] if parent_row is not None else None
            connection.execute(
                "UPDATE runs SET status = ?, final_output = NULL, blocked_question = NULL, finished_at = NULL WHERE id = ?",
                ("running", task["run_id"]),
            )
            connection.commit()
        self.create_event(task["run_id"], task_id, "info", "task_retried", f"Retried task {task_id}.")
        return task["run_id"]

    def finalize_run(self, run_id: str, final_output: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, final_output = ?, blocked_question = NULL, finished_at = ? WHERE id = ?",
                ("done", final_output, utcnow(), run_id),
            )
            connection.commit()

    def set_run_blocked(self, run_id: str, question: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, blocked_question = ? WHERE id = ?",
                ("blocked_on_user", question, run_id),
            )
            connection.commit()

    def clear_run_blocked(self, run_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, blocked_question = NULL WHERE id = ?",
                ("running", run_id),
            )
            connection.commit()

    def get_or_create_agent_session(self, agent_key: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM agent_sessions WHERE agent_key = ?", (agent_key,)).fetchone()
            if row is None:
                session_id = self._new_id()
                connection.execute(
                    "INSERT INTO agent_sessions(id, agent_key, memory_summary, last_used_at) VALUES(?, ?, ?, ?)",
                    (session_id, agent_key, "", utcnow()),
                )
                connection.commit()
                row = connection.execute("SELECT * FROM agent_sessions WHERE agent_key = ?", (agent_key,)).fetchone()
        return dict(row)

    def update_agent_session_memory(self, agent_key: str, memory_summary: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE agent_sessions SET memory_summary = ?, last_used_at = ? WHERE agent_key = ?",
                (memory_summary, utcnow(), agent_key),
            )
            connection.commit()

    def _task_row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        task = dict(row)
        if task["structured_output_json"]:
            task["structured_output"] = json.loads(task["structured_output_json"])
        else:
            task["structured_output"] = None
        return task
