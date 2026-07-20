# Epic 31 — Ledger Replay Correctness

**Status:** Active (created 2026-07-18)
**Created:** 2026-07-18
**Seeded by:** A defect found while scoping tech-debt **US-24.9** (the deferred
ledger-path cash de-dilution from Epic 30 / PRD F-10). Investigating the
imported ledger-replay return series surfaced a **fabricated −36.34% single-day
return** on the committed IB2026 portfolio, which inflates its reported
annualised volatility by **+79%**. Root-caused to a complete causal chain
(F-1..F-3 below), **reproduced against the frozen golden market data**
(`app/scripts/golden_market_data.json` — deterministic and network-free, so
these numbers are not a local-cache artifact). No fixes applied during
diagnosis, matching the Epic 27 / Epic 30 findings-first discipline.

## Problem

The **imported ledger-replay path** (`historical_basis="imported_portfolio_history"`)
is the truth-class the product treats as most trustworthy — it replays the
broker's own ledger rather than reconstructing synthetic history. Epic 30
deliberately kept it on the trade-safe TWR basis for exactly that reason
(US-30.5c). But the replay silently mis-states cash for the entire window and
then corrects itself in one day, so a pure **accounting adjustment is published
as performance**.

This is the F-1/F-2 defect class from Epic 30, on a different path: a fabricated
number carrying a confident trust label, with nothing warning the researcher.
It is worse here because the imported path is the one the product presents as
broker truth.

The affected series feeds the imported diagnostics fan-out — the Exposure tab's
rolling correlation & beta chart, the statistical factor model, the risk
summary, and the volatility regime. Some downstream metrics are currently
policy-gated to `null` (`_allow_diagnostics_relative_return_outputs()` returns
`False`), which limits but does **not** eliminate user-visible impact; scoping
exactly which on-screen numbers are wrong today vs withheld is part of US-31.1.

## Goal

1. **The replayed daily series is either right or honestly degraded.** Opening
   positions are valued from real prices, or the resulting uncertainty is
   surfaced — never silently absorbed into cash.
2. **No accounting adjustment is ever published as a return.** Reconciliation
   corrections are disclosed, distributed, or fail closed — not dumped into a
   single day's return.
3. **Regression-proofed**: the replay gains invariant tests that fail if cash
   drift reappears or a single-day return exceeds a plausibility bound.

## Non-goals

- No change to the *synthetic* history path (Epic 30 / US-30.5c settled it).
- No new analytics, cards, or market-data providers.
- Not US-24.9 itself (ledger-path cash de-dilution) — that remains deferred
  and should be built **after** this epic, on a trustworthy series.

## Verified findings (2026-07-18 — F-1..F-3)

Reproduced against the committed `docs/IB2026.csv` portfolio using the **frozen**
`golden_market_data.json` (deterministic, network-free). Evidence at file:line.

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F-1 | **Critical** | **Price histories are fetched only for *current* positions, but the replay reconstructs *opening* positions — so every since-sold symbol is unpriced.** `PortfolioStateEngine.build_daily_states` rolls ending positions back through BUY/SELL to derive opening positions, producing **38** opening symbols for a snapshot that holds **20** today. Market data is fetched with `[p.symbol for p in snapshot.positions]` (the 20 current holdings), so the 18 since-sold symbols have **no price rows at all**. On day 1 (2026-01-08) only **11 of 38** positions are priced; the 27 unpriced (AAPL, ACN, ASML, GOOG, NFLX, TSM, …) contribute **$0** to opening market value. | `engine/portfolio_state.py:31-60` (opening reconstruction), `:176-190` (`if market_value is not None: total_market_value += market_value` — unpriced silently contribute 0); callers fetch current-symbol history only: `services/diagnostics_engine.py:668-672`, `analytics/performance.py` (`build_daily_portfolio_states`). Reproduction: day-1 opening MV **$14,582.03** vs implied true **$50,116.24**. |
| F-2 | **Critical** | **Cash is a plug variable that silently absorbs any opening-position valuation error.** The opening cash anchor is `base_cash = starting_nav − opening_positions_value` (`portfolio_state.py:52,124`). Because F-1 undervalues opening positions by **$35,534.21**, that exact amount is absorbed into opening cash: the engine anchors **$37,799.09** where the statement implies **$2,264.88** (true ending cash $1,993.65 minus net window flow −$271.23). The error then rides **every** daily state in the window — every `total_portfolio_value` on the imported path is overstated by ~$35.5k — with **no disclosure and no fail-closed**: the states still carry full confidence. This is the same structural defect as Epic 30 F-1 (a derived cash anchor absorbing an error), which was fixed only for the *no-ledger* request path. | `engine/portfolio_state.py:52,124`; reproduction: engine opening cash **$37,799.09** vs implied **$2,264.88**, drift **$35,534.21** — exactly the F-1 undervaluation. |
| F-3 | **High** | **The terminal reconciliation converts the accumulated error into a fabricated single-day return.** `_reconcile_terminal_state_to_statement_totals` (`portfolio_state.py:254-268`) overwrites the **final** state's `total_portfolio_value` with the statement's ending NAV (and back-solves cash), correcting the whole F-2 drift at once. The return series reads that correction as performance: the last day yields **−36.34%** (with reconciliation) vs **+0.57%** (without). One fabricated day inflates annualised volatility from **36.05% → 64.55%** (**+79%**), and contaminates every rolling window (20/60/252-day) that touches 2026-06-30. Nothing marks the day as an adjustment. | `engine/portfolio_state.py:207,254-268`; reproduction (frozen data): terminal PV 99,900.94 → 63,234.80 while market value moves only 61,812.06 → 62,378.06 and `external_cash_flow = 0`. |

### Causal chain (the three findings are one defect)

```
F-1  fetch prices for CURRENT holdings only
      └─ opening reconstruction needs 38 symbols, 27 unpriced on day 1
          └─ opening positions valued $14,582 instead of ~$50,116   (−$35,534)
F-2      └─ base_cash = starting_nav − opening_value  ⇒ cash absorbs the error
              └─ opening cash $37,799 instead of $2,265; wrong ALL window
F-3          └─ terminal reconciliation snaps PV to true ending NAV on day N
                  └─ −36.34% fabricated "return"  ⇒ volatility +79%
```

### Impact map — what a user actually sees today (US-31.1 AC3)

Derived from the policy gates, which are deterministic constants:
`_allow_diagnostics_drawdown_outputs()` and
`_allow_diagnostics_relative_return_outputs()` both `return False`
(`diagnostics_engine.py:208,253`). So a subset of the corrupted series is
withheld — but **not the most prominent surfaces**.

| Metric (imported path) | Derived from the corrupted series? | Status today |
|---|---|---|
| Exposure **rolling correlation & beta** chart (`rolling_risk`) | Yes | **SURFACED — corrupted.** Ungated. Every 20/60/252-day window touching 2026-06-30 includes the fabricated −36.34% day. |
| Risk summary `portfolio_beta` / `portfolio_correlation` / `r_squared` | Yes | **SURFACED — corrupted.** Ungated (`build_portfolio_risk_summary` is not wrapped by any policy). |
| Risk summary `portfolio_volatility_pct` / `benchmark_volatility_pct` | Yes | **SURFACED — corrupted.** The +79% inflation lands here directly. |
| `statistical_factor_model` loadings / R² / residual vol | Yes | **SURFACED — corrupted.** Ungated; also propagates into `risk_contribution_breakdown` via `model`. |
| `volatility_regime.snapshot` `realized_vol_60d` / `downside_vol_60d` | Yes | **SURFACED — corrupted.** The drawdown gate nulls only the drawdown fields, not the vol fields. |
| `relative_risk` tracking error / active return / information ratio | Yes | **Gated to `null`** — protected today by the relative-return policy. |
| Drawdown family (`current_drawdown_pct`, `max_drawdown_pct`, `wealth_index`, `drawdown_pct`) | Yes | **Gated to `null`** — protected today by the drawdown policy. |

**Conclusion:** the gates do *not* contain this defect. The Exposure tab's
rolling correlation & beta chart and the risk summary's beta / correlation /
volatility are surfaced and wrong on the imported path. That sets F-1..F-3 as
genuinely user-facing, not merely internal.

*(Method note: this map is read from the gate constants and the fan-out in
`build_historical_diagnostics_result`, not from a live run — the frozen
`golden_market_data.json` covers only the dashboard pipeline's symbols, so a
full diagnostics run against it raises `FrozenMarketDataMiss` on the factor
proxies. Re-capturing the fixture to cover the factor set is itself a candidate
task for US-31.2.)*

### Examined and found correct

Recorded so a future reader knows the audit covered them:

- The **synthetic** history path is unaffected — it builds from current holdings
  forward and never reconstructs opening positions (Epic 30 / US-30.5c basis
  rule stands).
- `external_cash_flow` correctly captures only DEPOSIT/WITHDRAWAL
  (`portfolio_state.py:170-171`); the −$271.23 net window flow reconciles
  against the canonical ledger's per-type totals (BUY −96,189.29, SELL
  +85,849.30, DEPOSIT +9,963.00, DIVIDEND +122.64, WITHHOLDING_TAX −17.47,
  INTEREST +1.64, FEE −1.05).
- Every raw snapshot entry type survives into the canonical ledger (no entry
  type is dropped by `snapshot_to_ledger`) — the drift is **not** unmodeled
  ledger activity.
- `portfolio_proof.py:1299` already builds states with
  `apply_terminal_reconciliation=False`, so the proof surface is not
  contaminated by F-3.

## Story list

| Story | Title | Priority |
|---|---|---|
| US-31.1 | Findings-first audit of the imported ledger replay (this table) + scope which surfaced metrics are affected vs policy-gated | **Critical** |
| US-31.2 | *(to be scoped from US-31.1)* Fix F-1: fetch price history for the full reconstructed symbol set, not just current holdings | TBD |
| US-31.3 | *(to be scoped)* Fix F-2/F-3: stop cash absorbing valuation error — disclose or fail closed, and never publish a reconciliation adjustment as a return | TBD |

## Success signals

- The IB2026 replayed series shows **no** single-day return attributable to a
  reconciliation adjustment; annualised volatility reflects market movement
  (~36%, not ~65%).
- Opening cash reconciles to the statement's implied opening cash within a
  documented tolerance, or the degradation is surfaced with an explicit trust
  level — never silently absorbed.
- A regression test fails if replayed cash drift exceeds a bound, and if any
  replayed daily return breaches a plausibility bound.
- `run_all_tests.py` green; any golden change is deliberate and itemized
  per-family (the Epic 28 convention).
