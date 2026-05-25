# US-8.5: Remove ranking, construction, and optimizer backend

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** [`epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want the backend to contain only the services the retained product surface (Dashboard and Exposure) uses, so that the codebase is smaller, unambiguous, and free of dead code.

## Context

After US-8.1–8.3 removed the frontend tabs and feature directories, the quant-engine still contains routes, services, schemas, and data artifacts for ranking, construction, and optimizer workflows that are no longer reachable from the UI. This story deletes that dead backend code. Dashboard and Exposure routes remain untouched.

## Acceptance criteria

- [x] AC1 — Routes `construction.py`, `optimizer.py`, `strategy_lab.py` are deleted from `app/api/routes/`.
- [x] AC2 — All ranking, construction, and optimizer service files are deleted from `app/services/`.
- [x] AC3 — Schemas `construction.py`, `generic_ranking.py`, `optimizer.py`, `ranking.py`, `research.py` are deleted from `app/schemas/`; instrument types extracted to a new `instruments.py` schema consumed by `registry.py`.
- [x] AC4 — The `strategies/` package and `overlay/` package are deleted.
- [x] AC5 — All corresponding test files are deleted.
- [x] AC6 — `app/api/main.py` registers only the retained routers: health, imports, exposure, diagnostics, dashboard_history, market_data.
- [x] AC7 — `SKIP_GOLDEN_FRESHNESS_CHECK=1 python -m pytest app/tests/` is green (214 tests pass).

## Test plan

Backend (pytest):
- `app/tests/test_routes.py` — retained route smoke tests (health, import, CORS) pass.
- `app/tests/test_analytics.py`, `test_dashboard_history.py`, `test_diagnostics.py`, `test_exposure.py`, `test_imports.py`, `test_market_data_routes.py` — all retained suite tests pass.

Regression / guardrail:
- Full retained pytest suite (214 tests) green with `SKIP_GOLDEN_FRESHNESS_CHECK=1`.

## Tickets

- [x] T-8.5.1 — Delete `app/api/routes/construction.py`, `optimizer.py`, `strategy_lab.py`. Update `app/api/main.py` to remove their router includes.
- [x] T-8.5.2 — Delete all ranking, construction, optimizer, strategy-lab, cross-sectional-research, and monitor-definition service files from `app/services/`. Audit `dashboard_history_engine.py` and `diagnostics_engine.py` for shared imports; trim rather than delete if needed (both were clean — full deletion possible).
- [x] T-8.5.3 — Delete `app/schemas/construction.py`, `generic_ranking.py`, `optimizer.py`, `ranking.py`, `research.py`, `backtest_engine.py`. Extract `Instrument`, `AssetClass`, `InstrumentKind`, `FuturesContract` to new `app/schemas/instruments.py`; update `app/instruments/registry.py` import.
- [x] T-8.5.4 — Delete `app/strategies/` package and `app/overlay/` package.
- [x] T-8.5.5 — Delete all test files for removed features. Clean `conftest.py` fixture that monkeypatched deleted artifact-store services. Remove `test_strategy_lab_holdings_refresh_route` from `test_market_data_routes.py`. Run full pytest — 214 pass.
- [x] T-8.5.6 — Delete all persisted data artifacts: `data/artifacts/etf-ranking-artifacts/`, `etf-replacement-ranking-artifacts/`, `generic-ranking-artifacts/`, `optimizer-handoffs/`, `construction-artifacts/`. Retain `cross-sectional-research-artifacts/` and `monitor-definitions/` directories (empty, cleaned separately in US-8.8).

## Out of scope

- Removing `data/artifacts/cross-sectional-research-artifacts/` and `monitor-definitions/` — covered in US-8.8.
- Removing backtest and monitoring routes — that is US-8.6 (combined in this PR).
- Frontend changes — covered in US-8.1 through US-8.4.

## Notes / decisions

- `research.py` contained both ranking artifact types and core instrument types (`Instrument`, `AssetClass`, `InstrumentKind`, `FuturesContract`). The instrument types are used by `registry.py` (retained) and were extracted to a new `schemas/instruments.py`. This is a pure refactor with no behaviour change.
- `dashboard_history_engine.py` and `diagnostics_engine.py` had no imports from any deleted schema or service — both full-deletion paths were clean.
