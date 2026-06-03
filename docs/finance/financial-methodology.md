# Financial Methodology

*Updated for Epic 8 (2026-05-25): ranking/construction/optimizer/backtest methodology removed.*

This document is the project-level reference for the financial and economic methodology implemented in the codebase.

For the canonical shipped-state boundary, use `docs/product/current-product-state.md`.

## Terminology

The project uses the term `factor` rather than `quant`.

Implemented factor families include:
- `market`
- `style`
- `sector`
- `macro`

Primary implementation:
- `services/quant-engine/app/analytics/risk.py`

## Truth Classes

The project distinguishes between different financial truth classes.

- `broker-truth historical diagnostics`
  - based on imported portfolio history or explicitly available historical context
- `snapshot current-state analytics`
  - based on current holdings only
- `synthetic snapshot-history diagnostics`
  - approximate historical diagnostics built from current holdings plus external market data
- `persisted imports`
  - saved import artifacts (content-addressed, immutable); broker truth is never mutated

Relevant implementation:
- `services/quant-engine/app/services/diagnostics_engine.py`

## Trust, Degradation, Withholding, and Unavailability

This is shipped baseline behavior across diagnostics and dashboard-history.

- `verified_*`
  - the contract can make the documented trust claim for that path
- `degraded_*`
  - the engine may still compute useful outputs, but trust must be downgraded explicitly and stronger claims must stay suppressed
- `withheld`
  - broader diagnostics or replay evidence exists, but investor-economics outputs stay intentionally suppressed until return-basis requirements are justified
- `unavailable`
  - the required source inputs or trustworthy path do not exist for the requested output

Consumer rule:
- do not treat `withheld` as generic missing data
- do not backfill withheld investor-economics families through nearby diagnostics or comparison views

Import admission rule:
- `ImportAdmissionSummaryV1` is read-only reconciliation evidence for imported broker snapshots; it does not mutate broker truth, trust levels, admission state, imported values, or workspace creation
- desktop-local `ImportAdmissionReviewDispositionV1` records reviewer rationale for non-pass checks only; it is not backend truth and has no backend persistence endpoint
- numeric admission evidence must be finite-only; non-finite imported numeric inputs become unavailable/degraded evidence rather than serialized `NaN` or `Infinity`

## Market Data Basis

The project uses historical price series, benchmark series, ETF holdings, and security metadata supplied through `MarketDataService`.

Primary implementation:
- `services/quant-engine/app/services/market_data.py`

Important financial rule:
- return-based analytics should use adjusted-close or stronger total-return-equivalent inputs whenever economically required

Current shipped hardening state:
- diagnostics degrades benchmark and factor source semantics to `live_market_data_unverified_return_basis` when adjusted-close trust is not proven
- diagnostics run-level confidence degrades when those paths remain unverified
- diagnostics and dashboard-history expose grouped `section_trust` so mixed trust does not collapse into one top-line label
- investor-economics withholding is policy-driven and explicit, not a generic market-data failure

Current adjusted-close verification rule:
- a history is marked `verified_adjusted_close` only when the required loaded rows explicitly support that claim under the current code path
- absence of that proof keeps the path degraded or withheld rather than silently upgrading trust

## Portfolio Return Methodology

### Cash-flow-neutral daily returns

For historical risk and factor diagnostics, the portfolio return series is built from daily portfolio states using a cash-flow-neutral formula.

Implemented formula:

```text
daily_return_t = ((total_portfolio_value_t - external_cash_flow_t) / total_portfolio_value_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_portfolio_time_weighted_return_series(...)`

## Benchmark and Factor Return Methodology

Benchmark and factor returns are built from price series using simple daily returns.

Implemented formula:

```text
return_t = (price_t / price_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_benchmark_return_series(...)`
- `_series_to_returns(...)`

Financial rule:
- these return paths must not overclaim investor-economics trust when adjusted-close or total-return-equivalent support is not proven for the specific contract path

## Wealth Index and Drawdown

### Wealth index

```text
wealth_0 = 100
wealth_t = wealth_(t-1) * (1 + daily_return_t)
```

### Drawdown

```text
drawdown_t = (wealth_t / running_peak_t) - 1
```

### Drawdown episode identification

A drawdown *episode* is a contiguous run of `drawdown < 0` between two equal
peaks in the wealth index.

```text
Algorithm (greedy walk forward through daily drawdown series):
  state ← "at-peak"
  for each date t in chronological order:
    if state == "at-peak" and drawdown_t < 0:
      episode.peak_date    ← date of max(wealth_{0..t-1})
      episode.peak_value   ← wealth at peak_date
      episode.trough_date  ← t
      episode.trough_value ← wealth_t
      state ← "in-drawdown"
    elif state == "in-drawdown":
      if wealth_t < episode.trough_value:
        episode.trough_date  ← t
        episode.trough_value ← wealth_t
      if wealth_t >= episode.peak_value:
        episode.recovery_date   ← t
        episode.magnitude_pct   ← (trough_value / peak_value - 1) * 100
        episode.duration_days   ← trough_date - peak_date     (calendar days)
        episode.underwater_days ← recovery_date - peak_date
        emit episode
        state ← "at-peak"

At end of series, if state == "in-drawdown":
  emit incomplete episode with:
    recovery_date   = null
    underwater_days = (last_date - peak_date)
```

Edge cases:
- single-day dip (`wealth_t < wealth_{t-1}` and `wealth_{t+1} >= wealth_{t-1}`):
  episode is still emitted; `duration_days = 0`
- series length < 20: emit zero episodes; surface as `trust = 'unavailable'`

Top-N selection: sort emitted episodes by `magnitude_pct` ascending (deepest
first); return first `N` (default `N = 5`).

Academic precedent:
- Magdon-Ismail & Atiya (2004), "Maximum drawdown," *Risk Magazine*, Oct 2004
- Goldberg & Mahmoud (2017), "Drawdown: from practice to theory and back
  again," *Mathematics and Financial Economics* 11(3): 275–297

Implementation:
- `services/quant-engine/app/analytics/risk.py` —
  `_build_wealth_index(...)`, `_build_drawdown_from_return_index(...)`
- `services/quant-engine/app/analytics/drawdown.py` —
  `build_underwater_series(...)`, `identify_drawdown_episodes(...)`,
  `current_drawdown_pct(...)`, `max_drawdown_pct(...)` (Epic 13 / US-13.2),
  `decompose_drawdown_episode(...)` (Epic 15 / US-15.1)
- `services/quant-engine/app/services/drawdown_engine.py` —
  `run_drawdown_engine(...)` (wires market data → analytics)
- `services/quant-engine/app/api/routes/drawdown.py` —
  `POST /engines/drawdown/run`

Contract rule:
- `recovery_date = null` is distinct from "no episode" — it explicitly signals
  the portfolio is still under water. UI must surface this state, not collapse
  it to "no data".

### Drawdown episode decomposition

Decomposes a drawdown episode's portfolio-level magnitude into per-position
contributions using arithmetic Brinson-style attribution under the
synthetic-history convention (current holdings × historical prices, no
rebalancing).

```text
Per-position contribution:
  contribution_i  =  w_i(t_peak)  ×  r_i

where:
  w_i(t_peak)  =  V_i(t_peak) / V_p(t_peak)
                 = (q_i × p_i(t_peak)) / Σ_j (q_j × p_j(t_peak))
  r_i          =  p_i(t_trough) / p_i(t_peak) − 1
  q_i          =  synthetic quantity (current holdings; see
                  `_build_synthetic_snapshot_history_states`)
  p_i(t)       =  adjusted-close price for symbol i on date t
  V_p(t)       =  Σ_j (q_j × p_j(t))    (portfolio market value at t)
  V_i(t)       =  q_i × p_i(t)          (position i's market value at t)

  contribution_i is in decimal; the schema reports
    contribution_pct = contribution_i × 100.

Episode-level residual:
  residual_pct  =  episode.magnitude_pct
                   − Σ_i contribution_i_non_null × 100
  (sum runs over positions with non-null contribution_i only)

Reconciliation invariant:
  |episode.magnitude_pct − (Σ_i contribution_pct + residual_pct)|  <  1e-9
  The engine MUST raise rather than emit values that violate this.

Top-N selection:
  Sort decomposable positions by abs(contribution_pct) descending; keep
  first N (default N = 5). Positions ranked 6+ aggregate into a single
  `other_contribution_pct` value preserving the reconciliation.
```

Edge cases:
- `p_i(t_peak)` or `p_i(t_trough)` null: `contribution_i = null`; surface
  as `trust='unavailable'` at the contributor level — never fabricate as zero.
- `V_p(t_peak) = 0`: entire decomposition undefined →
  `decomposition_trust = 'unavailable'`.
- Cash: `r_cash = 0` ⇒ `contribution_cash = 0`; cash weight counts in the
  denominator but cash is NOT listed as a contributor (zero row adds no
  signal).
- Position added after `t_peak`: no synthetic price pre-peak ⇒
  `contribution_i = null`; portfolio residual absorbs the gap.

Synthetic-history caveat:
- The decomposition answers "given my current portfolio composition, what
  would each position have contributed during this historical episode?" —
  NOT "what each position actually contributed when this happened in my
  real account history." The latter requires ledger history with per-day
  weights, which is out of current scope.

Academic precedent:
- Brinson, Hood & Beebower (1986), "Determinants of Portfolio
  Performance," *Financial Analysts Journal* 42(4): 39–44 — foundational
  arithmetic attribution framework
- Goldberg & Mahmoud (2017) §3, "Drawdown: from practice to theory and
  back again," *Mathematics and Financial Economics* 11(3): 275–297 —
  extends drawdown theory to position-level decomposition under
  static-weight assumption
- Bertsimas, Lauprete & Samarov (2004), "Shortfall as a risk measure:
  properties, optimization and applications," *Journal of Economic
  Dynamics and Control* 28(7): 1353–1381 — coherent contribution
  measures (referenced for context; not used as the operative formula)

Contract rule:
- never fabricate a zero contribution to fill a price-data gap; surface
  `null` + per-row `trust='unavailable'` instead
- `residual_pct` is always reported (never hidden) so the UI can surface
  partial-data states
- the reconciliation identity must hold to within 1e-9; violations raise
  rather than emit inconsistent data (same discipline as the CVaR ≥ VaR
  invariant in §Value-at-Risk and Distribution)

## Volatility and Relative Risk

### Annualized realized volatility

```text
realized_vol = stdev(daily_returns) * sqrt(252)
```

### Downside volatility

```text
downside_t = min(return_t, 0)
downside_vol = stdev(downside_t) * sqrt(252)
```

### Tracking error

```text
active_return_t = portfolio_return_t - benchmark_return_t
tracking_error = stdev(active_return_t) * sqrt(252)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`

Contract rule:
- benchmark-relative outputs may be computed internally but still withheld or suppressed at the contract boundary when trust attestation is weaker than required

## Statistical Factor Model

The project implements a rolling ETF-proxy factor model.

Methodology string in code:

```text
Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `factor_model_methodology()`

### Per-window orthogonalization (corrected methodology — US-9.4)

Gram-Schmidt orthogonalization is performed **within each rolling window**, not
over the full date range. This guarantees that the orthogonalized factors are
mutually uncorrelated within the window used for regression, so each coefficient
has a clean "partial loading" interpretation.

```text
For each date t with window w = [t−w+1, t]:

  1. Slice raw factor returns to the window:
       f_k(window) = daily returns of proxy_k on dates [t−w+1, t]

  2. Gram-Schmidt within the window (orthogonalization order: market=1,
     growth=2, value=3, small_cap=4, technology=5, financials=6, ...):
       F*_1 = f_1          (Market/SPY — unmodified)
       F*_k = f_k − Σ_{j<k} (<f_k, F*_j> / <F*_j, F*_j>) × F*_j
              where <a, b> = Σ_i a_i × b_i  (inner product over the window)

  3. Ridge-stabilized OLS:
       X = [1, F*_1, ..., F*_K]       (K = active factor count)
       β = (X'X + λ·D)⁻¹ X'y
       D = diag(0, 1, 1, ..., 1)      (ridge on factor columns only)

       Ridge floor: λ = 1e-5 for all windows.
       Per-window Gram-Schmidt guarantees orthogonal factors within each window,
       so X'X is well-conditioned and a small λ provides numerical stability
       without material coefficient shrinkage. (λ=0.01 would shrink a typical
       daily-return-scale coefficient by >80% — unacceptable bias.)

  4. Reported loading for factor k = β_{k+1}
     Interpretation: unit of portfolio return per unit of orthogonalized factor k
                     after controlling for all higher-priority factors.
```

Edge cases:
- Window has fewer than `WINDOW_MIN_OBSERVATIONS[w]` dates: return null for all
  factors on that date; never partial-fill.
- A factor's orthogonalized residual has zero variance (collinear with earlier
  factors in this window): skip that factor's coefficient (null), do not
  propagate to later factors.
- R² reported per point is the in-sample OLS fit; it is diagnostic only and
  must not be used to claim out-of-sample explanatory power.

Academic precedent:
- Fama, E.F. & French, K.R. (1993). "Common risk factors in the returns on
  stocks and bonds." *Journal of Financial Economics*, 33(1), 3–56.
  (Orthogonal factor construction over the estimation window.)
- Connor, G. & Korajczyk, R. (1988). "Risk and return in an equilibrium APT."
  *Journal of Financial Economics*, 21(2), 255–289.
  (Rolling estimation consistency for factor models.)
- Bai, J. & Ng, S. (2002). "Determining the number of factors in approximate
  factor models." *Econometrica*, 70(1), 191–221.
  (Stability of factor estimates under short windows.)

Contract rule:
- factor-model and risk-contribution paths degrade explicitly when their return-basis trust is not proven
- rolling window coefficients are in-sample regression coefficients; they carry
  synthetic-history trust class (not verified), because they apply current
  holdings weights to historical price data
- a Market loading outside [−2, +4] for a long-only equity portfolio indicates
  numerical instability; the ridge floor must be sufficient to prevent this

### Sector exposure vs. factor loading — why they can diverge

**Sector exposure** (Exposure tab) and **factor loading** (Rolling Factor Analysis) measure
fundamentally different quantities and will routinely disagree. Treating a negative
Technology factor loading as evidence the portfolio is "short tech" when the Exposure tab
shows 32% Technology is a misreading of both numbers.

```text
Sector exposure  = Σ w_i  for all holdings i classified in sector S
                 = portfolio weight in that sector by current holdings composition
                 Source: snapshot analytics (holdings-based, no return history needed)

Factor loading   = β_k in the orthogonalized OLS regression:
                   r_portfolio = α + β_market·F*_market + β_growth·F*_growth
                                   + β_value·F*_value + β_small_cap·F*_small_cap
                                   + β_technology·F*_technology + ...
                 where F*_technology = XLK_returns − proj(XLK onto all prior factors)
                 = sensitivity of portfolio RETURNS to the RESIDUAL sector effect
                   after removing everything the higher-priority factors already explain
                 Source: synthetic history (returns-based, 20/60/252d rolling window)
```

**Why a negative Technology loading is compatible with a large Technology sector weight:**

The orthogonalization order places Growth (QQQ, order 2) before Technology (XLK, order 5).
QQQ (Nasdaq-100) is ~50% Technology sector companies by GICS classification and overlaps
heavily with XLK. Gram-Schmidt removes the QQQ component from XLK before Technology enters
the regression. The residual `F*_technology` then represents the *pure sector-specific* tech
move not explained by the growth/QQQ factor.

For a portfolio whose technology holdings are dominated by mega-cap names (Apple, Microsoft,
Nvidia) that also constitute the bulk of QQQ, the Growth factor absorbs most of the tech
return variation. The residual `F*_technology` effect can be small, noisy, or negative over
any given 20-day window — even when 30%+ of the portfolio is classified as Technology
by GICS.

Concretely, β_technology = −0.64 means:
  "Over the last 20 trading days, after accounting for broad market, growth-style, value,
   and size moves, the pure XLK sector effect had a mild negative relationship with this
   portfolio's daily returns."

This is not evidence of a short position or a data error. It is evidence that:
  (a) the portfolio's technology exposure is better captured by the Growth factor than by
      the residual sector factor, and/or
  (b) the specific XLK sector constituents (non-QQQ-overlap tech) moved opposite to the
      portfolio during this window.

Academic reference:
- Grinold, R.C. & Kahn, R.N. (2000). *Active Portfolio Management*, 2nd ed., Ch. 2–3
  (McGraw-Hill). (Factor loading vs. portfolio weight distinction; why holdings composition
  and return attribution diverge in orthogonalized multi-factor models.)
- Barra / MSCI factor model documentation: sector factor loadings are orthogonal to style
  factors by construction; a neutral sector loading is expected when style factors dominate
  return variation within that sector.

Consumer rule:
- Do not interpret a negative sector factor loading as a short position.
- Do not treat sector factor loading and sector holdings weight as interchangeable.
- The factor loading describes return behaviour over the rolling window; the sector
  weight describes current composition. They answer different questions.

## Risk Contribution and Concentration

The project reports position and factor risk contribution metrics plus concentration diagnostics.

Implementation:
- `services/quant-engine/app/analytics/risk.py`

Contract rule:
- diagnostics-side concentration fields are history-derived risk concentration outputs
- current-state holdings concentration remains a separate snapshot truth class in exposure contracts

## Stress Scenarios

Stress scenario returns are estimated from current factor exposures.

Conceptually:

```text
estimated_scenario_return = sum(current_factor_loading_i * shock_i)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py` —
  `build_stress_scenarios(...)` + `STRESS_SCENARIOS` constant
- `services/quant-engine/app/services/stress_engine.py` —
  `run_stress_engine(...)` (Epic 13 / US-13.1)
- `services/quant-engine/app/api/routes/stress.py` —
  `POST /engines/stress/run`

Contract rule:
- unavailable stress support must return `null`, not fabricated zeroes

## Indexed Return Series

An indexed return series re-bases portfolio and benchmark values to 100 at the
start of a window, allowing visual comparison of trajectories regardless of
absolute price or value level.

```text
indexed_t = (value_t / value_0) * 100

where:
  value_t = portfolio total_market_value or benchmark adjusted-close price on day t
  value_0 = the same on the first available trading day of the window

Edge cases:
  value_0 = 0 or null: return null for all points in the series
  value_t = null (no price for that date): emit null for that point (no interpolation)
```

Implementation:
- `services/quant-engine/app/services/drift_engine.py` — `daily_series` field
  (partially implemented; full chart rendering added in Epic 9)

Contract rule:
- Indexed series points with null values must be emitted as null, not omitted.
  The frontend renders null as a line break, not a zero.

## Rolling Pearson Correlation

Rolling correlation measures how linearly co-movement between portfolio daily
returns and benchmark daily returns evolves over time. It is the primary
statistic for determining whether a portfolio is behaving like a given market
index.

```text
rho_t(w) = cov(r_p[t-w+1 : t], r_b[t-w+1 : t])
           / (std(r_p[t-w+1 : t]) * std(r_b[t-w+1 : t]))

where:
  r_p_t  = daily portfolio return (cash-flow-neutral formula, see Portfolio Return Methodology)
  r_b_t  = (price_b_t / price_b_(t-1)) - 1  (simple daily price return)
  w      = rolling window in trading days: 20, 60, or 252
  t      = current date index in the sorted series

Range: [-1, +1]
  +1 = perfect positive co-movement
   0 = uncorrelated
  -1 = perfect inverse co-movement

Edge cases:
  std(r_p) = 0 or std(r_b) = 0: return null (constant series — no information)
  len(series) < 2: return null
  Available dates < w: return null for those prefix dates (no partial-window fill)
```

Academic precedent:
- Pearson, K. (1895). "Note on regression and inheritance in the case of two
  parents." *Proceedings of the Royal Society of London*, 58, 240–242.
- Elton, E.J., Gruber, M.J., Brown, S.J. & Goetzmann, W.N. (2014).
  *Modern Portfolio Theory and Investment Analysis*, 9th ed., Ch. 4 (Wiley).
- Hull, J.C. (2021). *Options, Futures, and Other Derivatives*, 11th ed., §22.1
  (Pearson).

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)
- `services/quant-engine/app/services/correlation_engine.py` (Epic 9)

Contract rule:
- Rolling correlation is always synthetic history trust — current holdings
  applied to historical prices. Never labelled verified.
- Null gaps in the rolling series must propagate as null fields, not be filled
  with adjacent values or zero.

## Beta (Market Beta)

Beta measures the sensitivity of portfolio returns to benchmark returns — the
slope of the OLS regression of r_p on r_b.

```text
beta = cov(r_p, r_b) / var(r_b)

where r_p and r_b are computed over the same lookback window (default: 252 trading days,
or max available if shorter).

Interpretation:
  beta > 1: portfolio amplifies benchmark moves
  beta = 1: portfolio moves in lockstep with benchmark
  0 < beta < 1: portfolio is less volatile than benchmark
  beta < 0: portfolio moves inversely to benchmark

Edge cases:
  var(r_b) = 0: return null (benchmark never moved — division undefined)
  len(series) < 20 trading days: return null (insufficient data for stable estimate)
```

Academic precedent:
- Sharpe, W.F. (1964). "Capital asset prices: A theory of market equilibrium
  under conditions of risk." *Journal of Finance*, 19(3), 425–442.
- Lintner, J. (1965). "The valuation of risk assets and the selection of risky
  investments in stock portfolios and capital budgets." *Review of Economics
  and Statistics*, 47(1), 13–37.

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)

Contract rule:
- Beta is synthetic history trust. Null when data insufficient; never
  fabricated or approximated from tracking error alone.

## R² (Coefficient of Determination)

R² measures the proportion of portfolio return variance explained by benchmark
returns. It is the square of the Pearson correlation coefficient.

```text
r_squared = rho^2

where rho is the Pearson correlation computed over the same lookback window.

Range: [0, 1]  (always non-negative regardless of correlation sign)
  R² = 0.90: 90% of portfolio variance is explained by this benchmark
  R² = 0.00: benchmark explains none of the portfolio's variance

Edge cases:
  rho = null: r_squared = null
```

Academic precedent:
- Elton et al. (2014), *Modern Portfolio Theory and Investment Analysis*, Ch. 5.
- Grinold, R.C. & Kahn, R.N. (2000). *Active Portfolio Management*, 2nd ed.,
  Ch. 2 (McGraw-Hill).

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)

Contract rule:
- R² is synthetic history trust. Reported alongside beta and correlation as a
  trio; never shown without the correlation from which it derives.

## Multi-Benchmark Correlation

A point-in-time snapshot of how the portfolio co-moves with multiple market
benchmarks over a single lookback window. Uses the formulas above —
§Rolling Pearson Correlation, §Beta (Market Beta), §R² — applied pairwise
between the synthetic portfolio return series and each benchmark's daily
price return series.

Benchmark universe (hardcoded in `services/quant-engine/app/services/correlation_engine.py`):
- SPY (S&P 500), QQQ (Nasdaq-100), GLD (Gold), IEF (US 7-10yr Bonds), VT (Global Equity)

Sort contract:
- Rows are returned ordered by `abs(correlation)` descending; rows with
  `correlation = None` (unavailable) sort last.

Edge cases:
- < 20 overlapping trading-day returns for a benchmark: `correlation`,
  `beta`, `r_squared` all null and `trust = 'unavailable'`.
- Benchmark price history not fetchable: same — null + unavailable.

Implementation:
- `services/quant-engine/app/analytics/correlation.py` — scalar helpers
- `services/quant-engine/app/services/correlation_engine.py` — orchestration + sort
- `POST /engines/correlation/multi` — route

Contract: see `docs/contracts/correlation-fields.md` (US-9.3 section) for the
field-level inventory and UI rendering rules.

## Factor Return Attribution

Factor return attribution decomposes the portfolio's daily return history into
contributions from each systematic factor and a residual (idiosyncratic + alpha)
component. Each factor's daily contribution is the product of its per-window
rolling OLS loading (β) and the orthogonalized factor return on that day.
Contributions are summed arithmetically over any selected period to produce
period-level attribution.

This is the *return* counterpart to the Rolling Factor Model: where the factor
model shows *exposures* (betas), attribution shows *realized contributions* (how
much return each exposure actually generated over the history).

### Daily factor contribution

```text
contribution_k(t) = β̂_k(w, t) × f*_k(t)

where:
  β̂_k(w, t)  = rolling OLS loading for factor k using window w ending at date t
                (output of _build_rolling_factor_loadings; see §Statistical Factor Model)
  f*_k(t)    = orthogonalized daily return of factor k on day t
                (the Gram-Schmidt residual of factor k after projecting out all
                 higher-priority factors; computed within the same window w)
  w           = rolling estimation window: 20, 60, or 252 trading days
  t           = trading date in the portfolio return history
  k           = factor index in orthogonalization order
                (market=1, growth=2, value=3, small_cap=4, technology=5,
                 financials=6, health_care=7, energy=8, industrials=9,
                 consumer_staples=10, utilities=11, consumer_discretionary=12,
                 rates_ief=13, rates_tlt=14, credit=15, commodities=16)

Units: decimal (e.g. 0.012 = 1.2%). Multiply by 100 for percentage display.
```

### Daily residual contribution

```text
residual(t) = r_p(t) − Σ_k contribution_k(t)

where:
  r_p(t) = cash-flow-neutral daily portfolio return (see Portfolio Return Methodology)
  Σ_k    = sum over all K active factors with non-null β̂_k(w, t)
```

### Period attribution (arithmetic sum)

```text
period_contribution_k(t1, t2) = Σ_{t=t1}^{t2} contribution_k(t)
period_residual(t1, t2)        = Σ_{t=t1}^{t2} residual(t)
period_portfolio_return(t1, t2) = Σ_{t=t1}^{t2} r_p(t)   [arithmetic, not compounded]

Reconciliation identity (exact by construction):
  Σ_k period_contribution_k + period_residual = period_portfolio_return
```

*Arithmetic note:* The arithmetic sum of daily contributions equals the
arithmetic sum of daily returns. It does not equal the compound return
((1+r₁)(1+r₂)…(1+rₙ) − 1). For windows ≤ 3 months the difference is negligible;
for longer windows the compounding gap widens. The engine labels all outputs
as arithmetic and the UI must communicate this to the researcher.

### Cumulative contribution series (for chart)

```text
cumul_contribution_k(t) = Σ_{s=t0}^{t} contribution_k(s)
cumul_residual(t)         = Σ_{s=t0}^{t} residual(s)
cumul_portfolio_return(t) = Σ_{s=t0}^{t} r_p(s)

where t0 = first date in the analysis window
```

### Edge cases

```text
β̂_k(w, t) = null (window not filled or factor collinear):
  → contribution_k(t) = null
  → residual(t) = null
  → that date is excluded from all period and cumulative sums

Any factor contribution null on date t:
  → exclude date t entirely from period sums and cumulative series

Period attribution null when:
  → fewer than min_window_observations dates have non-null contributions for the
     selected window (e.g. portfolio history < 20 days for 20d window)
  → emit attribution_status = 'unavailable', not fabricated zeros

Residual must never be labeled "alpha" or "skill" in UI or contracts:
  → label as "Unexplained / idiosyncratic" — contains both alpha and model error
```

Academic precedent:
- Brinson, G.P., Hood, L.R. & Beebower, G.L. (1986). "Determinants of
  portfolio performance." *Financial Analysts Journal*, 42(4), 39–44.
  (Original arithmetic performance attribution decomposition framework.)
- Fama, E.F. & French, K.R. (1993). "Common risk factors in the returns on
  stocks and bonds." *Journal of Financial Economics*, 33(1), 3–56.
  (Factor-based return decomposition and the separation of systematic vs.
  idiosyncratic return components.)
- Bacon, C.R. (2008). *Practical Portfolio Performance Measurement and
  Attribution*, 2nd ed., Ch. 8–9 (Wiley). (Arithmetic linking, residual
  interpretation, and reconciliation identities in time-series attribution.)

Implementation target:
- `services/quant-engine/app/analytics/attribution.py` (Epic 11)
- `services/quant-engine/app/services/attribution_engine.py` (Epic 11)
- `services/quant-engine/app/api/routes/attribution.py` (Epic 11)

Contract rule:
- Factor return attribution is always synthetic history trust class. Never
  labelled verified. Any field can be null; never fabricate.
- The residual field must be labelled "unexplained_pct" or "idiosyncratic_pct"
  in the schema — never "alpha_pct".
- Arithmetic attribution must carry a `methodology_note` field in the response
  explaining that sums are arithmetic, not compounded.
- The reconciliation identity (Σ contributions + residual = arithmetic portfolio
  return) must hold to floating-point precision. If it does not, the engine must
  return an error rather than emit inconsistent data.

## Value-at-Risk and Distribution

Daily return distribution analytics measured from the synthetic portfolio return
series over a lookback window. All outputs are synthetic-history trust class.

### Daily return series

```text
r_t = (wealth_t - external_cash_flow_t) / wealth_{t-1} - 1

  cash-flow-neutral, consistent with §Portfolio Return Methodology.
  series r computed over the lookback window w trading days.
  w ∈ {60, 252, 504}; default w = 252.
  calendar-day fetch = ceil(w * 1.6) + 30   (project standard heuristic)
```

### Percentiles

```text
p_q = quantile(r, q)        for q ∈ {0.05, 0.10, 0.50, 0.90, 0.95}

  NIST linear-interpolation method (numpy.quantile default).
```

### Historical Value-at-Risk

```text
VaR_α = -p_{1-α} * 100        for α ∈ {0.95, 0.99}

  reported as positive loss in percent
  e.g. VaR_95 = 2.34 means "5% of days lost ≥ 2.34%"
```

### Conditional VaR (Expected Shortfall)

```text
tail   = { r_t ∈ r : r_t ≤ p_{1-α} }
CVaR_α = -mean(tail) * 100    for α ∈ {0.95, 0.99}

  reported as positive loss in percent
  CVaR_α ≥ VaR_α by construction (coherent risk measure)
```

### Distribution shape

```text
mean = mean(r)
std  = sqrt(var(r))           (population N denominator)
skew = E[((r - mean) / std)^3]            (Fisher-Pearson)
kurt = E[((r - mean) / std)^4] - 3        (EXCESS kurtosis, Fisher)
```

### Histogram

```text
bins  = 30 (default)
range = [min(r), max(r)]      (auto-fit; no symmetric padding; no outlier trim)
```

Edge cases:
- `len(r) < 20`: every metric returns `null`; surface `trust = 'unavailable'`
- `|tail| < 2`: `CVaR_α` returns `null` (single tail sample is not a mean)
- `std = 0` (constant series): `skew`, `kurt` return `null`
- all `r ≥ 0` (no loss days in window): `VaR_α` and `CVaR_α` may be NEGATIVE
  (= "the tail day was still positive") — reported as-is, never clipped to zero

Academic precedent:
- Jorion (2007), *Value at Risk*, 3rd ed., McGraw-Hill, Ch. 5 — historical-
  simulation VaR
- Acerbi & Tasche (2002), "On the coherence of expected shortfall," *Journal
  of Banking & Finance* 26(7): 1487–1503 — CVaR / ES as a coherent risk
  measure
- Embrechts, McNeil & Frey (2015), *Quantitative Risk Management*, 2nd ed.,
  Princeton UP, Ch. 2.4 — historical vs parametric vs Monte Carlo VaR
  comparison

Implementation:
- `services/quant-engine/app/analytics/distribution.py` —
  `compute_percentiles(...)`, `compute_var(...)`, `compute_cvar(...)`,
  `compute_distribution_shape(...)`, `compute_histogram(...)` (Epic 13 /
  US-13.3; pure-Python, no numpy / scipy)
- `services/quant-engine/app/services/distribution_engine.py` —
  `run_distribution_engine(...)` (enforces `CVaR ≥ VaR` invariant)
- `services/quant-engine/app/api/routes/distribution.py` —
  `POST /engines/distribution/run`

Contract rule:
- never clip `VaR` to a positive number — a negative VaR is a meaningful
  signal that the window contained no loss days at the requested confidence
- `CVaR < VaR` is impossible by construction; if the engine emits such a
  pair it must raise rather than return inconsistent data

## Current Known Financial Limitations

At the time of writing, the main finance-related limitations are:

- some return paths still remain intentionally degraded or withheld because total-return-equivalent trust is not yet proven broadly enough to unlock stronger claims everywhere
- factor interpretation still depends on factor ordering and proxy quality

## Maintenance Rule

When any of the following changes, update this file:
- financial formulas
- methodology strings
- factor definitions
- trust, degradation, withholding, or unavailability semantics
