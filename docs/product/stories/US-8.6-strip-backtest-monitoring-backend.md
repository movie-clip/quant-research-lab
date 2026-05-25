# US-8.6: Remove backtest and monitoring backend

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** [`epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want the backtest and monitoring routes, services, and schemas removed from the backend, so that the quant-engine contains only what the Dashboard and Exposure surfaces actually call.

## Context

`app/api/routes/backtests.py` and the backtest engine services (`backtests/engine.py`, `backtests/portfolio_engine.py`, `backtest_engine_service.py`, `portfolio_backtest_engine.py`) are dead code after the frontend Workspace tab was removed in US-8.1–8.4. `monitor_definition_artifact_service.py` and related schemas are similarly unreachable. This story deletes all of it. Combined with US-8.5, the full backend deletion is delivered in a single PR.

## Acceptance criteria

- [x] AC1 — `app/api/routes/backtests.py` is deleted.
- [x] AC2 — `app/backtests/` package (`engine.py`, `portfolio_engine.py`, `__init__.py`) is deleted.
- [x] AC3 — `app/services/backtest_engine_service.py`, `portfolio_backtest_engine.py`, and `monitor_definition_artifact_service.py` are deleted.
- [x] AC4 — `app/schemas/backtest_engine.py` is deleted.
- [x] AC5 — `app/datasets/` package (`catalog.py`, `sample_data.py`, `__init__.py`) is deleted.
- [x] AC6 — All corresponding test files (`test_backtests.py`, `test_portfolio_allocation_backtests.py`, `test_mocked_flows.py`) are deleted.
- [x] AC7 — `SKIP_GOLDEN_FRESHNESS_CHECK=1 python -m pytest app/tests/` is green (214 tests pass).

## Test plan

Backend (pytest):
- Full retained pytest suite — 214 tests pass after all deletions (combined with US-8.5 scope).

Regression / guardrail:
- `dashboard_history_engine.py` and `diagnostics_engine.py` confirmed to have no imports from `portfolio_backtest_engine.py` or `backtest_engine_service.py` before deletion.

## Tickets

- [x] T-8.6.1 — Delete `app/api/routes/backtests.py`; update `app/api/main.py` router includes (done as part of T-8.5.1 combined pass).
- [x] T-8.6.2 — Delete `app/backtests/` package. Delete `app/services/backtest_engine_service.py`, `portfolio_backtest_engine.py`, `monitor_definition_artifact_service.py`.
- [x] T-8.6.3 — Delete `app/schemas/backtest_engine.py`. Delete `app/datasets/` package.
- [x] T-8.6.4 — Delete test files: `test_backtests.py`, `test_portfolio_allocation_backtests.py`, `test_mocked_flows.py`. Run full pytest — 214 pass.

## Out of scope

- Removing frontend backtest code — covered in US-8.2.
- Removing App.tsx backtest/monitoring state — covered in US-8.4.
- Removing `data/artifacts/monitor-definitions/` directory — covered in US-8.8.

## Notes / decisions

- US-8.5 and US-8.6 were delivered together in one PR since both are pure backend deletions with no sequencing dependency between them. The combined pass deleted 155 files (routes, services, schemas, tests, data artifacts).
- `datasets/` package was deleted alongside backtests because its only consumers were the backtest engine and the deleted strategy-lab route.
