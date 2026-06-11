# Testing Architecture

This document defines the target testing architecture for reconstruction work. The goal is a flexible, deterministic, and auditable test system that can evolve while preserving one stable confidence command.

## Goals

- Keep `python scripts/run_all_tests.py` as the canonical full-project test entrypoint.
- Make narrow reconstruction work easy without weakening the full test gate.
- Keep financial outputs traceable to backend formulas, schemas, and documented methodology.
- Treat broker statements as source-of-truth layout/accounting references while keeping committed expectations privacy-aware and deterministic.
- Prefer fail-fast diagnostics over broad downstream assertion noise.

## Non-Goals

- Do not replace pytest or Vitest.
- Do not move financial calculations into desktop tests or components.
- Do not make raw broker PDFs the only asserted artifact; tests should assert normalized semantics.
- Do not allow local-only test shortcuts to bypass the canonical full run.

## Canonical Test Contract

`scripts/run_all_tests.py` is the command developers and agents should run before considering the project healthy. Its default behavior should remain stable:

1. Generate dashboard golden fixtures from backend output.
2. Run backend pytest from `services/quant-engine`.
3. Run desktop Vitest from `apps/desktop`.

Future changes may add optional phase selectors, but the default command must continue to run every required project test.

Recommended future phase names:

- `goldens`: regenerate or check generated cross-layer fixtures.
- `backend`: run pytest.
- `frontend`: run Vitest.
- `frontend-typecheck`: run `npm run build` or `npx tsc --noEmit` if promoted into the canonical gate.

## Test Layers

Backend tests should be organized conceptually by layer even if files remain in the current flat directory during reconstruction.

| Layer | Purpose | Examples |
| --- | --- | --- |
| Unit | Small pure functions and validation helpers | parsers, normalizers, schema validators |
| Service | Deterministic business logic without HTTP | import admission, construction, ranking, artifacts |
| Route | FastAPI request/response contracts | upload/analyze, ranking routes, construction routes |
| Contract | Backend-to-desktop field and golden contracts | dashboard goldens, schema/type alignment |
| Source Fixture | Real broker statement semantic extraction | IB2026, FF2026, ESPP2026 normalized assertions |
| Artifact | Persisted write-once/fail-closed stores | ranking artifacts, construction artifacts, monitor definitions |
| Market Data | Cache/client behavior and degradation paths | FMP cache, unavailable/degraded data paths |

Frontend tests should stay colocated with feature code, but each test should make its layer clear through file placement and test names:

- app/store and storage behavior
- feature component rendering
- route/fetch adapter behavior
- generated golden rendering contracts
- fail-closed unavailable/degraded UI states

## Shared Fixtures

Shared fixtures should be explicit, narrow, and deterministic.

- Keep cross-cutting pytest setup in `services/quant-engine/app/tests/conftest.py` only when it truly applies to almost every test.
- Prefer helper modules for fixture concerns that can be imported directly, such as broker statement paths or normalized snapshot serializers.
- Avoid silent fixture absence. If a local fixture is intentionally optional, use `pytest.skip(...)` with a clear reason.
- Avoid absolute developer-machine paths in tests. Resolve paths relative to the repository root.

Current high-value shared helpers:

- `services/quant-engine/app/tests/_statement_fixtures.py` for broker statement paths.
- `services/quant-engine/app/scripts/export_dashboard_goldens.py` for backend-generated desktop dashboard fixtures.
- `apps/desktop/src/test/dashboardGoldens.ts` for generated dashboard expectations.

## Broker Statement Source-of-Truth Strategy

The active real-statement references are:

- `docs/IB2026.pdf`
- `docs/FF2026.pdf`
- `docs/ESPP2026.pdf`

These files should be used as durable layout and accounting-shape references. Tests should assert normalized extracted semantics rather than depending on binary PDF identity.

Recommended semantic assertions per broker:

- statement metadata: importer, account label, base currency, period, page count
- positions: selected symbols, quantities, market values, dates, instrument identity fields
- cash: starting and ending balances by currency
- ledger: entry counts, event types, dates, and representative amounts
- totals: starting NAV, ending NAV, stock total, cash total, dividends, taxes, deposits where available
- admission summary: non-pass/pass status, finite numeric evidence, and explicit unavailable/degraded states

Privacy and determinism rules:

- Do not add new raw broker statements unless they are intentionally approved and redacted where needed.
- Prefer committed normalized expected outputs over expanding raw personal statement coverage.
- Normalize `imported_at`, absolute `source_path`, and temporary upload paths before equality checks.
- If PDF SHA checks are introduced, use them as optional fixture identity diagnostics, not the primary product assertion.

## Golden Fixture Workflow

Dashboard goldens are cross-layer contract tests: backend import/analytics output is rendered into TypeScript fixtures consumed by desktop tests.

Since US-21.4 the generator is **fully deterministic and network-free**. It reads market data from a committed, frozen fixture (`services/quant-engine/app/scripts/golden_market_data.json`) via `FrozenMarketData` instead of the live FMP cache, so regeneration produces byte-identical output on every machine and the per-machine churn (the recurring "`git checkout` the goldens before committing" gotcha) is gone. The conftest goldens-freshness fixture inherits this — bare `pytest` passes offline with no env var and no warm cache. `SKIP_GOLDEN_FRESHNESS_CHECK=1` remains only as an explicit escape hatch for narrow runs.

Rules:

- Regenerate through `python scripts/run_all_tests.py` or `python -m app.scripts.export_dashboard_goldens` from `services/quant-engine` — deterministic, no network.
- Review generated diffs before committing; a non-trivial diff now means a real fixture/methodology change (not cache drift).
- Keep source paths canonicalized to basenames so goldens are stable across machines and worktrees.
- If backend output changes intentionally, update methodology and contract docs when the change affects financial semantics.
- **Re-capturing market data** (rare — only when the committed broker statements `IB2026.pdf` / `FF2026.pdf` change, introducing a new symbol/window): run `python -m app.scripts.export_dashboard_goldens --capture` against a warm FMP cache (or live key) to refresh `golden_market_data.json`, then regenerate the goldens. A `FrozenMarketDataMiss` during the freshness check means the fixture is stale and must be re-captured.

## Reconstruction Guidelines

During reconstruction, prefer test changes that reduce coupling and clarify intent:

- Replace broad brittle assertions with semantic assertions tied to truth class and trust state.
- Split large tests only when it improves diagnosis without losing end-to-end confidence.
- Keep generated fixtures generated; do not hand-edit generated output except as part of reviewing a generated diff.
- Add regression tests at the layer where the bug escaped.
- For financial methodology changes, update tests in the same pass as code and docs.

## First Improvement Slice

The recommended first implementation slice is importer fixture hygiene:

1. Route all importer tests through `services/quant-engine/app/tests/_statement_fixtures.py`.
2. Replace silent `return` skips with explicit `pytest.skip(...)` helper messages.
3. Add normalized deterministic re-import equality tests for `IB2026`, `FF2026`, and `ESPP2026`.
4. Add selected semantic assertions for positions, cash, ledger, totals, and admission evidence.
5. Keep `python scripts/run_all_tests.py` as the acceptance command.
