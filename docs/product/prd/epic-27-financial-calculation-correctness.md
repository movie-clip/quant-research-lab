# Epic 27 — Financial Calculation Correctness

**Status:** Active (started 2026-07-05)
**Created:** 2026-07-05
**Seeded by:** A full financial-calculations audit of the analytics + engine
layer against `docs/finance/financial-methodology.md` (2026-07-05). Findings
were recorded first (no fixes applied during the audit); this epic ticketes
the fixes.

## Problem

A line-by-line review of every implemented formula (`app/analytics/*`, the
engine services that wire them, `dashboard_history_engine.py`,
`engine/portfolio_state.py`) against the methodology doc found **13 findings**:
4 confirmed math/correctness bugs, 6 guardrail violations (fabrication /
silent-fallback / doc-vs-code divergence), and 3 low-severity consistency
gaps. None are currently caught by tests — several sit exactly in spots the
test suite asserts only null/not-null, not numeric values.

## Audit findings (canonical record)

Severity: **H** = wrong number shown to the researcher today; **M** = wrong
under realistic-but-not-universal conditions, or a hard guardrail violation;
**L** = consistency/documentation gap.

| # | Sev | Where | Finding |
|---|---|---|---|
| F1 | H | `analytics/risk.py` `build_relative_risk_summary` (~line 830) | **Information Ratio not annualized per the documented formula.** Code computes `(mean_active × √252) / TE_annualized`, which algebraically equals the *daily* IR (`mean_daily/σ_daily`). Methodology §Information Ratio specifies `(mean_active × 252) / tracking_error` — the standard annualized IR (Grinold & Kahn). Displayed IR is **under-stated by √252 ≈ 15.9×** on the Dashboard Risk Summary card (US-25.5). No numeric test pin exists (tests only assert null/not-null). |
| F2 | H | `services/dashboard_history_engine.py` `_compute_max_drawdown` (~line 826) | **Max drawdown computed on raw `portfolio_value`, not the compounded return index.** Deposits mask real drawdowns; withdrawals fabricate fake ones. Methodology (`VolatilityAssumptions.drawdown_basis = "compounded_return_index"`, §Wealth Index and Drawdown) requires the cash-flow-neutral wealth index. The diagnostics-side drawdown path does this correctly (`_build_wealth_index` on TWR returns); the dashboard-history path does not. |
| F3 | H | `services/dashboard_history_engine.py` `_compute_contribution_adjusted_monthly_returns` (~line 793) | **Monthly returns drop every month-boundary return.** Compounding resets per month group (`previous_state = None`), so the return from the last trading day of month M to the first trading day of month M+1 is never counted in any month. Monthly returns do not chain to the period TWR (Π(1+mᵢ) ≠ total), and each month is biased by omission of its first trading day. The month's first day should compound against the prior month's last state. |
| F4 | H | `analytics/risk.py` `_compute_covariance_matrix` (~line 1969) | **Covariance can be computed over misaligned dates.** Each symbol's return list is built by independently filtering `dates` to that symbol's coverage. When two symbols are missing *different* dates but end up with the *same* count, `zip` pairs returns from different dates — a silently wrong covariance. (When counts differ the cell is at least None.) Downstream: factor/position variance contributions, risk shares, top-N shares, both HHIs, `RiskConcentrationSnapshot`. Fix: intersect the date set per pair (or precompute the common grid), consistent with how `analytics/correlation.py` pairs series. |
| F5 | M | `analytics/risk.py` `build_stress_scenarios` (~line 1443) | **Missing factor loadings are zero-filled in stress projections.** `(latest_snapshot.get(factor) or 0.0) × shock` silently treats an unavailable loading as 0. `stress_engine.py` guards only the all-loadings-null case. A scenario computed from e.g. 9 of 16 loadings is presented as a full projection with no degradation. Violates the §Stress Scenarios contract rule ("unavailable stress support must return null, not fabricated zeroes"). Also note `or 0.0` conflates a *genuine* 0.0 loading with a missing one (numerically harmless, semantically wrong). |
| F6 | M | `analytics/risk.py` `build_risk_contribution_breakdown` (~line 946) vs methodology §Risk share | **Factor risk-share denominator diverges from the documented formula.** Doc: `risk_share_i = variance_contribution_i / factor_total_variance` (denominator "matching the same decomposition"). Code first computes exactly that inside `_build_factor_risk_contributions`, then **overwrites** every factor `risk_share` with `variance_contribution / total_variance_raw` (factor + specific variance). Factor shares therefore sum to `factor_risk_share_total` (< 1), and `factor_hhi` / `top_N_factor_risk_share` are computed over the rescaled values — while position shares use the position-only denominator. Either convention is defensible; code and doc must agree and the mixed-denominator HHI comparison must be called out. |
| F7 | M | `analytics/risk.py` `_orthogonalize_factors_window` (~line 1626) | **Collinear factor kept raw instead of nulled.** When a factor's Gram-Schmidt residual is ~0 (collinear with higher-priority factors in the window), the code re-inserts the **raw** series into the design matrix. The subsequent ridge OLS then splits the loading arbitrarily between the collinear pair, and later factors are orthogonalized against the raw (not residualized) series. Methodology §Per-window orthogonalization: "skip that factor's coefficient (null), do not propagate to later factors." `attribution.py` consumes the same pipeline, so attributed contributions inherit the arbitrary split. |
| F8 | M | `services/diagnostics_engine.py` `_build_synthetic_snapshot_history_states` (~line 745) and `engine/portfolio_state.py` (~line 58) | **Prices are back-filled flat before a symbol's first quote.** Dates before a symbol's history starts get `first_price` (and the state builders then treat the position as held at constant value), producing a flat segment → fabricated zero returns → understated volatility, VaR, drawdown, and distorted correlation for any portfolio holding a recently-listed symbol over a long window. Methodology: null gaps must propagate as null — "no interpolation", "never fabricate". The fix must decide the correct fail-closed behaviour (exclude symbol from the window, or shorten the window) and surface it via trust/metadata rather than silently flattening. |
| F9 | M | `engine/portfolio_state.py` `to_base_currency` (~line 70) | **Missing FX rate silently falls back to 1.0 conversion.** When `fx_history` has no rate for a non-base-currency position, the raw value is returned unconverted (EUR treated as USD). No trust degradation, no warning. `drift_engine.py` always passes `fx_history={}`, so every non-USD position in the drift path is mis-valued whenever base ≠ trading currency. Violates "never silently fallback". |
| F10 | M | `services/drift_engine.py` `_portfolio_return` (~line 29) | **Drift-window portfolio return is not cash-flow-neutral.** `last.total_market_value / first.total_market_value − 1` over states built from the **replayed ledger** (buys/sells/deposits change market value without being performance). A mid-window BUY converts cash → positions and shows up as "return"; the spread vs the benchmark is then misleading. Also the row's note claims "current holdings applied to historical prices" while the engine actually replays the ledger. Should use the TWR chain (§Portfolio Return Methodology) or the synthetic-snapshot convention — and say which. |
| F11 | L | `analytics/performance.py` `build_true_performance_series` (~line 80) | **Fabricated 0.0 return points.** When the return-basis contract is unverified, or a mid-series day has a zero previous value, the point is emitted with `portfolio_return_pct = 0.0` — rendered as a real "0% cumulative return", not an absent value. Suppression should be explicit (null / withheld), not a plausible-looking zero. |
| F12 | L | `analytics/risk.py` (sample, N−1) vs `analytics/correlation.py` + `analytics/distribution.py` (population, N) | **Two stdev conventions coexist undocumented.** β/ρ ratios are unaffected (the denominator convention cancels), but stdev-level outputs (vol, TE, DR inputs) differ slightly between surfaces for the same window. Only distribution's population choice is documented. Document the convention per surface in the methodology (or standardize). |
| F13 | L | `services/intra_correlation_engine.py` + `services/correlation_engine.py` | **(a)** DR numerator σᵢ uses each holding's own non-null dates while the denominator σ_p uses complete-case dates only — with ragged coverage the documented DR ≥ 1 guarantee can break. **(b)** These engines consume `row["price"]` directly (never `select_history_price_series`), so the return basis depends on what the provider put in `price` (Yahoo fallback sets it to adjClose; FMP light must be verified empirically). Dividend ex-date artifacts would bias correlations/DR/ENB. Verify the FMP basis and either switch to the selected-series helper or document the basis. |

**Explicitly checked and found correct** (for the record): Modified Dietz
weighting (both implementations agree with the doc and each other), historical
VaR/CVaR + the CVaR ≥ VaR invariant enforcement, NIST percentile interpolation,
skew/excess-kurtosis moments, histogram binning, wealth index + underwater
series + episode identification, drawdown episode decomposition + its
reconciliation invariant, attribution's per-date reconciliation identity +
NaN fail-closed guards, pairwise correlation matrix null semantics, ENB
eigenvalue clamping, active share / overlap weight, HHI + top-N share + 
effective holdings on the Exposure tab, tracking error, rolling vol/downside
vol, beta/ρ/R² helpers.

## Goal

Fix every H and M finding as a reviewed, test-pinned change; resolve the L
findings by fixing or documenting. Every story updates
`financial-methodology.md` and the affected contract docs in the same pass
(the project's methodology-traceability guardrail), and adds **numeric**
regression tests — the audit showed null/not-null assertions let F1-class
bugs through.

## Non-goals

- No new analytics, cards, or product surface.
- No factor-model redesign (ordering, proxies, ridge policy stay as-is).
- No importer/market-data-provider changes beyond what F13's verification
  requires.

## Story list

| Story | Title | Findings | Priority |
|---|---|---|---|
| US-27.1 | Fix the Information Ratio annualization | F1 — **Resolved 2026-07-05** | **High** |
| US-27.2 | Fix dashboard monthly-return chaining + max-drawdown basis | F2, F3 — **Resolved 2026-07-05** | **High** |
| US-27.3 | Fix covariance-matrix date alignment | F4 — **Resolved 2026-07-05** | **High** |
| US-27.4 | Stress scenarios: null semantics for missing loadings | F5 — **Resolved 2026-07-05** | Med |
| US-27.5 | Reconcile the factor risk-share denominator with the methodology | F6 — **Resolved 2026-07-05** | Med |
| US-27.6 | Null (don't keep raw) collinear factors in per-window orthogonalization | F7 — **Resolved 2026-07-05** | Med |
| US-27.7 | Stop flat back-filling synthetic history before a symbol's first quote | F8 — **Resolved 2026-07-05** | Med |
| US-27.8 | Surface FX-fallback trust + fix the drift-window return basis | F9, F10 | Med |
| US-27.9 | Low-severity tail: fabricated 0.0 points, stdev conventions, DR/return-basis consistency | F11–F13 | Low |

Recommended order: 27.1 → 27.2 → 27.3 (the three "wrong number today" fixes,
each small and independent), then 27.4/27.5/27.6 (factor-model semantics),
then 27.7/27.8 (behaviour-aware valuation changes with the widest blast
radius — goldens will shift and must be regenerated deliberately), 27.9 last.

## Success signals

- IR on the Risk Summary card matches a hand-computed
  `mean_active × 252 / TE` on the golden fixture, pinned by an exact-value test.
- Π(1 + monthly_return) reconciles to the range TWR within float tolerance,
  pinned by a property test.
- A regression test with deliberately-different missing dates proves the
  covariance matrix either aligns pairwise or returns None — never a silently
  misaligned number.
- A stress scenario with any missing loading is `status='partial'`-or-better
  semantics per the story decision — never a silent full-confidence number.
- Every H/M finding row above is marked Resolved (or explicitly re-classified
  with a written reason); the L rows are Resolved or Documented.
- `financial-methodology.md` matches the code for every touched formula; the
  deterministic suite + dead-code gate stay green; golden changes are
  deliberate, story-scoped, and explained in the slice log.
