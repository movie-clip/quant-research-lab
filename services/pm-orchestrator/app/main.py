from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import Database
from .llm import build_llm_client
from .orchestrator import Orchestrator
from .worker import Worker


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

db = Database(settings.db_path)
llm = build_llm_client()
orchestrator = Orchestrator(db=db, llm=llm)
worker = Worker(orchestrator=orchestrator)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    if not worker.is_alive():
        worker.start()
    yield
    worker.stop()
    worker.join(timeout=2)


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "runs": db.list_runs(),
        },
    )


@app.post("/runs")
def create_run_form(input_text: str = Form(...)) -> RedirectResponse:
    run_id = orchestrator.submit_run(input_text)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.post("/api/runs")
async def create_run_api(request: Request) -> JSONResponse:
    payload = await request.json()
    input_text = (payload.get("input") or "").strip()
    if not input_text:
        raise HTTPException(status_code=400, detail="Missing input")
    run_id = orchestrator.submit_run(input_text)
    return JSONResponse({"run_id": run_id, "url": f"/runs/{run_id}"})


@app.post("/runs/{run_id}/answer")
def answer_blocked_run_form(run_id: str, answer: str = Form(...)) -> RedirectResponse:
    try:
        orchestrator.answer_blocked_run(run_id, answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.post("/api/runs/{run_id}/answer")
async def answer_blocked_run_api(run_id: str, request: Request) -> JSONResponse:
    payload = await request.json()
    answer = (payload.get("answer") or "").strip()
    if not answer:
        raise HTTPException(status_code=400, detail="Missing answer")
    try:
        orchestrator.answer_blocked_run(run_id, answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"status": "queued", "run_id": run_id})


@app.post("/tasks/{task_id}/retry")
def retry_task_form(task_id: str) -> RedirectResponse:
    try:
        run_id = db.retry_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.post("/api/tasks/{task_id}/retry")
def retry_task_api(task_id: str) -> JSONResponse:
    try:
        run_id = db.retry_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse({"status": "queued", "run_id": run_id})


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str) -> HTMLResponse:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {"run": run},
    )


@app.get("/runs/{run_id}/status", response_class=HTMLResponse)
def run_status(request: Request, run_id: str) -> HTMLResponse:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    tasks = db.get_tasks_for_run(run_id)
    task_tree = db.get_tasks_for_run_grouped(run_id)
    graph_rows = orchestrator.build_graph_rows(run_id)
    events = db.list_events(run_id)
    agent_messages = db.list_agent_messages_for_run(run_id)
    return templates.TemplateResponse(
        request,
        "partials/run_status.html",
        {
            "run": run,
            "tasks": tasks,
            "task_tree": task_tree,
            "graph_rows": graph_rows,
            "events": events,
            "agent_messages": agent_messages,
        },
    )


@app.get("/api/runs/{run_id}")
def run_detail_api(run_id: str) -> JSONResponse:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return JSONResponse(
        {
            "run": run,
            "tasks": db.get_tasks_for_run(run_id),
            "graph_rows": orchestrator.build_graph_rows(run_id),
            "events": db.list_events(run_id),
            "agent_messages": db.list_agent_messages_for_run(run_id),
        }
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
