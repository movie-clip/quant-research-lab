# PRD: Epic 9 — Portfolio Correlation & Co-movement Analysis

**Status:** Active
**Last updated:** 2026-05-25

---

## Problem

After Epic 8, the Exposure tab shows 5 summary windows comparing portfolio
return vs a single benchmark (1M / 3M / 6M / 12M / Since Import). A portfolio
researcher can see *whether* they outperformed over a period, but cannot see:

1. **How the portfolio tracked day-by-day** — the backend already computes a
   `daily_series` of indexed returns but the UI renders nothing from it.
   Window cards tell you the endpoint; they don't show the journey.

2. **Whether the portfolio's correlation to the market is stable or drifting**
   — a portfolio might have 0.8 correlation to SPY on average but shift to 0.4
   or 0.95 in different regimes. No rolling correlation metric exists.

3. **Which market factor the portfolio most resembles** — correlation,
   beta, and R² vs SPY, QQQ, GLD, IEF, VT in one view. Without this the
   researcher must mentally compare separate drift windows across benchmark
   switches, which is error-prone and slow.

---

## Goal

- Researcher can see a **time-series chart** of portfolio vs benchmark indexed
  returns (both normalized to 100) without leaving the Exposure tab.
- Researcher can see a **rolling correlation chart** (30d / 60d / 90d rolling
  Pearson ρ) to understand regime stability.
- Researcher can see a **multi-benchmark snapshot table** (ρ, β, R² vs SPY /
  QQQ / GLD / IEF / VT) to identify which market factor their portfolio most
  resembles.

---

## Non-goals

- No predictive modelling, no forecasted correlation, no look-ahead.
- No trade signals or target-weight suggestions derived from correlation.
- No intraday data — all analysis is daily granularity.
- No factor decomposition beyond the five benchmark proxies already listed
  (the existing ETF factor model in `risk.py` handles factor loadings
  separately).
- No user-configurable benchmark universe — the five symbols are hardcoded
  (SPY, QQQ, GLD, IEF, VT).

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-9.1 | Indexed return time-series chart | Frontend chart of existing `daily_series` data |
| US-9.2 | Rolling correlation engine + chart | New backend analytics + frontend line chart |
| US-9.3 | Multi-benchmark correlation matrix | New backend endpoint + frontend comparison table |

Stories are ordered by dependency: 9.2 and 9.3 require the new `correlation.py`
analytics module introduced in 9.2 first.

---

## Success signals

- A researcher can open the Exposure tab, see the indexed return chart, and
  immediately identify a divergence event (e.g. where their portfolio
  de-correlated from SPY) without reading a number table.
- Rolling correlation chart shows at least 30 data points (30d window needs
  31 days of portfolio history, which any import with >1 month of history will
  provide).
- Multi-benchmark table loads in < 2 s on the local quant engine (all five
  benchmarks computed in a single request).
- All outputs carry a visible "Synthetic" trust badge — no metric implies
  verified return-basis attestation.

---

## Financial methodology

All formulas for this epic are defined in
`docs/finance/financial-methodology.md`:

- **Indexed Return Series** — rebases portfolio and benchmark to 100 at window
  start; null propagates as null (no interpolation).
- **Rolling Pearson Correlation** — sliding-window ρ with null for prefix dates
  where window is not yet filled.
- **Beta** — OLS slope cov(r_p, r_b) / var(r_b); null when var(r_b) = 0 or
  < 20 data points.
- **R²** — ρ²; always [0, 1]; null when ρ is null.

Trust class for all outputs: **synthetic history** (current holdings applied to
historical prices). Never fabricated, never zero-filled.

---

## Implementation notes

- The drift engine (`drift_engine.py`) already computes `daily_series` with
  `portfolio_indexed` and `benchmark_indexed`. US-9.1 renders this data — no
  new backend work needed.
- Epic 9 introduces `services/quant-engine/app/analytics/correlation.py` as a
  new analytics module (alongside the existing `risk.py`). This module
  implements rolling ρ, beta, and R².
- New route module: `app/api/routes/correlation.py` with two endpoints:
  `POST /engines/correlation/run` (single benchmark, rolling series) and
  `POST /engines/correlation/multi` (all five benchmarks, snapshot stats).
- The existing `VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST` routing in the drift
  engine applies to correlation benchmarks as well.
