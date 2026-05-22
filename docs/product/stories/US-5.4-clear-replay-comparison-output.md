# US-5.4: Clear replay comparison output

**Epic:** 5 — Usable Core Flow
**PRD:** [`epic-5-usable-core-flow.md`](../prd/epic-5-usable-core-flow.md)
**Status:** Done
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want **the replay comparison to lead with total
return, max drawdown, and Sharpe rather than risk-shape metrics**, so that **I
can see immediately whether the proposed allocation is better than what I hold,
before reading the methodology details**.

## Context

After a successful construction replay, the researcher sees a "Replay Summary"
comparison table inside `HypotheticalReplaySection`. That table currently shows
only seven risk-shape metrics — Annualized Volatility, Downside Volatility,
Tracking Error, Beta, Correlation, Total Turnover, and Total Cost Paid. The
backend already returns `total_return_pct`, `annualized_return_pct`,
`max_drawdown_pct`, `sharpe_ratio`, and `sortino_ratio` in every
`AllocationBacktestMetrics` payload, and their signed differences in
`AllocationBacktestComparison`, but none are in `buildSummaryRows` in
`PortfolioAllocationBacktestPanel.tsx`. The three delta-callout cards therefore
surface the biggest risk-shape delta (often "volatility dropped 1%") instead of
the most decision-relevant one ("return improved 2%"). This is a pure frontend
change — no backend route, schema, or methodology changes needed.

Implementer: read `docs/contracts/backtest-fields.md` for the
`investor_economics_status` trust guardrail. When status is `withheld`, the
backend already returns `null` for investor-economics metrics; the UI must
surface "N/A" and must not fabricate or zero-fill.

## Acceptance criteria

- [x] AC1 — When the `HypotheticalReplaySection` renders a result that has both
  `reference_result` and `comparison`, the comparison sub-section heading reads
  "Current vs Proposed" (was "Replay Summary").
- [x] AC2 — The comparison table shows Total Return, Annualized Return, Max
  Drawdown, Sharpe Ratio, and Sortino Ratio as the first five rows, before
  the existing risk-shape rows (Annualized Volatility, Downside Volatility,
  Tracking Error, Beta, Correlation, Turnover, Cost).
- [x] AC3 — Positive delta is coloured green (positive tone) for Total Return,
  Annualized Return, Sharpe Ratio, and Sortino Ratio. For Max Drawdown a
  positive delta (less-negative drawdown for the candidate) is also coloured
  green.
- [x] AC4 — When `investor_economics_status` is `withheld` on the replay
  result, the Total Return, Annualized Return, Max Drawdown, Sharpe Ratio, and
  Sortino Ratio rows each display "N/A" in all three columns (baseline,
  candidate, delta), and none of these rows appears in the delta callout cards.
- [x] AC5 — The existing "Replay Decision Readout", "Replay Metadata", equity
  curve chart, weight tables, and all diagnostics sections are unchanged.

## Test plan

Backend (pytest):
- None — pure frontend change.

Frontend (vitest):
- `PortfolioAllocationBacktestPanel.test.tsx` — assert that when
  `HypotheticalReplaySection` renders with a `hypotheticalReplayResult` whose
  embedded replay has a non-null `reference_result` and `comparison`, the text
  "Current vs Proposed" appears in the document and "Total Return" appears as a
  row label in the comparison table.
- `PortfolioAllocationBacktestPanel.test.tsx` — assert that the delta callout
  cards include a return-family delta (e.g. "+2.00%" for total return) when
  `investor_economics_status` is `{ status: 'available', reason: null }` and
  `comparison.total_return_diff_pct` is positive.
- `PortfolioAllocationBacktestPanel.test.tsx` — assert that when
  `investor_economics_status` is `withheld` on both `reference_result` and
  `candidate_result` and all investor-economics metrics are `null`, the Total
  Return and Max Drawdown rows show "N/A" in the table and do not appear in
  the delta callout cards.

Regression / guardrail:
- All existing `PortfolioAllocationBacktestPanel.test.tsx` tests (saved
  proposal readout, persisted construction artifact review, optimizer handoff
  review, constraint validation, overlay-aware replay) must stay green.
- All existing `PortfolioImprovementWorkspaceShell.test.tsx` tests must stay
  green.
- All existing `App.test.tsx` tests must stay green.
- The `buildReplayMetricRefusalLine` warning text must continue to appear when
  `investor_economics_status` is withheld.

## Tickets

- [x] T-5.4.1 — Frontend: in `PortfolioAllocationBacktestPanel.tsx`, prepend
  five new rows (total_return, annualized_return, max_drawdown, sharpe_ratio,
  sortino_ratio) to `buildSummaryRows`; update `metricDeltaTone` to colour
  these keys correctly (all five are "better when higher"); rename the "Replay
  Summary" `panel-label` inside `HypotheticalReplaySection` to "Current vs
  Proposed"; add three new `it` blocks in `PortfolioAllocationBacktestPanel.test.tsx`
  covering AC1 (heading visible), AC2+AC3 (return rows and delta tone), and AC4
  (trust-withheld suppression).

## Out of scope

- Renaming the "Saved Proposal Review", "Artifact Review Replay", or
  "Optimizer Handoff Review Replay" outer section headings — only the
  `HypotheticalReplaySection` comparison sub-heading changes.
- Adding new backend fields, routes, or Pydantic schemas — all needed metrics
  already exist in the response contract.
- Redesigning the equity curve, weight tables, or diagnostics delta sections.
- Changing the "Replay Decision Readout" provenance block or "Replay Metadata"
  card — those remain for auditability.
- Modifying any `investor_economics_status` suppression logic — the existing
  guardrail is sufficient; this story only adds rows whose null values already
  surface correctly as "N/A".

## Notes / decisions

- No new formula is introduced. `total_return_pct`, `annualized_return_pct`,
  `max_drawdown_pct`, `sharpe_ratio`, and `sortino_ratio` are already defined
  in `docs/finance/financial-methodology.md` and computed by the backend.
- `metricDeltaTone` must treat `max_drawdown` as "better when higher": the
  backend signs the diff as `candidate - baseline`, so if candidate max drawdown
  is -3% and baseline is -4%, `max_drawdown_diff_pct` = +1 — a positive delta
  means a less severe drawdown, which is an improvement.
- `sharpe_ratio` and `sortino_ratio` use format `'number'` (dimensionless
  ratios), not `'pct'`.
- The `buildReplayDeltaCallouts` function already filters rows where
  `delta == null`, so withheld investor-economics rows (which arrive as `null`
  from the backend) will automatically not appear in callouts — no new
  suppression logic needed.
- The five new rows will appear in all three compare-table contexts that call
  `buildSummaryRows`: `HypotheticalReplaySection`, `SavedProposalReadoutSection`,
  and `PersistedConstructionArtifactReviewSection` / `PersistedOptimizerHandoffReviewSection`.
  Only `HypotheticalReplaySection` gets the panel-label rename; the persisted
  review sections do not have a "Replay Summary" panel-label to rename.
