# US-9.1: Indexed return time-series chart

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Next phase
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want to see a day-by-day line chart of my
portfolio and the selected benchmark — both indexed to 100 at the start of the
window — so that I can immediately spot when my portfolio diverged from the
market, not just whether it outperformed over the full period.

## Context

US-8.9 shipped a drift panel with 5 summary window cards and a
`DriftResult.daily_series` field (array of `{date, portfolio_indexed,
benchmark_indexed}`) that the backend already returns. The UI currently renders
only the summary cards — the time-series data is fetched but not displayed.
This story adds a Recharts `LineChart` below (or replacing) the cards.

Implementer must read:
- `docs/finance/financial-methodology.md` — "Indexed Return Series" section
- `docs/contracts/drift-fields.md` (if it exists; otherwise the Pydantic schema
  in `app/schemas/drift.py` is the contract)

## Acceptance criteria

- [ ] AC1 — The Exposure tab shows a time-series line chart below the drift
  window cards. The chart has two lines: "Portfolio" (solid) and the selected
  benchmark (dashed), both normalized to 100 at the start of the displayed
  window.
- [ ] AC2 — The chart respects the active benchmark selection (SPY / QQQ / IEF
  / VT); switching the benchmark re-fetches the drift result and re-renders the
  chart.
- [ ] AC3 — A window selector (Since Import / 12M / 6M / 3M / 1M) controls
  which slice of the `daily_series` is charted. The selected window start date
  determines the rebasing point (index = 100).
- [ ] AC4 — Data points where `portfolio_indexed` or `benchmark_indexed` is
  null are rendered as gaps in the line (not zero, not interpolated).
- [ ] AC5 — When `daily_series` is empty or the drift result is unavailable,
  the chart area shows a "No data available" message rather than a blank or a
  zero line.
- [ ] AC6 — A "Synthetic" trust badge is visible near the chart title.
- [ ] AC7 — `npx tsc --noEmit` is clean; `npx vitest run` passes.

## Test plan

Frontend (vitest):
- `IndexedReturnChart.test.tsx` — renders two lines when `daily_series` has
  data; gap on null `portfolio_indexed`; "No data available" message when
  series is empty; benchmark label updates when benchmark prop changes;
  window selector slices series to correct start date.

Regression / guardrail:
- `DriftBenchmarkPanel.test.tsx` — existing 6 tests must stay green (this story
  must not change the summary card rendering).
- `ExposurePanel.test.tsx` — existing 16 tests must stay green.

## Tickets

- [ ] T-9.1.1 — Add `IndexedReturnChart.tsx`: Recharts `LineChart` that accepts
  `series: DriftDailyPoint[]`, `portfolioLabel: string`,
  `benchmarkLabel: string`, and `windowStartDate: string | null`.
  Slice `series` to entries ≥ `windowStartDate`; rebase the slice to 100 at
  the first non-null point. Render null values as gaps (Recharts
  `connectNulls={false}`). Include `IndexedReturnChart.test.tsx` with 5 tests.

- [ ] T-9.1.2 — Add window selector state to `DriftBenchmarkPanel.tsx`:
  a `selectedWindow` toggle (Since Import / 12M / 6M / 3M / 1M) that slices
  the `daily_series` and passes the appropriate `windowStartDate` to
  `IndexedReturnChart`. The five window start dates come from `DriftResult.windows`
  (each `DriftWindow` has a `start_date` field). Render
  `IndexedReturnChart` below the existing window cards, wrapped in the same
  panel. Add 2 vitest tests to `DriftBenchmarkPanel.test.tsx`.

- [ ] T-9.1.3 — Update `docs/product/stories/README.md` (US-9.1 Done) and
  `docs/product/epic-roadmap.md` (slice log entry).

## Out of scope

- No new backend endpoint — `daily_series` is already returned by
  `/engines/drift/run` (US-8.9).
- No zoom or pan interaction on the chart.
- No CSV export of the series.
- Rolling correlation is US-9.2.

## Notes / decisions

- **Recharts** is the charting library in use (see `apps/desktop/package.json`).
  If Recharts is not yet installed, add it in T-9.1.1 before the component.
- **Rebasing**: the rebasing (dividing by the first value × 100) must happen
  inside the component, not in the backend, to allow the window selector to
  rebase to different start dates without a new fetch.
- **Null gap handling**: Recharts renders null as a gap when
  `connectNulls={false}` (the default). Confirm this is set explicitly.
- **Academic reference**: "Indexed Return Series" formula in
  `financial-methodology.md` — `indexed_t = (value_t / value_0) * 100`.
