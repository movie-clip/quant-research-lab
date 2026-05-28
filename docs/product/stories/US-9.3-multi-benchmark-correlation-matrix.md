# US-9.3: Multi-benchmark correlation matrix

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Next phase
**Last updated:** 2026-05-28

## Story

As a **portfolio researcher**, I want to see a single table comparing my
portfolio's correlation (ρ), beta (β), and R² against five market benchmarks
simultaneously — S&P 500 (SPY), Nasdaq-100 (QQQ), Gold (GLD), US Bonds (IEF),
and Global Equity (VT) — so that I can immediately identify which market factor
my portfolio most resembles without manually switching benchmarks.

## Context

After US-9.2 the researcher can see rolling correlation (vs their primary
benchmark) in the Exposure tab. That story was frontend-only — it consumed
fields already in `rolling_risk`. This story adds a **new backend endpoint**
that computes correlation, beta, and R² against five hardcoded benchmarks
simultaneously, and a frontend table that displays them side-by-side.

The backend reuses the existing private helpers `_calculate_beta` and
`_calculate_correlation` from `services/quant-engine/app/analytics/risk.py`.
This story introduces a new `app/analytics/correlation.py` module (scalar
functions only — `pearson`, `beta`, `r_squared`) and a new
`POST /engines/correlation/multi` endpoint.

Implementer must read:
- `docs/finance/financial-methodology.md` — "Rolling Pearson Correlation",
  "Beta", "R²" sections
- `services/quant-engine/app/analytics/risk.py` — `_calculate_beta`,
  `_calculate_correlation` (existing helpers to reuse)
- `services/quant-engine/app/services/attribution_engine.py` — pattern for
  window-based lookback date computation (`_lookback_calendar_days`) and
  synthetic daily state construction (`_build_synthetic_snapshot_history_states`)

## Acceptance criteria

- [ ] AC1 — `POST /engines/correlation/multi` accepts a
  `MultiBenchmarkCorrelationRequest` (same holdings fields as
  `PortfolioEngineRequest` + `lookback_days: int`, default 252) and returns a
  `MultiBenchmarkCorrelationResult` containing stats for all five hardcoded
  benchmarks (SPY, QQQ, GLD, IEF, VT).
- [ ] AC2 — Each `BenchmarkStats` entry contains: `symbol`, `label` (human
  name e.g. "S&P 500"), `correlation: float | null`, `beta: float | null`,
  `r_squared: float | null`, `trust: 'synthetic' | 'unavailable'`.
- [ ] AC3 — When a benchmark has insufficient price history (< 20 trading
  days overlap with the portfolio), its `correlation`, `beta`, and `r_squared`
  are all null and its `trust` is `'unavailable'`.
- [ ] AC4 — The Exposure tab shows a `BenchmarkCorrelationTable` below the
  rolling correlation chart. Columns: Benchmark, ρ (correlation), β (beta),
  R², Trust. Rows are sorted by |ρ| descending by default.
- [ ] AC5 — Null cells render as "—" (not zero, not blank, not "N/A").
- [ ] AC6 — A "Synthetic" badge appears in the table header or as a per-row
  indicator next to unavailable rows.
- [ ] AC7 — The table loads data once when the Exposure tab is opened (or a
  new portfolio is loaded) — it does not re-fetch on every benchmark selector
  change in the drift/correlation charts above it.
- [ ] AC8 — `npx tsc --noEmit` clean; `npx vitest run` passes; backend pytest
  passes; `python scripts/run_all_tests.py` is green.

## Test plan

Backend (pytest):
- `test_correlation_engine.py` — route `POST /engines/correlation/multi`
  returns 200 with five rows; SPY row has non-null values when holdings have
  ≥ 20 days of history; a benchmark with 0 historical overlap returns
  `trust='unavailable'` and all null metric fields; rows are ordered by
  |correlation| descending; `lookback_days` parameter is respected.

Frontend (vitest):
- `BenchmarkCorrelationTable.test.tsx` — renders 5 rows; null fields show
  "—"; unavailable rows show trust indicator; rows are sorted by |ρ|;
  component renders "No data" when `benchmarks` prop is empty.

Regression / guardrail:
- `test_correlation_engine.py` (US-9.2 tests) — all must stay green.
- `RollingCorrelationChart.test.tsx` — must stay green.
- `python scripts/run_all_tests.py` — full suite green (219+ backend,
  111+ frontend).

## Tickets

- [ ] T-9.3.1 — **Backend analytics module**: create
  `services/quant-engine/app/analytics/correlation.py` with scalar functions:
  `pearson(r_p, r_b) -> float | None` (Pearson ρ; null when len < 2 or std = 0),
  `beta(r_p, r_b) -> float | None` (cov/var; null when var = 0 or len < 20),
  `r_squared(r_p, r_b) -> float | None` (ρ²; null when ρ is null). Unit tests
  in `test_correlation_engine.py` covering edge cases: all-null input, zero
  variance, short series.

- [ ] T-9.3.2 — **Backend schema + service + route**: create
  `app/schemas/correlation.py` with `MultiBenchmarkCorrelationRequest` and
  `MultiBenchmarkCorrelationResult` (containing `list[BenchmarkStats]` +
  `lookback_days`); create `app/services/correlation_engine.py` with
  `run_multi_benchmark_correlation` (builds synthetic daily states via
  `_build_synthetic_snapshot_history_states`, fetches all five benchmark price
  histories, calls analytics functions for each, sorts rows by |ρ| descending);
  create `app/api/routes/correlation.py` with `POST /engines/correlation/multi`;
  register in `app/api/main.py`. Add 5 integration pytest tests to
  `test_correlation_engine.py`.

- [ ] T-9.3.3 — **Frontend types**: add `BenchmarkStats`,
  `MultiBenchmarkCorrelationResult` to `features/portfolio/types.ts`; add
  `runMultiBenchmarkCorrelation(snapshot, lookbackDays?)` to
  `portfolioAnalysisAdapter.ts`.

- [ ] T-9.3.4 — **Frontend component**: create
  `features/portfolio/BenchmarkCorrelationTable.tsx` — `<table>` with columns
  Benchmark / ρ / β / R² / Trust; sorts rows by |ρ| descending;
  null → "—"; unavailable trust → "Unavailable" badge; Synthetic trust →
  "Synthetic" badge. Create `BenchmarkCorrelationTable.test.tsx` with 5 tests.

- [ ] T-9.3.5 — **Wire into Exposure tab**: add `multiBenchmarkResult` state
  to `App.tsx`; call `runMultiBenchmarkCorrelation` in parallel with
  exposure + drift in `analyzeExposureSnapshot`; pass result as
  prop to `ExposurePanel`; render `BenchmarkCorrelationTable` in
  `ExposurePanel.tsx` beneath `RollingCorrelationChart`.

- [ ] T-9.3.6 — **Docs close-out**: update `docs/contracts/correlation-fields.md`
  with multi-benchmark fields; set US-9.3 to Done in
  `docs/product/stories/README.md`; add slice log entry to
  `docs/product/epic-roadmap.md`; set Epic 9 snapshot to all Done.

## Out of scope

- No user-configurable benchmark list (five symbols are hardcoded).
- No rolling multi-benchmark view — this is a point-in-time snapshot over the
  lookback window.
- No heatmap or scatter chart — table only in this story.
- No statistical significance testing (p-values, t-statistics).

## Notes / decisions

- **Five hardcoded benchmarks**: SPY (S&P 500), QQQ (Nasdaq-100), GLD (Gold),
  IEF (US 7-10yr Bonds), VT (Total World Equity). These are defined as a
  constant in `correlation_engine.py`, not in the request.
- **Parallel fetch**: `run_multi_benchmark_correlation` should fetch all five
  benchmark price series concurrently (e.g. `asyncio.gather` or
  `ThreadPoolExecutor`) to keep the endpoint fast.
- **Sorting**: sort rows by `abs(correlation)` descending in the backend
  response; the frontend preserves this order by default.
- **`BenchmarkStats.label`**: human-readable names ("S&P 500", "Nasdaq-100",
  "Gold", "US Bonds 7-10yr", "Global Equity") defined in a lookup table in the
  backend service, not passed by the client.
- **Academic references**: Sharpe (1964) for beta; Elton et al. (2014) Ch. 5
  for R²; Grinold & Kahn (2000) Ch. 2 — all cited in
  `financial-methodology.md`.
