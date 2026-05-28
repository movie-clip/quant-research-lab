# US-9.2: Rolling correlation and beta chart

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Done
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

- [x] AC1 — The Exposure tab contains a new "Rolling Correlation & Beta" card
  below the Factor Attribution card. The card title includes a "Synthetic"
  trust badge.
- [x] AC2 — The card shows a line chart with two series: rolling Pearson
  correlation (left Y-axis, domain [−1, +1], reference line at y = 0) and
  rolling beta (right Y-axis, domain auto-scaled, reference line at y = 1).
- [x] AC3 — A window selector lets the researcher choose between 20d, 60d, and
  252d rolling windows. Selecting a window switches which pair of fields is
  rendered (`correlation_20d`/`beta_20d`, etc.). The default window is 60d.
- [x] AC4 — Dates where `correlation_Nd` or `beta_Nd` is null are rendered as
  visible gaps in the line — not connected, not zero-filled.
- [x] AC5 — When `rolling_risk` is empty or all values for the selected window
  are null, the chart area shows "Insufficient history for [N]d rolling window"
  rather than a blank chart or a zero-baseline line.
- [x] AC6 — The chart X-axis shows dates; the left Y-axis label reads
  "Correlation (ρ)"; the right Y-axis label reads "Beta (β)".
- [x] AC7 — A tooltip on hover shows date, correlation value (2 d.p.), and beta
  value (2 d.p.), each showing "—" if null.
- [x] AC8 — The existing Rolling Factor Analysis card and all cards above it are
  visually and functionally unchanged.
- [x] AC9 — `npx tsc --noEmit` passes with no new type errors.

## Test plan

Frontend (vitest):
- `RollingCorrelationChart.test.tsx` — 5 tests: window selector buttons render;
  "Insufficient history" shown when all 60d values null; "Insufficient history"
  shown when array empty; window switch does not show insufficient when data
  exists; "Insufficient history for 20d" when 20d selected but only 60d data
  present.

Regression / guardrail:
- No backend change; all 239 backend tests unaffected.
- All 12 frontend test files pass (102 total vitest tests).

## Tickets

- [x] T-9.2.1 — Created `RollingCorrelationChart.tsx`: Recharts `ComposedChart`
  with dual `<YAxis>` (correlation left [-1,1] with ReferenceLine y=0, beta
  right auto with ReferenceLine y=1); `connectNulls={false}` on both lines;
  `buildChartData` helper maps `RollingRiskPoint[]` to chart data keyed by
  selected window; `CorrelationTooltip` custom tooltip; `WindowSelector` (20d /
  60d / 252d, default 60d); "Insufficient history for Nd" empty state; Synthetic
  trust badge. `RollingCorrelationChart.test.tsx` with 5 vitest tests.

- [x] T-9.2.2 — `ExposurePanel.tsx`: imported `RollingCorrelationChart`; mounted
  below `FactorAttributionCard`, passing `result.rolling_risk ?? []`.
  `npx tsc --noEmit` clean.

## Out of scope

- No new backend endpoint — `rolling_risk` fields are already computed and
  returned.
- No multi-benchmark overlay — single-benchmark only. Multi-benchmark
  comparison is US-9.3.
- No Spearman or Kendall correlation — Pearson only (already computed).
- No statistical significance testing (p-values, confidence intervals).
- No rolling R² chart — R² is derivable as ρ² but is not visualised here.

## Notes / decisions

- **Data source**: `ExposureAnalysis.rolling_risk: RollingRiskPoint[]` — no
  schema or API changes required.
- **Window values**: 20d / 60d / 252d match the existing `RollingRiskPoint`
  field naming convention (`correlation_20d`, `beta_20d`, etc.).
- **Dual-axis chart**: Recharts `ComposedChart` with two `<YAxis>` — `yAxisId`
  `"correlation"` left, `"beta"` right. Each `<Line>` references its axis via
  `yAxisId`. The dual axis is necessary because correlation is bounded [-1, 1]
  while beta can exceed 1.5 for an equity-heavy portfolio.
- **Null gap handling**: `connectNulls={false}` on both `<Line>` components.
  Pass `null` directly (not `undefined`) from `buildChartData`.
- **Trust class**: Synthetic history — current holdings applied to historical
  prices. Never `verified`.
- **Academic references**: Pearson (1895); Elton, Gruber, Brown & Goetzmann
  (2014) *Modern Portfolio Theory and Investment Analysis* Ch. 4 — cited in
  `financial-methodology.md` §Rolling Pearson Correlation.
