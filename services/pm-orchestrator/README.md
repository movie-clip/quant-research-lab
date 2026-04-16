# PM Orchestrator

Starter `FastAPI + SQLite + HTMX` app for persistent `/pm` agent orchestration.

This service is intentionally small and local-first:
- `/pm <request>` always routes to the persistent `pm` agent
- `pm` can delegate to persistent specialists
- specialists return to their parent agent, not directly to the user
- only `pm` can finalize a run for the UI

The current implementation ships with:
- a deterministic in-process fake LLM adapter for local testing without keys
- an OpenAI-compatible Responses API adapter when `PM_ORCHESTRATOR_LLM_PROVIDER=openai` and `PM_ORCHESTRATOR_LLM_API_KEY` are set

## Run

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8090
```

Open `http://127.0.0.1:8090`.

## Optional real model provider

Set these environment variables before starting the app:

```bash
set PM_ORCHESTRATOR_LLM_PROVIDER=openai
set PM_ORCHESTRATOR_LLM_API_KEY=your_key_here
set PM_ORCHESTRATOR_LLM_MODEL=gpt-4.1
```

Optional overrides:
- `PM_ORCHESTRATOR_LLM_API_BASE`
- `PM_ORCHESTRATOR_LLM_TIMEOUT_SECONDS`

If the provider config is missing, the app falls back to the deterministic fake adapter.

Current provider verification status:
- fake adapter is covered by local tests
- OpenAI-compatible provider wiring is covered by a mocked unit test for request/response parsing
- no live provider call is executed in repo tests because that would require a real key and network access

## What is included

- persistent agent registry and session summaries
- SQLite-backed runs, tasks, events, and agent sessions
- background worker thread for queued tasks
- recursive delegation / synthesis flow
- HTMX run status panel for live updates
- blocked-question answer + resume flow for PM

## Main files

- `app/main.py` - web app and routes
- `app/db.py` - SQLite schema and persistence helpers
- `app/orchestrator.py` - run/task orchestration engine
- `app/llm.py` - fake adapter plus optional OpenAI-compatible provider adapter
- `app/worker.py` - background task loop
- `app/agents.py` - persistent specialist registry
