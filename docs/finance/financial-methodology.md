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

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_build_wealth_index(...)`
- `_build_drawdown_from_return_index(...)`

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

Core mechanics:
- factor proxy returns use simple daily returns on the selected history price series
- later factors are orthogonalized against earlier factors in configured order
- regression uses a very light ridge stabilization term
- rolling windows currently include `20d`, `60d`, and `252d`

Contract rule:
- factor-model and risk-contribution paths degrade explicitly when their return-basis trust is not proven

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
- `services/quant-engine/app/analytics/risk.py`
- `build_stress_scenarios(...)`

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
  w      = rolling window in trading days: 30, 60, or 90
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
