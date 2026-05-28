# US-9.6: Multi-benchmark correlation follow-ups (sort + trust + docs)

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Done
**Last updated:** 2026-05-28

## Story

As a **portfolio researcher**, I want the multi-benchmark correlation table's
sort ordering and per-row trust indicator to be pinned by regression tests and
documented, so that future refactors cannot silently break the contract and so
that any agent reading the methodology doc can find a single home for the
multi-benchmark application of Pearson / β / R².

## Context

US-9.3 shipped a working multi-benchmark correlation matrix
(`POST /engines/correlation/multi`, 5 benchmarks, sorted by |ρ| descending,
synthetic trust). `verify-story` on US-9.3 surfaced three small gaps that are
cosmetic but worth fixing before Epic 9 closes for good:

1. **No test pins the sort order** — backend sorts by `|correlation|` desc
   (`correlation_engine.py:202-206`), but `grep -n "sort\|order" test_correlation_engine.py`
   returns nothing. A future refactor could silently break AC4.
2. **AC4 column-vs-opacity ambiguity** — US-9.3's AC4 reads "Columns: Benchmark,
   ρ, β, R², Trust" (five columns). Implementation has four columns; trust is
   shown via row-level CSS opacity dim (line 33) plus the table-header
   "Synthetic" badge (line 172-176). This is the cleaner UX — but the
   contract doc and the test suite don't pin it.
3. **Dangling methodology reference** — `analytics/correlation.py:9` docstring
   says "see docs/finance/financial-methodology.md §Multi-Benchmark Correlation",
   but that section does not exist. The underlying formulas live under
   §Rolling Pearson Correlation, §Beta, §R².

This story is **cleanup only** — no new user-visible behaviour, no formula
changes, no schema changes. After it lands, Epic 9 is fully closed.

Implementer must read:

- `docs/finance/financial-methodology.md` — confirm §Rolling Pearson Correlation,
  §Beta, §R² are unchanged; add a short umbrella §Multi-Benchmark Correlation
  section that points at them
- `docs/contracts/correlation-fields.md` — update the "BenchmarkStats"
  section's UI notes to document that trust is rendered as row opacity + a
  table-header badge, not a column
- `services/quant-engine/app/services/correlation_engine.py:200-210` — the
  existing sort logic that the new tests will pin

## Acceptance criteria

- [x] AC1 — Backend `test_correlation_engine.py` contains a test
  (e.g. `test_benchmarks_sorted_by_abs_correlation_descending`) that constructs
  a `MultiBenchmarkCorrelationResult` with mixed correlation values and asserts
  the rows come back ordered by `abs(correlation)` descending.
- [x] AC2 — Backend `test_correlation_engine.py` contains a test
  (e.g. `test_unavailable_benchmarks_sort_last`) that mixes synthetic and
  unavailable rows and asserts every `trust='unavailable'` row appears after
  every `trust='synthetic'` row.
- [x] AC3 — Frontend `BenchmarkCorrelationTable.test.tsx` contains a test
  that renders a result whose `benchmarks` array has a specific intentional
  order (e.g. QQQ first, then SPY, then GLD) and asserts the rendered `<tr>`
  elements appear in that exact order — i.e. the component preserves the
  engine's sort and does not re-order client-side.
- [x] AC4 — Frontend `BenchmarkCorrelationTable.test.tsx` contains a test
  that asserts unavailable rows render with the dimmed `opacity` style
  (the per-row trust indicator), distinguishing them visually from synthetic
  rows. Use a query like `getByText('Gold').closest('tr')` + style assertion
  on `opacity`.
- [x] AC5 — `docs/finance/financial-methodology.md` contains a new section
  `## Multi-Benchmark Correlation` placed after §R². The section is short
  (≤ 15 lines), names the five hardcoded benchmarks (SPY/QQQ/GLD/IEF/VT),
  cites §Rolling Pearson Correlation / §Beta / §R² as the underlying formulas,
  documents the sort contract (`|ρ|` desc, unavailable last), and links the
  contract doc `docs/contracts/correlation-fields.md#us-93--multi-benchmark-correlation-matrix`.
- [x] AC6 — `docs/contracts/correlation-fields.md` BenchmarkStats UI-display
  notes updated to read: "trust is rendered as row opacity (dim for
  `unavailable`) + a table-header `Synthetic` badge. There is no dedicated
  Trust column."
- [x] AC7 — `services/quant-engine/app/analytics/correlation.py:9` docstring
  reference to `§Multi-Benchmark Correlation` now resolves (the new section
  from AC5 makes it valid).
- [x] AC8 — `python scripts/run_all_tests.py` is green;
  `npx tsc --noEmit` is clean. Net delta: +2 backend pytest, +2 frontend
  vitest. No regressions in the existing 22 backend + 5 frontend correlation
  tests.

## Test plan

Backend (pytest):

- `test_correlation_engine.py` — **2 new tests** (existing 22 stay green):
  - `test_benchmarks_sorted_by_abs_correlation_descending` — constructs a
    `MultiBenchmarkCorrelationResult` with `benchmarks=[ρ=0.3, ρ=0.9, ρ=-0.7, ρ=0.1, ρ=-0.5]`
    (via direct service call with a mocked MarketDataService, OR by
    constructing the result in-test and asserting the service's sort function
    in isolation). Asserts result order is `[0.9, -0.7, -0.5, 0.3, 0.1]` by
    `abs(correlation)`.
  - `test_unavailable_benchmarks_sort_last` — mixes 2 synthetic rows
    (ρ=0.4, ρ=0.6) with 3 unavailable rows. Asserts the first 2 returned
    rows have `trust='synthetic'` and the last 3 have `trust='unavailable'`.

Frontend (vitest):

- `BenchmarkCorrelationTable.test.tsx` — **2 new tests** (existing 5 stay green):
  - `test_rows_render_in_engine_returned_order` — `mockRun.mockResolvedValue`
    with `benchmarks` in a deliberately non-alphabetical, non-correlation-sorted
    order (e.g. ['GLD', 'SPY', 'VT', 'QQQ', 'IEF']). Asserts the rendered
    `<tr>` elements appear in that exact order via
    `screen.getAllByRole('row')` and reading the first cell.
  - `test_unavailable_rows_render_with_dimmed_opacity` — renders a result
    where 2 of 5 rows have `trust='unavailable'`. Queries those rows and
    asserts their inline `opacity` style is the dimmed value (`0.55` per
    line 33 of the component).

Regression / guardrail:

- All 22 existing tests in `test_correlation_engine.py` must stay green.
- All 5 existing tests in `BenchmarkCorrelationTable.test.tsx` must stay green.
- No change to `analytics/correlation.py` formulas, `correlation_engine.py`
  service logic, or the schemas — these are tests + docs only.
- Final suite: 263 backend + 109 frontend green (was 261 + 107 after US-9.3).

## Tickets

- [x] T-9.6.1 — **Backend sort-order tests**: add the 2 new tests to
  `services/quant-engine/app/tests/test_correlation_engine.py` per the test
  plan AC1+AC2. Tests target the in-service sort logic
  (`correlation_engine.py:202-206`); if a `mocker.patch` on
  `MarketDataService` is needed to inject deterministic correlation values,
  follow the autouse pattern in `conftest.py`. **Invoke the `write-tests`
  skill for this slice.**

- [x] T-9.6.2 — **Frontend trust-indicator + ordering tests**: add the 2
  new tests to `apps/desktop/src/features/portfolio/BenchmarkCorrelationTable.test.tsx`
  per the test plan AC3+AC4. Reuse the existing `vi.mock` adapter pattern
  and `makeFullResult()` / `makeAllUnavailableResult()` factories. For the
  opacity assertion, target the rendered `<tr>` and read inline style.
  **Invoke the `write-tests` skill for this slice.**

- [x] T-9.6.3 — **Docs close-out (auto via update-docs)**:
  - Add `## Multi-Benchmark Correlation` umbrella section to
    `docs/finance/financial-methodology.md` (after §R²; ≤ 15 lines; per AC5)
  - Update `docs/contracts/correlation-fields.md` BenchmarkStats UI notes
    (per AC6)
  - Verify `analytics/correlation.py:9` docstring now resolves (per AC7);
    no code change needed — the section heading from AC5 makes the reference valid
  - Update `docs/product/epic-roadmap.md`: add US-9.6 slice log entry,
    move Epic 9 row back to all-Done after US-9.6 ships, keep epic header
    as "Completed Epic"
  - Update `docs/product/stories/README.md`: set US-9.6 to Done
  - Set story status: Done; tick all ACs + tickets

## Out of scope

- **No new Trust column** in `BenchmarkCorrelationTable` — opacity + header
  badge is the chosen UX. If the user later wants an explicit Trust column,
  that's a separate story.
- **No total-return correlation** (using `adjClose` instead of `price` for
  income-paying benchmarks IEF/VT) — flagged in US-9.3 verify-story report
  as a future story candidate, not this one.
- **No multi-currency FX handling** for synthetic history — pre-existing
  limitation of the synthetic-history pipeline, shared by attribution engine;
  fixing it is its own story.
- **No new schema fields** — `BenchmarkStats` shape is fixed.
- **No formula changes** — Pearson / β / R² stay exactly as they are.

## Notes / decisions

- **Why this story exists**: surfaced by `verify-story` on US-9.3 (see report
  in conversation history). Three small follow-ups packaged together because
  individually they're too small to be standalone stories but collectively
  they pin contracts that would otherwise drift.
- **No `quant-research` brief needed** — no new formula; the umbrella section
  in AC5 only restates the application of existing formulas.
- **Why not add a Trust column** — the opacity + header-badge UX is more
  scannable than a redundant fifth column showing "synthetic" / "synthetic" /
  "synthetic" / "unavailable" / "unavailable". The story explicitly updates
  the contract doc to document this choice.
- **Sort-test isolation**: prefer testing the sort by calling
  `run_multi_benchmark_correlation` with mocked benchmark prices that produce
  predictable correlations, rather than testing a private sort helper. This
  keeps the test honest about the actual contract.
