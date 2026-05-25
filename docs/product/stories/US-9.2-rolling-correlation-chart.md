# US-9.2: Rolling correlation engine and chart

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Next phase
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want to see a rolling correlation chart that
shows how my portfolio's correlation to a benchmark has evolved over time
(30-day, 60-day, or 90-day rolling window), so that I can tell whether my
portfolio's market exposure is stable or shifting across different regimes.

## Context

No rolling correlation analytics exist in the codebase today. This story adds:
- A new analytics module `app/analytics/correlation.py` (rolling Pearson ρ,
  beta, R²)
- A new service `app/services/correlation_engine.py` and route
  `POST /engines/correlation/run`
- A frontend `RollingCorrelationChart.tsx` rendered in the Exposure tab beneath
  the indexed return chart (US-9.1)

Implementer must read:
- `docs/finance/financial-methodology.md` — "Rolling Pearson Correlation",
  "Beta", and "R²" sections
- `services/quant-engine/app/services/drift_engine.py` — for the pattern of
  building daily portfolio states and fetching benchmark price history
- `services/quant-engine/app/schemas/drift.py` — for the request schema pattern
  (`PortfolioEngineRequest` base class)

## Acceptance criteria

- [ ] AC1 — `POST /engines/correlation/run` accepts a `CorrelationEngineRequest`
  (same holdings fields as `DriftEngineRequest` + `benchmark_symbol: str` +
  `window_days: int` ∈ {30, 60, 90}) and returns a `CorrelationResult`.
- [ ] AC2 — `CorrelationResult` contains: `rolling_series` (list of
  `{date, correlation: float | null}`), `beta: float | null`,
  `r_squared: float | null`, `correlation_252d: float | null`,
  `benchmark_symbol: str`, `window_days: int`,
  `availability: 'available' | 'partial' | 'unavailable'`.
- [ ] AC3 — Rolling correlation values are null for dates where fewer than
  `window_days` preceding trading-day returns exist; never zero-filled or
  interpolated.
- [ ] AC4 — When benchmark price variance is zero, `beta` is null; when
  fewer than 20 data points are available, `beta` and `r_squared` are null.
- [ ] AC5 — The Exposure tab shows a `RollingCorrelationChart` below the
  indexed return chart. The chart has one line for the selected window,
  y-axis range [−1, +1] with a reference line at 0, x-axis is date.
- [ ] AC6 — A window selector toggles between 30d / 60d / 90d rolling windows.
  Selecting a new window re-fetches from the backend (not client-side slice).
- [ ] AC7 — Summary stats (β, R², ρ₂₅₂d) are displayed as labelled values
  beneath or beside the chart, each with "—" when null.
- [ ] AC8 — Null gaps in the rolling series are rendered as line breaks (not
  connected, not zeroed).
- [ ] AC9 — A "Synthetic" trust badge is visible near the chart title.
- [ ] AC10 — `npx tsc --noEmit` clean; `npx vitest run` passes; backend
  pytest passes.

## Test plan

Backend (pytest):
- `test_correlation_engine.py` — rolling series has correct length (len(dates) − window_days + 1 non-null points for a complete series); prefix nulls when series shorter than window; beta null when var(benchmark)=0; r_squared equals rho²; route `POST /engines/correlation/run` returns 200 with valid schema; `availability='unavailable'` when no portfolio history.

Frontend (vitest):
- `RollingCorrelationChart.test.tsx` — renders line with data; gap on null
  correlation point; summary stats show "—" when beta is null; "No data"
  message when rolling_series is empty; window selector change triggers
  `onWindowChange` callback.

Regression / guardrail:
- `test_drift_engine.py` — all 5 existing tests must stay green.
- `DriftBenchmarkPanel.test.tsx` + `IndexedReturnChart.test.tsx` — must stay
  green (no cross-contamination of state).

## Tickets

- [ ] T-9.2.1 — **Backend analytics**: create
  `services/quant-engine/app/analytics/correlation.py` with:
  - `rolling_pearson(r_p: list[float | None], r_b: list[float | None], window: int) -> list[float | None]` — returns list of same length as inputs; nulls for prefix
  - `beta(r_p, r_b) -> float | None` — cov/var; null when var=0 or len<20
  - `r_squared(r_p, r_b) -> float | None` — beta² of correlation; null when insufficient data
  - Unit tests in `test_correlation_engine.py` for each function (edge cases: all-null input, zero variance, short series).

- [ ] T-9.2.2 — **Backend schema + service + route**: create
  `app/schemas/correlation.py` (`CorrelationEngineRequest`,
  `RollingCorrelationPoint`, `CorrelationResult`); create
  `app/services/correlation_engine.py` (`run_correlation_engine`); create
  `app/api/routes/correlation.py` (`POST /engines/correlation/run`); register
  router in `app/api/main.py`. Add route + schema integration tests to
  `test_correlation_engine.py`.

- [ ] T-9.2.3 — **Frontend types + adapter**: append correlation types to
  `features/portfolio/types.ts` (`CorrelationResult`, `RollingCorrelationPoint`
  mirroring Pydantic schemas); add `runCorrelationEngine(snapshot, benchmark,
  windowDays)` to `portfolioAnalysisAdapter.ts` following the same pattern as
  `runDriftEngine`.

- [ ] T-9.2.4 — **Frontend component**: create
  `features/portfolio/RollingCorrelationChart.tsx` — Recharts `LineChart`,
  y-axis domain [-1, 1], `ReferenceLine y={0}`, null gaps via
  `connectNulls={false}`, summary stats row (β / R² / ρ₂₅₂d) below chart,
  window selector (30d / 60d / 90d). Create
  `RollingCorrelationChart.test.tsx` with 5 tests.

- [ ] T-9.2.5 — **Wire into Exposure tab**: add `correlationResult` state and
  `correlationWindowDays` state (default 60) to `App.tsx`; call
  `runCorrelationEngine` in parallel with drift in `analyzeExposureSnapshot`;
  pass correlation props to `ExposurePanel`; render `RollingCorrelationChart`
  in `ExposurePanel.tsx` beneath `IndexedReturnChart`.

- [ ] T-9.2.6 — Update `docs/product/stories/README.md` (US-9.2 Done) and
  `docs/product/epic-roadmap.md` (slice log entry). Update
  `docs/contracts/correlation-fields.md` (new contract doc).

## Out of scope

- Multi-benchmark comparison is US-9.3.
- No Spearman or Kendall correlation — Pearson only.
- No statistical significance testing (p-values, confidence intervals).
- No user-defined rolling window lengths beyond 30 / 60 / 90.

## Notes / decisions

- **Request pattern**: `CorrelationEngineRequest` should extend
  `PortfolioEngineRequest` (same as `DriftEngineRequest`) and add
  `benchmark_symbol: str` and `window_days: int` (validator: must be in
  {30, 60, 90}).
- **Portfolio return series**: reuse `build_daily_portfolio_states` from
  `app.analytics.performance` — same as drift engine. Do NOT recompute
  independently.
- **Benchmark price fetch**: same routing as drift engine — use
  `get_direct_verified_benchmark_history` for SPY; `get_historical_prices`
  for others.
- **`correlation_252d`**: a single scalar over the full 252-day (or max
  available) window, useful for the summary stats row. Computed separately
  from the rolling series.
- **Academic references**: Pearson (1895); Elton et al. (2014) Ch. 4; Hull
  (2021) §22.1 — all cited in `financial-methodology.md`.
