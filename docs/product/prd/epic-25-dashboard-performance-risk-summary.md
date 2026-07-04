# Epic 25 — Dashboard Performance & Risk Summary

**Status:** Active
**Created:** 2026-07-04

## Problem

`docs/product/current-product-state.md` and `docs/contracts/dashboard-fields.md`
both describe the Dashboard tab as showing a time-weighted-return performance
chart with benchmark comparison, a monthly returns grid, risk metrics (max
drawdown, volatility), and investor-economics status. None of this is true
today: `DashboardPanel.tsx` renders exactly three cards — Rolling Factor
Analysis, Sector composition, and Benchmark Positioning — plus import
controls. A dedicated regression test even documents the removal
(`DashboardPanel.test.tsx`: "renders the account overview shell and keeps
removed sections absent").

Git history shows this happened incrementally across several UI rewrites
(`bc4ff4d` removed the drift panel, `195dc70` removed two other sections,
`df5d478`/`e0254d6` replaced the composition view), each of which
narrowed `DashboardPanel.tsx` without a corresponding pass over
`dashboard-fields.md` or `current-product-state.md`. Contract-drift audits in
Epic 23 (US-23.5) checked schema ↔ TS type ↔ contract-doc consistency, which is
a different axis — they would not have caught "the doc describes a UI section
that no live component renders," because the underlying types and backend
fields are all still live and correct.

The backend is not the gap. `DashboardHistoryResult` (time-weighted return,
money-weighted return, net contributions, monthly returns,
`monthly_returns_reliable`, `max_drawdown_pct`, investor-economics
withholding policy) and `DiagnosticsResult` (`volatility_summary`,
`drawdown_summary`, `risk_concentration_summary` with HHI) are fully
implemented, tested, and golden-pinned — they are simply never rendered. This
is the inverse of dead code: a fully computed, contract-documented data
pipeline with no UI consumer.

## Goal

- Give the researcher a performance track record on the Dashboard tab: TWR
  index chart vs benchmark, and a summary strip (Portfolio Value, TWR, MWR,
  Net Contributions).
- Surface a monthly returns grid, hidden outright when the backend marks the
  reconstructed series unreliable (`monthly_returns_reliable = false`) —
  never shown as plausible-looking garbage.
- Surface portfolio risk (volatility, drawdown, concentration/HHI) sourced
  from the already-fetched Diagnostics engine result, which is not subject to
  the dashboard-history investor-economics withholding policy.
- Reconcile `dashboard-fields.md` and `current-product-state.md` to describe
  what actually ships, closing the documentation-drift gap identified in this
  epic's origin review.

## Non-goals

- **No backend/schema changes.** Every field this epic renders already exists
  in `DashboardHistoryResult` / `DiagnosticsResult`. If a story discovers a
  genuine missing backend field, that is a new story, not scope creep into
  this one.
- **No attempt to unlock additional investor-economics scalars.** The
  existing withholding policy (`investor_economics_status` +
  `investor_economics_partial_unlock` allowlist) is authoritative; this epic
  renders only what the policy already admits. It does not loosen or
  reinterpret the allowlist.
- **No Sharpe/Sortino/risk-adjusted-return ratio.** That is a separate
  research item (tracked outside this epic) requiring a `quant-research` brief
  before any formula is written.
- **No restoration of "Trusted Portfolio Snapshot" or "Freshness And Coverage
  Readiness"** — those were deliberately removed (`195dc70`) and are out of
  scope; this epic only restores the performance/risk/monthly-returns surface
  described (and never withdrawn) in the still-live contract docs.
- **No draft/Allocation-Overview changes** — that section (sector pie editing)
  already ships and is unrelated to this gap.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-25.1 | Performance & benchmark comparison card | Frontend — TWR index chart vs benchmark + summary strip (Portfolio Value, TWR, MWR, Net Contributions), sourced from existing `range_metrics`/`performance_series`; respects investor-economics `n/a` rules |
| US-25.2 | Monthly returns grid card | Frontend — grid from `range_metrics[*].monthly_returns`; hidden whole-card when `monthly_returns_reliable = false` |
| US-25.3 | Risk metrics card (volatility, drawdown, concentration) | Frontend — sourced from the already-fetched `DiagnosticsResult` (`volatility_summary`, `drawdown_summary`, `risk_concentration_summary`), not the withheld dashboard-history path |
| US-25.4 | Docs close-out | Docs — reconcile `dashboard-fields.md` + `current-product-state.md` to the shipped state; add the missing HHI/concentration and money-weighted-return formula sections to `financial-methodology.md` |

Recommended build order: 25.1 → 25.2 → 25.3 → 25.4 (docs close-out last, once
the shipped surface is final).

## Success signals

- A researcher opens the Dashboard tab after importing a statement and sees a
  performance chart, monthly returns, and risk metrics without navigating to
  Exposure or Risk tabs.
- `dashboard-fields.md` and `current-product-state.md` describe exactly what
  `DashboardPanel.tsx` renders — no aspirational or stale sections.
- No investor-economics withholding rule is loosened; `max_drawdown_pct` from
  dashboard-history stays withheld exactly as today, and the new risk card
  sources drawdown from the unaffected diagnostics path instead.
