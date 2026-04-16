from __future__ import annotations

from .config import settings
from .db import Database, TERMINAL_TASK_STATUSES
from .llm import LLMClient


class Orchestrator:
    def __init__(self, db: Database, llm: LLMClient):
        self.db = db
        self.llm = llm

    def submit_run(self, user_input: str) -> str:
        normalized = user_input.strip()
        if normalized.startswith("/pm"):
            normalized = normalized[3:].strip()
        run_id = self.db.create_run(user_input=user_input.strip(), root_command="/pm")
        self.db.create_task(
            run_id=run_id,
            parent_task_id=None,
            agent_key="pm",
            title="PM root request",
            input_text=normalized or "Empty /pm request",
        )
        return run_id

    def process_next_task(self) -> bool:
        task = self.db.claim_next_queued_task()
        if task is None:
            return False
        self.process_task(task)
        return True

    def process_task(self, task: dict) -> None:
        session = self.db.get_or_create_agent_session(task["agent_key"])
        self.db.create_agent_message(
            run_id=task["run_id"],
            task_id=task["id"],
            agent_key=task["agent_key"],
            session_id=session["id"],
            direction="input",
            content=task["input_text"],
        )
        try:
            raw_output, structured_output = self.llm.generate(
                agent_key=task["agent_key"],
                input_text=task["input_text"],
                memory_summary=session["memory_summary"],
            )
            self.db.create_agent_message(
                run_id=task["run_id"],
                task_id=task["id"],
                agent_key=task["agent_key"],
                session_id=session["id"],
                direction="output",
                content=raw_output,
            )
            action = structured_output.get("action", "final")
            if action == "delegate":
                self._handle_delegate(task, raw_output, structured_output)
            elif action == "ask_user":
                self._handle_ask_user(task, raw_output, structured_output)
            else:
                self._handle_final(task, raw_output, structured_output)
        except Exception as exc:  # pragma: no cover - starter service fallback path
            self.db.mark_task_failed(task["id"], f"Task failed: {exc}")
            self.db.create_event(task["run_id"], task["id"], "error", "task_failed", str(exc))
            if task["parent_task_id"]:
                self._resume_parent_if_ready(task["parent_task_id"])

    def _handle_delegate(self, task: dict, raw_output: str, structured_output: dict) -> None:
        children = structured_output.get("children", [])
        self.db.set_task_waiting(task["id"], raw_output, structured_output)
        self.db.create_event(task["run_id"], task["id"], "info", "delegated", f"{task['agent_key']} delegated to {len(children)} child task(s).")
        for child in children:
            self.db.create_task(
                run_id=task["run_id"],
                parent_task_id=task["id"],
                agent_key=child["agent"],
                title=child.get("title", child["agent"]),
                input_text=child["input"],
            )
        self._update_memory(task["agent_key"], structured_output.get("summary", raw_output))

    def _handle_ask_user(self, task: dict, raw_output: str, structured_output: dict) -> None:
        self.db.mark_task_blocked(task["id"], raw_output, structured_output)
        question = structured_output.get("question", "Agent is blocked and needs user input.")
        self.db.set_run_blocked(task["run_id"], question)
        self.db.create_event(task["run_id"], task["id"], "warning", "blocked", question)
        self._update_memory(task["agent_key"], question)

    def _handle_final(self, task: dict, raw_output: str, structured_output: dict) -> None:
        self.db.mark_task_done(task["id"], raw_output, structured_output)
        message = structured_output.get("message", raw_output)
        self.db.create_event(task["run_id"], task["id"], "info", "task_done", f"{task['agent_key']} completed its task.")
        self._update_memory(task["agent_key"], message)
        if task["agent_key"] == "pm" and task["parent_task_id"] is None:
            self.db.finalize_run(task["run_id"], message)
            return
        if task["parent_task_id"]:
            self._resume_parent_if_ready(task["parent_task_id"])

    def _resume_parent_if_ready(self, parent_task_id: str) -> None:
        parent = self.db.get_task(parent_task_id)
        if parent is None or parent["status"] != "waiting_for_children":
            return
        children = self.db.get_children(parent_task_id)
        if not children or any(child["status"] not in TERMINAL_TASK_STATUSES for child in children):
            return
        synthesis_prompt = self._build_synthesis_prompt(parent, children)
        self.db.prepare_task_resume(parent_task_id, synthesis_prompt)
        self.db.create_event(parent["run_id"], parent_task_id, "info", "resume_parent", f"Resuming {parent['agent_key']} after all child tasks completed.")

    def _build_synthesis_prompt(self, parent: dict, children: list[dict]) -> str:
        child_sections = []
        for child in children:
            child_sections.append(
                f"Agent: {child['agent_key']}\nTitle: {child['title']}\nOutput:\n{child.get('raw_output') or ''}"
            )
        combined = "\n\n".join(child_sections) if child_sections else "No child outputs."
        return (
            "SYNTHESIZE\n"
            f"Agent: {parent['agent_key']}\n"
            f"Original request:\n{parent['original_input_text']}\n\n"
            f"Child outputs:\n{combined}"
        )

    def _update_memory(self, agent_key: str, text: str) -> None:
        summary = text.strip()
        if len(summary) > settings.max_memory_summary_chars:
            summary = summary[: settings.max_memory_summary_chars - 3] + "..."
        self.db.update_agent_session_memory(agent_key, summary)

    def answer_blocked_run(self, run_id: str, answer: str) -> None:
        run = self.db.get_run(run_id)
        if run is None:
            raise ValueError("Run not found")
        if run["status"] != "blocked_on_user":
            raise ValueError("Run is not blocked on user input")
        blocked_tasks = [
            task for task in self.db.get_tasks_for_run(run_id)
            if task["status"] == "blocked_on_user"
        ]
        if not blocked_tasks:
            raise ValueError("No blocked task found for run")
        task = blocked_tasks[-1]
        resumed_input = (
            f"{task['original_input_text']}\n\n"
            "USER_RESPONSE\n"
            f"{answer.strip()}"
        )
        self.db.prepare_task_resume(task["id"], resumed_input)
        self.db.clear_run_blocked(run_id)
        self.db.create_event(run_id, task["id"], "info", "user_answered", "User answered the blocked PM question.")

    def build_graph_rows(self, run_id: str) -> list[dict]:
        tasks = self.db.get_tasks_for_run(run_id)
        task_by_id = {task["id"]: task for task in tasks}
        rows: list[dict] = []
        for task in tasks:
            parent = task_by_id.get(task["parent_task_id"]) if task["parent_task_id"] else None
            rows.append(
                {
                    "id": task["id"],
                    "agent_key": task["agent_key"],
                    "title": task["title"],
                    "status": task["status"],
                    "parent_task_id": task["parent_task_id"],
                    "parent_agent_key": parent["agent_key"] if parent else None,
                }
            )
        return rows
