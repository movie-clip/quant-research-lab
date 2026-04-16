from pathlib import Path

from app.db import Database
from app.llm import FakeLLMClient, OpenAIResponsesClient, validate_agent_output
from app.orchestrator import Orchestrator


def build_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.init()
    return db


def drain(orchestrator: Orchestrator) -> None:
    while orchestrator.process_next_task():
        pass


def test_validate_agent_output_rejects_invalid_delegate_shape() -> None:
    try:
        validate_agent_output({"action": "delegate", "summary": "x", "children": []})
    except ValueError as exc:
        assert "at least one child task" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected delegate validation failure")


def test_pm_delegate_flow_completes_run(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=FakeLLMClient())

    run_id = orchestrator.submit_run("/pm Design a ranking backend plan")
    drain(orchestrator)

    run = db.get_run(run_id)
    assert run is not None
    assert run["status"] == "done"
    assert run["final_output"] is not None
    assert "PM synthesis complete" in run["final_output"]


def test_blocked_run_can_resume_after_user_answer(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=FakeLLMClient())

    run_id = orchestrator.submit_run("/pm We need key for the provider")
    drain(orchestrator)

    blocked_run = db.get_run(run_id)
    assert blocked_run is not None
    assert blocked_run["status"] == "blocked_on_user"
    assert blocked_run["blocked_question"]

    orchestrator.answer_blocked_run(run_id, "Here is the required key")
    drain(orchestrator)

    completed_run = db.get_run(run_id)
    assert completed_run is not None
    assert completed_run["status"] == "done"
    assert completed_run["blocked_question"] is None


def test_failed_child_still_allows_parent_resume(tmp_path: Path) -> None:
    class BrokenClient(FakeLLMClient):
        def generate(self, agent_key: str, input_text: str, memory_summary: str):
            if agent_key == "quant_platform_engineer":
                raise RuntimeError("boom")
            return super().generate(agent_key, input_text, memory_summary)

    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=BrokenClient())

    run_id = orchestrator.submit_run("/pm Design a portfolio ranking backend")
    drain(orchestrator)

    run = db.get_run(run_id)
    tasks = db.get_tasks_for_run(run_id)
    assert run is not None
    assert run["status"] == "done"
    assert any(task["status"] == "failed" for task in tasks)
    assert run["final_output"] is not None


def test_retry_task_requeues_and_completes_run(tmp_path: Path) -> None:
    class BrokenOnceClient(FakeLLMClient):
        def __init__(self) -> None:
            self.failed = False

        def generate(self, agent_key: str, input_text: str, memory_summary: str):
            if agent_key == "producer" and not self.failed:
                self.failed = True
                raise RuntimeError("temporary failure")
            return super().generate(agent_key, input_text, memory_summary)

    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=BrokenOnceClient())

    run_id = orchestrator.submit_run("/pm Design a ranking backend plan")
    drain(orchestrator)

    failed_task = next(task for task in db.get_tasks_for_run(run_id) if task["status"] == "failed")
    retried_run_id = db.retry_task(failed_task["id"])
    assert retried_run_id == run_id

    drain(orchestrator)

    run = db.get_run(run_id)
    assert run is not None
    assert run["status"] == "done"


def test_agent_messages_are_persisted_for_inputs_and_outputs(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=FakeLLMClient())

    run_id = orchestrator.submit_run("/pm Design a backend ranking plan")
    drain(orchestrator)

    messages = db.list_agent_messages_for_run(run_id)
    assert messages
    directions = {message["direction"] for message in messages}
    assert "input" in directions
    assert "output" in directions
    assert any(message["agent_key"] == "pm" for message in messages)


def test_graph_rows_include_parent_relationships(tmp_path: Path) -> None:
    db = build_db(tmp_path)
    orchestrator = Orchestrator(db=db, llm=FakeLLMClient())

    run_id = orchestrator.submit_run("/pm Design a backend ranking plan")
    drain(orchestrator)

    graph_rows = orchestrator.build_graph_rows(run_id)
    assert graph_rows
    assert any(row["parent_agent_key"] == "pm" for row in graph_rows if row["parent_task_id"])


def test_openai_client_parses_mocked_provider_response(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "output_text": '{"action":"final","message":"done"}'
            }

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            assert url.endswith("/responses")
            assert json["model"] == "gpt-4.1"
            assert json["input"][1]["content"] == "hello"
            return FakeResponse()

    monkeypatch.setattr("app.llm.httpx.Client", FakeClient)
    client = OpenAIResponsesClient(
        api_key="test-key",
        api_base="https://api.openai.com/v1",
        model="gpt-4.1",
        timeout_seconds=30,
    )

    raw_output, structured = client.generate("pm", "hello", "memory")

    assert '"action": "final"' in raw_output
    assert structured == {"action": "final", "message": "done"}
