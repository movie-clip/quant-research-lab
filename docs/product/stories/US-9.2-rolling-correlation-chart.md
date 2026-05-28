# US-9.2: Rolling correlation and beta chart

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Next phase
**Last updated:** 2026-05-28

## Story

As a **portfolio researcher**, I want to see a rolling correlation and beta chart
in the Exposure tab, so that I can tell whether my portfolio's relationship to
the benchmark is stable or drifting across market regimes.

## Context

The diagnostics engine already computes rolling Pearson correlation and rolling
beta (20d, 60d, 252d windows) as part of `build_rolling_risk_series` in
`services/quant-engine/app/analytics/risk.py`. These are returned in the
`rolling_risk: RollingRiskPoint[]` field of every `DiagnosticsEngineResponse`
(and therefore `ExposureAnalysis`). The frontend receives this data today but
renders nothing from it.

This is a **frontend-only** story. No new backend analytics, endpoints, or
schemas are required. The existing `RollingRiskPoint` type in
`apps/desktop/src/features/portfolio/types.ts` already carries
`correlation_20d`, `correlation_60d`, `correlation_252d`, `beta_20d`,
`beta_60d`, and `beta_252d`.

Implementer must read:
- `docs/finance/financial-methodology.md` — "Rolling Pearson Correlation" and
  "Beta" sections for the exact window-fill and null-propagation rules
- `apps/desktop/src/features/portfolio/types.ts` — `RollingRiskPoint`,
  `ExposureAnalysis.rolling_risk`

## Acceptance criteria

- [ ] AC1 — The Exposure tab contains a new "Rolling Correlation & Beta" card
  below the Rolling Factor Analysis card. The card title includes a "Synthetic"
  trust badge.
- [ ] AC2 — The card shows a line chart with two series: rolling Pearson
  correlation (left Y-axis, domain [−1, +1], reference line at y = 0) and
  rolling beta (right Y-axis, domain auto-scaled, reference line at y = 1).
- [ ] AC3 — A window selector lets the researcher choose between 20d, 60d, and
  252d rolling windows. Selecting a window switches which pair of fields is
  rendered (`correlation_20d`/`beta_20d`, etc.). The default window is 60d.
- [ ] AC4 — Dates where `correlation_Nd` or `beta_Nd` is null are rendered as
  visible gaps in the line — not connected, not zero-filled.
- [ ] AC5 — When `rolling_risk` is empty or all values for the selected window
  are null, the chart area shows "Insufficient history for [N]d rolling window"
  rather than a blank chart or a zero-baseline line.
- [ ] AC6 — The chart X-axis shows dates; the left Y-axis label reads
  "Correlation (ρ)"; the right Y-axis label reads "Beta (β)".
- [ ] AC7 — A tooltip on hover shows date, correlation value (2 d.p.), and beta
  value (2 d.p.), each showing "—" if null.
- [ ] AC8 — The existing Rolling Factor Analysis card and all cards above it are
  visually and functionally unchanged.
- [ ] AC9 — `npx tsc --noEmit` passes with no new type errors.

## Test plan

Frontend (vitest):
- `RollingCorrelationChart.test.tsx` — renders two series when `rolling_risk`
  has non-null 60d values; asserts SVG path elements for both correlation and
  beta lines
- `RollingCorrelationChart.test.tsx` — renders a gap (no line segment) when a
  `correlation_60d` value is null; asserts the null point is not plotted as zero
- `RollingCorrelationChart.test.tsx` — renders unavailable state text
  ("Insufficient history") when all `correlation_60d` values in the series are
  null
- `RollingCorrelationChart.test.tsx` — window selector switches series:
  selecting 20d renders `correlation_20d`/`beta_20d`; selecting 252d renders
  `correlation_252d`/`beta_252d`
- `RollingCorrelationChart.test.tsx` — tooltip shows "—" for a date where
  `beta_60d` is null

Regression / guardrail:
- No backend change; all backend tests are unaffected
- Existing Rolling Factor Analysis card tests must remain green
- `python scripts/run_all_tests.py` must stay green

## Tickets

- [ ] T-9.2.1 — **Frontend component**: create
  `apps/desktop/src/features/portfolio/RollingCorrelationChart.tsx` — Recharts
  `ComposedChart` with two `<Line>` series (correlation, beta), dual
  `<YAxis>` (left for correlation domain [-1,1] with `ReferenceLine y={0}`,
  right for beta with `ReferenceLine y={1}`), `connectNulls={false}` on both
  lines, window selector (20d / 60d / 252d, default 60d), unavailable/empty
  state, Synthetic trust badge. Create `RollingCorrelationChart.test.tsx` with
  5 tests.

- [ ] T-9.2.2 — **Integration**: mount `RollingCorrelationChart` in the
  Exposure tab below the Rolling Factor Analysis card; pass
  `ExposureAnalysis.rolling_risk` from existing state; verify
  `npx tsc --noEmit` is clean.

## Out of scope

- No new backend endpoint — `rolling_risk` fields are already computed and
  returned.
- No multi-benchmark overlay — this chart is single-benchmark (vs the
  benchmark used for the diagnostics run, typically SPY). Multi-benchmark
  comparison is US-9.3.
- No Spearman or Kendall correlation — Pearson only (already computed).
- No statistical significance testing (p-values, confidence intervals).
- No rolling R² chart — R² is derivable as ρ² but is not visualised here.

## Notes / decisions

- **Data source**: `ExposureAnalysis.rolling_risk: RollingRiskPoint[]` — already
  in `apps/desktop/src/features/portfolio/types.ts`. No schema or API changes.
- **Window values**: 20d / 60d / 252d match the existing `RollingRiskPoint`
  field naming convention. The PRD originally said 30d/60d/90d but those windows
  do not exist in the backend — 20d/60d/252d are the computed windows.
- **Dual-axis chart**: Recharts `ComposedChart` with two `<YAxis>` (yAxisId
  `"correlation"` left, `"beta"` right). Each `<Line>` references its axis via
  `yAxisId`. The dual axis is necessary because correlation is bounded [-1, 1]
  while beta can exceed 1.5 for an equity-heavy portfolio.
- **Null gap handling**: `connectNulls={false}` (Recharts default). Pass `null`
  directly, not `undefined`.
- **Trust class**: Synthetic history — current holdings applied to historical
  prices. Never `verified`.
- **Academic references**: Pearson (1895); Elton, Gruber, Brown & Goetzmann
  (2014) *Modern Portfolio Theory and Investment Analysis* Ch. 4 — cited in
  `financial-methodology.md` §Rolling Pearson Correlation.
