# US-9.1: Indexed return time-series chart

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Done
**Last updated:** 2026-05-28

## Story

As a **portfolio researcher**, I want to see a day-by-day line chart of my
portfolio and the selected benchmark — both indexed to 100 at the start of the
window — so that I can immediately spot when my portfolio diverged from the
market, not just whether it outperformed over the full period.

## Context

US-8.9 shipped the backend drift endpoint (`/engines/drift/run`) and
`DriftResult.daily_series` type, but the frontend never rendered it. This story
adds a `DriftBenchmarkPanel` to the Exposure tab (window summary cards + indexed
return chart) and wires the drift engine call into `App.tsx`.

Implementer must read:
- `docs/finance/financial-methodology.md` — "Indexed Return Series" section
- `apps/desktop/src/features/portfolio/types.ts` — `DriftDailyPoint`, `DriftResult`

## Acceptance criteria

- [x] AC1 — The Exposure tab shows a time-series line chart below the drift
  window cards. The chart has two lines: "Portfolio" (solid) and the selected
  benchmark (dashed), both normalized to 100 at the start of the displayed
  window.
- [x] AC2 — The chart respects the active benchmark selection (SPY / QQQ / IEF
  / VT); switching the benchmark re-fetches the drift result and re-renders the
  chart.
- [x] AC3 — A window selector (Since Import / 12M / 6M / 3M / 1M) controls
  which slice of the `daily_series` is charted. The selected window start date
  determines the rebasing point (index = 100).
- [x] AC4 — Data points where `portfolio_indexed` or `benchmark_indexed` is
  null are rendered as gaps in the line (not zero, not interpolated).
- [x] AC5 — When `daily_series` is empty or the drift result is unavailable,
  the chart area shows an "Insufficient history — chart unavailable" message
  rather than a blank or a zero line.
- [x] AC6 — A "Synthetic" trust badge is visible near the chart title.
- [x] AC7 — `npx tsc --noEmit` is clean; `npx vitest run` passes.

## Test plan

Frontend (vitest):
- `IndexedReturnChart.test.tsx` — renders window selector buttons; shows
  "Insufficient history" when series is empty; shows "Insufficient history"
  when all values are null; active window button changes on click; renders
  without crash when windows array is empty.

Regression / guardrail:
- `ExposurePanel.test.tsx` — existing 10 tests stay green.
- All 97 frontend tests and 239 backend tests pass.

## Tickets

- [x] T-9.1.1 — Created `IndexedReturnChart.tsx` (Recharts LineChart; window
  selector; sliceAndRebase helper; gap rendering via connectNulls={false};
  unavailable/empty state) and `DriftBenchmarkPanel.tsx` (5 window cards +
  benchmark selector + Synthetic badge + chart integration). CSS for drift panel
  added to `styles.css`. `IndexedReturnChart.test.tsx` with 5 vitest tests.

- [x] T-9.1.2 — `App.tsx`: added `driftResult` and `driftBenchmark` state;
  `runDriftEngine` called in parallel with exposure + diagnostics in
  `analyzeExposureSnapshot`; `handleDriftBenchmarkChange` re-fetches on
  benchmark switch; `driftResult`/`driftBenchmark`/`onDriftBenchmarkChange`
  props wired to `ExposurePanel`. `ExposurePanel.tsx`: new props accepted;
  `DriftBenchmarkPanel` rendered at the top of the exposure stack.
  `npx tsc --noEmit` clean.

- [x] T-9.1.3 — Story status set to Done; README and epic-roadmap slice log
  updated.

## Out of scope

- No new backend endpoint — `daily_series` is already returned by
  `/engines/drift/run` (US-8.9).
- No zoom or pan interaction on the chart.
- No CSV export of the series.
- Rolling correlation is US-9.2.

## Notes / decisions

- **Rebasing**: `sliceAndRebase()` in `IndexedReturnChart.tsx` rebases
  `portfolio_indexed`/`benchmark_indexed` to 100 at the first non-null value
  in the selected sub-window. Formula from `financial-methodology.md` §Indexed
  Return Series: `indexed_t = (value_t / value_0) * 100`.
- **Null gap handling**: `connectNulls={false}` enforced explicitly on both
  `<Line>` components. Recharts renders `null` as a line break.
- **Drift engine is non-critical**: `runDriftEngine(...).catch(() => null)` in
  `analyzeExposureSnapshot` ensures that a drift network failure never blocks
  the exposure analysis result.
- **Academic reference**: Grinold & Kahn (2000) *Active Portfolio Management*
  Ch. 2; Bacon (2008) *Practical Risk-Adjusted Performance Measurement* Ch. 1.
