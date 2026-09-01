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
- `frontend-typecheck`: `npx tsc --noEmit` — **now part of the canonical gate** (run by `run_all_tests.py`).
- `deadcode`: the dead-code detectors (see below) — **an enforced zero-findings gate** since US-23.8.

## Dead-Code Detection (Epic 23) — enforced gate (US-23.8)

The project carries a dead-code detection floor so unused code is caught, not
re-accumulated. As of **US-23.8 it is an enforced gate**: `scripts/run_all_tests.py`
runs `python scripts/detect_deadcode.py --strict` (ruff + vulture + knip,
zero-findings) plus `npx tsc --noEmit` as suite steps, so any newly-introduced
dead code (or in-file unused local/param) **fails the run**. Tooling (dev-only,
installed via `requirements-dev.txt` / `npm install`):

- **Python** (`services/quant-engine/`): `ruff` (in-file unused — `F401`/`F811`/`F841`, configured in `ruff.toml`) + `vulture` (whole-program unused functions/classes/attributes `--min-confidence 80`, with a reasoned `vulture_allowlist.py` for dynamic-use false positives). 
- **TypeScript** (`apps/desktop/`): `knip` (unused files/exports/types/dependencies — the cross-file dead-export class `tsc` can't see; configured with `ignoreExportsUsedInFile: true` so a flagged export is used *nowhere*, not merely over-exported) + `tsconfig` `noUnusedLocals`/`noUnusedParameters` (in-file, enforced via the `tsc --noEmit` gate step).

**Reading a failure:** the detector summary names which of ruff/vulture/knip
found something and prints the `file:line`. If the symbol is genuinely dead →
remove it. If it is a dynamic-use false positive (route registration, pytest
fixtures, Pydantic/`field_validator` hooks, signature-match kwargs, persisted-
state sanitizers, CLI entry-point scripts) → add a **reasoned** entry to
`vulture_allowlist.py` (Python) or `knip.json` (TS). The allowlist is the
integrity risk: **every entry must name why it is a false positive** — an
unreasoned entry silently re-opens the door. Improvement findings (hardcodes /
magic numbers / anti-patterns) are catalogued in
[`docs/tech-debt-register.md`](../tech-debt-register.md) → Epic 24, not added to
the allowlist. The register also carries the **removal protocol** (the "confirmed
dead" checklist). **ESLint is deliberately not used** for this — `tsc` + `knip`
cover the dead-code goal; ESLint's in-file `no-unused-vars` is redundant with
`tsc` and misses unused exports/files.

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
- **Re-capturing market data** (whenever the statement's history window or holdings change): run `python scripts/refresh_statement.py` (requires `FMP_API_KEY`). It re-captures `golden_market_data.json`, regenerates the goldens, and runs the full suite in one step. A `FrozenMarketDataMiss` during the freshness check is the signal that this is needed.

## Statement refresh workflow

The canonical current IB statement is `docs/IB2026.csv` (US-28.2); the
researcher replaces it with a fresh Activity-Statement CSV export every few
weeks. Since US-28.3 the refresh is one command plus a small, documented set
of deliberate updates:

1. **Replace `docs/IB2026.csv`** with the new export (same filename).
2. **Run `python scripts/refresh_statement.py`** — re-captures the frozen
   market-data fixture (live FMP; needed because the new statement widens the
   history window and may add symbols), regenerates
   `dashboardGoldens.ts`, and runs the full suite.

   **The capture refuses to degrade (US-35.3).** Before writing, it compares the
   new capture against the committed one and stops if the series count drops,
   total rows fall by more than 5%, the benchmark comes back empty, or any
   symbol goes from having data to having none. It prints what changed and
   writes nothing. This exists because on 2026-08-19 the capture overwrote a
   73-series fixture with a 21-series one and reported success — the fixture the
   whole network-free suite derives from, replaced silently.

   If the refusal is *correct* — you deliberately imported a smaller portfolio —
   re-run with `--allow-smaller-capture`. If it is not, the usual causes are a
   rejected `FMP_API_KEY` (which now raises rather than returning empty data,
   US-35.1) or a poisoned cache: check `python scripts/manage_cache.py list`,
   and note that `--namespace history` does **not** clear `history_yf` (US-35.2).
3. **Update the importer-derived statement-truth pins** — all in ONE module:
   `services/quant-engine/app/tests/statement_truths.py`. These are the values
   the IB importer alone produces from the CSV (symbol lists, ledger counts,
   totals, TWR, implied FX, one pinned position per currency). The failing test
   is `test_importer_csv.py::test_statement_matches_truths_module`, and its
   `diff_statement_truths` output lists exactly which pins moved (each line
   names this doc). Structural tests — those that derive their expectations from
   the imported snapshot's own totals (schema shape, reconciliation passes, sums
   that fall out of the snapshot) — do not pin values from this module and must
   not fail on a refresh.

   **Replay-audit regression pins (step 3b).** A *distinct* pin class that does
   NOT live in `statement_truths.py` and is not a candidate to move there:
   inline `pytest.approx` literals in `app/tests/test_ledger_replay_audit.py`,
   `app/tests/test_portfolio_state.py` and `app/tests/test_analytics.py` —
   terminal and peak market value, per-day and range TWR, peak date,
   `len(states)`, cash-anchor residual, reconciliation adjustment,
   money-weighted return and investment gain, per-symbol replayed value, and the
   HHI / volatility ratios. These are **replay-engine-derived**, not
   importer-derived: each depends on the frozen `FrozenMarketData` golden plus
   the ledger-replay engine running over the widened history window, so there is
   no single importer accessor for them and `diff_statement_truths` cannot see
   them. On each refresh they are hand-regenerated from the values the
   assertion-failure messages report (deterministic, no network — the frozen
   golden is already staged by step 2), the new literal is written in place, and
   a `# <YYYY-MM-DD> statement refresh: <old> -> <new>` comment is added above
   the assertion recording the move (older `US-33.4:` pre/post comments in the
   same files are the prior art for this). The Epic 31 F-1..F-5 replay-audit
   tests exist *precisely* to pin these magnitudes in the order the narrative
   builds them, so pinning them inline is correct by design — re-homing them into
   a constants module would strip the per-test context the numbers only make
   sense inside.
4. **Add registry entries for brand-new holdings** — the one deliberate step
   outside the truths module (see the fmp-data skill; watch for wrong-fund
   ticker collisions like CIBR US vs CIBR.L UCITS). The registry ISIN
   integrity test (`test_registry_isin_integrity.py`) checks seeds against
   the statement's own ISINs.
5. **Commit together**: `docs/IB2026.csv`, `golden_market_data.json`,
   `dashboardGoldens.ts`, `statement_truths.py`, and any registry entries.

This failure surface is regression-pinned by
`app/tests/test_statement_refresh.py`: a simulated swap (changed quantity +
new symbol) must surface diffs ONLY from the truths module (each naming this
workflow) plus the registry-coverage step. The swap simulation inspects only
the diff of its own mutation, so it does **not** exercise the step-3b
replay-audit pins — those are a known, documented exception to "only the
truths module moves on a refresh", not a covered surface (the
`diff_replay_truths` harness that would let the meta-test assert against them
is unbuilt, tracked as a producer follow-up). Setting that class aside:
anything else failing on a refresh is a structural test wrongly pinning
statement truths (fix the test, per the classification in
`statement_truths.py`'s docstring).

The legacy IB PDFs (2022–2025), `FF2026.pdf`, and `ESPP2026.pdf` are frozen
committed fixtures — never refreshed — so their pinned truths (e.g. in
`test_importer.py`) are stable by construction and intentionally stay inline.

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
