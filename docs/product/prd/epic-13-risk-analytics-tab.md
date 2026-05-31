# PRD: Epic 13 — Risk Analytics Tab

**Status:** Next phase
**Last updated:** 2026-05-31

---

## Problem

The researcher can see what they own (Exposure) and what they've returned
(Dashboard), but cannot quickly answer the three core risk questions a real
research workbench needs to support:

1. **What happens to my portfolio under specific market stress scenarios?**
2. **How bad has past drawdown gotten, and how long did recovery take?**
3. **What is the realistic worst-case daily loss (statistically) I should
   plan for?**

Two of these (stress, drawdown) are quietly already computed in
`services/quant-engine/app/analytics/risk.py` (`build_stress_scenarios`,
`_build_drawdown_from_return_index`) but never surfaced. The third (VaR /
distribution) is genuinely new. A good answer to all three lets the
researcher pre-decide a risk budget (e.g. "I'll de-risk if 1-day VaR
exceeds 3% over the 60-day window") rather than reacting after the loss
has already happened.

---

## Goal

- Add a third tab, **Risk**, to the navigation (currently
  Dashboard + Exposure → becomes Dashboard + Exposure + Risk).
- Surface three risk views as cards inside the Risk tab, all backed by
  synthetic-history trust class (no fabrication, no broker-truth claim).
- Each card uses the Epic 12 design system primitives — `CardShell`,
  `TrustBadge`, `WindowSelector`, `ChartShell`, `chartDefaults`, state
  primitives — and passes the existing `designSystem.audit.test.ts`
  contract.
- Methodology doc grows by one new §Value-at-Risk and Distribution section
  and an extension to §Wealth Index and Drawdown for the episode
  identification algorithm.

---

## Non-goals

- No parametric / Monte Carlo VaR (only historical-simulation VaR).
- No user-editable stress scenarios (the 3 hardcoded are v1; a custom
  scenario editor is a future epic).
- No conditional drawdown decomposition (which positions drove the worst
  episode — out of scope; would need per-position daily returns).
- No backtest of stress projections vs realized events.
- No per-position VaR / drawdown — whole-portfolio only.
- No risk metrics for individual asset classes beyond what the existing
  factor model already covers.
- No expansion of Exposure or Dashboard tabs in this epic.

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-13.1 | Risk tab + Stress Scenarios card | Tab nav extension (`App.tsx` tab union) + `RiskPanel.tsx` scaffold + `StressScenariosCard.tsx` + `POST /engines/stress/run` route + service (delegates to existing `build_stress_scenarios`) |
| US-13.2 | Drawdown Analytics card | `app/analytics/drawdown.py` (episode identification) + `POST /engines/drawdown/run` + `DrawdownAnalyticsCard.tsx` (underwater curve + top-N episodes table) + methodology extension under §Wealth Index and Drawdown |
| US-13.3 | VaR & Distribution card | `app/analytics/distribution.py` (percentiles, VaR, CVaR, skew/kurtosis, histogram) + `POST /engines/distribution/run` + `VarDistributionCard.tsx` (histogram + percentile / tail-risk / shape table) + §Value-at-Risk and Distribution methodology |
| US-13.4 | Trust-state polish + a11y verification | Cross-card review: badge wording, null → `'—'` rendering, aria labels; small UX adjustments; no new functionality |
| US-13.5 | Docs close-out | `docs/contracts/risk-fields.md` created; methodology verified; roadmap slice log + Epic 13 closed; `current-product-state.md` Risk-tab section added; story statuses → Done |

Stories must be built in order (13.1 → 13.2 → 13.3 → 13.4 → 13.5).

---

## Success signals

- After US-13.1: a third tab is visible; clicking it shows a Risk panel
  with one card (3 scenario rows from the hardcoded `STRESS_SCENARIOS`
  table), each with a non-null `estimated_return_pct` for a portfolio
  that has at least 252 days of factor history.
- After US-13.2: the same tab adds an underwater curve chart that
  visually matches the wealth-index drawdown computed by the Dashboard,
  plus a top-5 episodes table that includes the 2020 COVID and 2022
  rate-hike drawdowns for any portfolio that lived through them.
- After US-13.3: a fresh import on a typical equity portfolio produces
  `VaR_95` in the 1.5–3.5% range and `CVaR_95` strictly larger than
  `VaR_95` (sanity check: CVaR ≥ VaR by definition; if violated, the
  implementation is wrong).
- After US-13.4: design-system audit passes; every chart has an
  `aria-label`, every nullable cell renders `'—'`, every Synthetic badge
  is the canonical primitive (not hand-rolled).
- After US-13.5: `docs/contracts/risk-fields.md` exists; a fresh
  `verify-story` run on Epic 13 emits PASS.
- All backend pytest (263 → ~+24) + frontend vitest (142 → ~+20) stay
  green throughout — exact counts set per story test plan.
