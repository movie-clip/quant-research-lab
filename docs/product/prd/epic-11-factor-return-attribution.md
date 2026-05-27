# Epic 11 — Factor Return Attribution

**Status:** Proposed
**Last updated:** 2026-05-27

---

## Problem

The researcher can see *what* their portfolio is exposed to (factor loadings from the Rolling Factor Analysis card) but cannot see *how much return* each exposure actually generated over any historical window. A beta of 0.8 to Market tells you the portfolio amplifies market moves, but not whether that amplification produced +2% or −1% over the past month. The Dashboard shows total portfolio return as a single number. There is currently no view connecting the factor model to realized return decomposition.

This means the researcher cannot answer the most fundamental performance question: "Did my returns come from the market going up, from a deliberate growth tilt, from rate exposure, or from something the factor model doesn't explain?" Without this, every positive-return period is opaque — it is impossible to distinguish a market-beta gift from a genuine active-positioning contribution.

---

## Goal

- Researcher can select a rolling window (20d / 60d / 252d) and see each factor's cumulative contribution to portfolio return as a line chart, alongside a residual (unexplained) line.
- Researcher can read a period attribution table showing: factor name, average β over the period, factor's own return, and the factor's contribution to portfolio return — with arithmetic total reconciled to portfolio return.
- All outputs carry a "Synthetic" trust badge. The residual is never labelled "alpha."
- The feature is additive — no existing Dashboard or Exposure behavior is changed.

---

## Non-goals

- **No geometric/compounded attribution.** Arithmetic linking only. Carino or Modified Dietz smoothing are explicitly out of scope.
- **No position-level attribution.** This decomposes returns by *factor*, not by individual holding (Brinson-style security attribution is a separate epic).
- **No forward-looking attribution** or scenario attribution. Historical realized data only.
- **No new data sources.** Attribution reuses factor proxy prices already fetched for the factor model; no additional FMP calls.

---

## Story list

| Story | Title | One-line scope |
|---|---|---|
| US-11.1 | Attribution engine + endpoint | New `build_factor_attribution()` in `analytics/attribution.py`; new Pydantic schema; new `/api/engines/attribution/run` route; full pytest coverage |
| US-11.2 | Attribution card (chart + table) | New `FactorAttributionCard` in the Exposure tab: cumulative line chart, window selector, period attribution table; full vitest coverage |
| US-11.3 | Docs, contracts, roadmap close-out | Update `financial-methodology.md`, create `docs/contracts/attribution-fields.md`, update `epic-roadmap.md` slice log, set all stories to Done |

---

## Success signals

- A researcher who imports an IB 2026 statement and opens the Exposure tab can immediately see, for the 60d window, which factors drove positive vs. negative cumulative contributions over the past year.
- The arithmetic sum of all factor contributions + residual matches the arithmetic portfolio return shown in the table footer, to two decimal places.
- The card shows a "Synthetic" badge prominently. Hovering the badge produces the tooltip: "Returns are reconstructed from current holdings and historical factor proxy prices."
- With fewer than 20 trading days of history, the card shows an explicit "Not enough history" state — never a blank or a zero chart.

---

## Research Brief reference

See `docs/finance/financial-methodology.md` §Factor Return Attribution for:
- All formulas (daily contribution, residual, period arithmetic sum, cumulative series)
- Edge-case rules (null propagation, min observations, reconciliation identity)
- Academic citations (Brinson et al. 1986; Fama & French 1993; Bacon 2008)
- Trust-class analysis (all outputs: synthetic history, never verified)

The implementation in `_build_rolling_factor_loadings` (risk.py) already computes the per-window orthogonalized factor returns internally. The attribution engine needs to capture `f*_k(t)` — the last value in each window's orthogonalized series — alongside the β coefficient, then multiply them.

---

## Key implementation constraint

The `_build_rolling_factor_loadings` function already has everything needed:
- It runs `_orthogonalize_factors_window(raw_window)` to get per-window orthogonalized factors
- The last element of each orthogonalized series is `f*_k(t)` for date `t`
- It already extracts `coefficients[position + 1]` as the rolling β

The attribution engine should either:
(a) Add a new `build_factor_attribution()` function that mirrors `_build_rolling_factor_loadings` but also captures `orthogonalized_window[-1]` values as the orthogonalized factor returns, or
(b) Refactor `_build_rolling_factor_loadings` to optionally return the orthogonalized factor returns alongside the loading points.

Option (a) is preferred to avoid changing the existing tested path.
