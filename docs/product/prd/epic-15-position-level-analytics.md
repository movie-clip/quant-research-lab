# PRD: Epic 15 — Position-Level Analytics

**Status:** Active
**Last updated:** 2026-06-01

---

## Problem

After Epic 13 shipped the Risk tab, the researcher can see what their
worst drawdown was, what scenarios threaten them, and where the
return distribution sits — all at PORTFOLIO level. The natural
follow-up question on every Risk card — "which of my positions
drove that?" — has no answer on screen. Similarly, the Exposure
tab's factor model shows TODAY's factor loadings but the rolling
loading time series (already computed by the statistical factor
model) is never visualized, so researchers can't see how their
factor mix has drifted over time.

Both gaps prevent rebalancing decisions: "is my -24% drawdown a
two-stock concentration problem or a broad market move?" and
"has my Technology exposure crept from 15% to 35% over the year?"
— each maps directly to whether a researcher should trim, add, or
hold a position.

---

## Goal

- Decompose each top-N drawdown episode into per-position
  contributions, surfaced as an expandable drawer in the existing
  DrawdownAnalyticsCard.
- Visualize the existing rolling factor loadings as a new card on
  the Exposure tab, with a 20d / 60d / 252d window selector.
- Preserve the synthetic-history trust class throughout (current
  holdings × historical prices); never fabricate to fill data gaps.

---

## Non-goals

- No per-position decomposition for VaR / CVaR / stress scenarios
  (potential Epic 16; same Brinson pattern applies but each is its
  own story).
- No real-ledger-based attribution (requires ledger history with
  per-day weights; out of current product scope).
- No per-position contribution to factor loadings ("which positions
  drove the Technology loading change?"). Different decomposition
  family (cross-sectional regression-based); future.
- No custom decomposition windows / user-defined date ranges (UX
  scope creep; v1 uses the episode's peak→trough range).
- No new factor-loading-drift visualization. **US-15.3 was
  cancelled during the cycle** (2026-06-04) after discovery
  that `RollingFactorLoadingsCard` already ships on the
  Dashboard tab and visualizes
  `ExposureAnalysis.statistical_factor_model.rolling_loadings_*`
  as a multi-line time series with the same 20d/60d/252d
  window selector, factor-group filter, and per-factor
  toggle. The use case the brief targeted ("researcher sees
  how factor mix has drifted over time") is met by the
  existing card. A future Epic could refactor it to use the
  Epic 12 design system + add it to the Exposure tab, or
  add a complementary "Factor Drift Summary" delta-indicator
  card — left as backlog candidates.

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-15.1 | Drawdown decomposition engine + schema | Backend: extend `app/analytics/drawdown.py` with `decompose_drawdown_episode(daily_states, episode, top_n=5)`; extend `DrawdownEpisode` Pydantic schema with `top_contributors`, `other_contribution_pct`, `decomposition_residual_pct`, `decomposition_trust`; wire into `drawdown_engine.run_drawdown_engine` so every episode in the response carries decomposition. Pytest covers the formula, reconciliation invariant, partial-data trust state, and cash handling. |
| US-15.2 | Drawdown card "Contributors" drawer | Frontend: extend `DrawdownAnalyticsCard.tsx` to render an expandable per-episode drawer (Symbol / Weight @ Peak / Return / Contribution columns, plus "Other (N positions)" aggregate row and "Residual" row when applicable). New TS types in `types.ts`. Vitest covers the drawer interaction, partial-trust caption, and reconciliation render. |
| US-15.3 | ~~Factor loading drift chart (Exposure tab)~~ | **Cancelled 2026-06-04**: existing `RollingFactorLoadingsCard` on Dashboard tab already covers the use case. No work shipped under this story; numbering preserved for audit trail. |
| US-15.4 | Epic 15 docs close-out | Docs: extend `docs/contracts/risk-fields.md` with the decomposition fields under the Drawdown section; verify methodology subsection `### Drawdown episode decomposition` matches shipped code; update `current-product-state.md` with the Drawdown card Contributors drawer; flip Epic 15 → Completed in roadmap. (Originally scoped to also cover the factor drift chart from US-15.3; that scope dropped when US-15.3 was cancelled.) |

Stories must be built in order (15.1 → 15.2 → 15.3 → 15.4).
US-15.2 depends on US-15.1's schema extension; US-15.3 is
independent of 15.1/15.2 but the slice log reads cleaner if all
four land sequentially.

---

## Success signals

- **After US-15.1:** `POST /engines/drawdown/run` on a real
  portfolio returns episodes whose `top_contributors` list has
  up to 5 entries with `contribution_pct` values summing (with
  `other_contribution_pct` + `decomposition_residual_pct`) to
  within 1e-9 of `magnitude_pct`. Backend pytest: +7 green.

- **After US-15.2:** clicking the expand toggle on the 2020 COVID
  drawdown row reveals the top-5 contributors — for a typical
  US-equity portfolio this surfaces concentration (e.g. the top
  3 holdings make up most of the drawdown). The "Residual" row
  appears only when `decomposition_trust = 'partial'` (some
  positions had missing prices). Frontend vitest: +6 green.

- **After US-15.3:** the Exposure tab gains a new card that
  shows 12+ factor lines over the selected window (when data is
  available), with the existing factor color palette and a
  "Synthetic" Trust badge. Window selector cycles 20d / 60d /
  252d; chart re-renders with the matching `rolling_loadings_*`
  series. Frontend vitest: +5 green.

- **After US-15.4:** `docs/contracts/risk-fields.md` includes
  the full decomposition field inventory under the Drawdown
  section; the methodology audit confirms the
  `### Drawdown episode decomposition` subsection matches the
  shipped `decompose_drawdown_episode(...)` signature;
  `current-product-state.md` mentions both new surfaces.

- All previously Done tests stay green throughout (321 backend +
  191 frontend baseline); design-system audit 5/5 throughout.
