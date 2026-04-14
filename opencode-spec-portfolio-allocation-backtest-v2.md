# OpenCode Spec: Portfolio Allocation Backtest v2 (Institutional-Grade)

```text
Implement a new `Portfolio Allocation Backtest` feature for the project using a more professional portfolio-construction standard than the existing strategy research backtest.

Important product constraint:
- Do NOT add text explanations, analyst commentary, interpretations, educational copy, or recommendation text
- Only provide raw metrics, structured assumptions, configuration controls, and charts/tables
- The user will interpret the results manually

Goal:
Create a true holdings-based historical allocation replay engine for long-only portfolio construction and portfolio comparison.

This feature should model a portfolio of weighted assets through time using adjusted prices, explicit rebalancing rules, execution lag, and transaction costs.

This is NOT:
- a factor what-if simulator
- a signal-based strategy backtest
- a replay of the user’s actual historical holdings unless historical holdings-by-date are available

If the portfolio is derived from a current imported snapshot, treat it as a counterfactual `as-of-now allocation replay` over history.

================================
PROFESSIONAL MODELING PRINCIPLES
================================

The implementation must follow these controls:

1. No look-ahead bias
- rebalance decisions must be based only on information available before execution
- do not compute drift using day `t` close and also execute at day `t` close

2. Adjusted price basis
- use adjusted close or total-return-equivalent series whenever available
- if only raw closes are available, either reject the run or return a structured degraded-status flag according to a deterministic rule

2a. EU/UCITS realism
- for historical portfolio backtests, use the actual tradable instruments specified by the user or imported portfolio, including UCITS ETFs where applicable
- do not silently replace tradable UCITS instruments with US analytical proxies inside the backtest engine
- analytical proxies such as `SPY`, `QQQ`, `XLF`, or `TLT` may still be used in separate exposure or factor-model workflows, but not as hidden substitutions for historical allocation replay

3. Explicit execution convention
- signal/decision date and execution date must be separable
- use a fixed daily-bar execution convention

Recommended v1 professional convention:
- evaluate rebalance condition on date `t`
- execute on next available valuation date `t+1`
- execute using `close` on `t+1`

4. Long-only, unlevered v1
- all target weights must be >= 0
- total target weights must sum to approximately 1.0
- no margin, no leverage, no shorting in v1

5. Counterfactual clarity
- if the portfolio comes from the currently imported snapshot, do not present results as realized account history
- treat it as a hypothetical historical replay of current target weights

6. Deterministic calendar policy
- use one clearly defined valuation calendar policy
- apply the same policy to candidate, reference, and benchmark series before comparison

7. Pre-tax disclosure
- treat the backtest as `pre-tax` in v2
- do not attempt to model Spain-specific tax treatment, withholding tax drag, or realized capital gains taxation unless a dedicated tax layer is added later
- expose tax treatment explicitly as structured assumptions metadata

================================
PRODUCT SCOPE
================================

Required workflows:

1. Reference Allocation Replay
- derive weights from imported portfolio snapshot
- replay as a counterfactual historical allocation

2. Candidate Allocation Replay
- user provides target weights
- replay on same date range and benchmark

3. Reference vs Candidate Comparison
- run both portfolios on identical aligned calendars and assumptions
- return structured comparison metrics only

Do NOT include factor-delta simulation in this ticket.

================================
BACKEND ARCHITECTURE
================================

Relevant files to inspect and update:
- `services/quant-engine/app/backtests/engine.py`
- `services/quant-engine/app/schemas/research.py`
- `services/quant-engine/app/services/`
- `services/quant-engine/app/api/routes/`
- related tests under `services/quant-engine/app/tests/`

Recommendation:
- do NOT overload the existing strategy research engine
- add a separate portfolio allocation replay engine

Suggested new backend components:
- `services/quant-engine/app/backtests/portfolio_engine.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`

Suggested route:
- `POST /backtests/portfolio-allocation`

================================
INPUT MODEL
================================

Required input fields:

1. Portfolio definition
- `portfolio_name`
- `weights`: array of `{ symbol, target_weight }`

2. Optional comparison portfolio
- `reference_weights`: array of `{ symbol, target_weight }` optional

3. Date range
- `start_date`
- `end_date`

4. Benchmark
- `benchmark_symbol`

5. Capital
- `initial_capital`

6. Rebalance controls
- `rebalance_frequency`: `none` | `monthly` | `quarterly`
- `drift_tolerance_pct`: optional

7. Transaction cost model
- `commission_bps`
- `slippage_bps`

8. Execution assumptions
- `price_basis`: `adjusted_close`
- `execution_price_field`: `close`
- `execution_lag_days`: integer, default `1`

9. Base currency
- align with project conventions
- use existing FX history logic if needed

10. Instrument metadata
- where available, track for each instrument:
  - `trading_currency`
  - `instrument_base_currency`
  - `currency_hedged`
  - `distribution_policy`

Suggested values:
- `currency_hedged`: `true` | `false` | `null`
- `distribution_policy`: `accumulating` | `distributing` | `unknown`

Suggested request models:

```python
class PortfolioWeightInput(BaseModel):
    symbol: str
    target_weight: float
```

```python
class PortfolioAllocationBacktestRequest(BaseModel):
    portfolio_name: str | None = None
    weights: list[PortfolioWeightInput]
    reference_weights: list[PortfolioWeightInput] | None = None
    benchmark_symbol: str = "SPY"
    start_date: date
    end_date: date
    initial_capital: float = 100000.0
    rebalance_frequency: Literal["none", "monthly", "quarterly"] = "monthly"
    drift_tolerance_pct: float | None = None
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
```

Validation rules:
- weights must not be empty
- all weights must be finite
- each target weight must be >= 0
- target weights must sum to approximately 1.0 within a small tolerance, e.g. 0.999 to 1.001
- `reference_weights` follow the same validation rules
- end date must be on or after start date
- initial capital must be positive
- `execution_lag_days` must be >= 1 in v2 to avoid same-bar look-ahead when only daily data is available

================================
DATA AND CALENDAR POLICY
================================

1. Price series
- use adjusted close history for every portfolio asset and benchmark
- returns must reflect splits and cash distributions

1a. Distribution policy rule
- if an ETF is distributing, adjusted or total-return-equivalent price history is required for a professional-quality total-return backtest
- if such history is unavailable, either reject the run or return a deterministic degraded status

1b. Hedge status rule
- do not assume that an ETF listed in EUR is EUR-hedged
- distinguish listing/trading currency from actual currency exposure when metadata is available

2. Valuation calendar
- preferred v2 rule: use intersection of valid adjusted-price dates across all tested assets and benchmark after applying start/end filters
- run reference and candidate on the same final aligned calendar before computing comparison metrics

3. Missing data
- do not forward-fill across missing trading dates in v2
- if an instrument lacks sufficient history for the requested period, either:
  - reject the request, or
  - deterministically shorten the usable period for all portfolios and benchmark to the common valid window
- whichever rule is chosen must be encoded as structured metadata and used consistently

4. FX conversion
- convert all non-base-currency prices using aligned FX series before valuation
- do not mix local-currency and base-currency returns

5. Benchmark selection
- benchmark must be user-configurable
- do not force a US default benchmark inside the engine when the user supplies another benchmark
- if the portfolio uses EU-traded UCITS ETFs, the benchmark can still be a US proxy or a UCITS benchmark proxy, but it must be explicit in the request and payload

================================
ENGINE MECHANICS
================================

Implement a true portfolio replay engine with these steps:

1. Determine aligned start date
- after all asset, benchmark, and FX series are aligned
- use the first valid execution date that satisfies the chosen calendar policy

2. Initial funding
- allocate initial capital to target weights at the first execution date
- allow fractional shares in v2
- retain residual cash after trading costs and numerical rounding

3. Daily valuation
- on each valuation date, compute:
  - asset market values
  - cash balance
  - total equity
  - gross exposure
  - realized weights

4. Rebalance schedule
- `none`: no rebalancing after initial allocation
- `monthly`: evaluate on month-end or chosen month rebalance dates using current valuation calendar, execute after lag
- `quarterly`: same approach for quarter-end schedule

Professional implementation rule:
- pick one deterministic schedule convention and keep it fixed, preferably:
  - schedule decision on the last valuation date of the period
  - execute on the next available valuation date after the configured lag

5. Drift-based trigger
- if `drift_tolerance_pct` is set, evaluate pre-trade realized weights on decision dates
- if any absolute deviation from target exceeds the threshold, generate a rebalance order for the next execution date
- do not evaluate drift and execute on the same daily bar in v2

6. Order generation
- compute target notional based on pre-trade equity minus expected cost buffer if needed
- generate buy/sell orders to move from realized weights to target weights

7. Transaction costs
- compute traded notional per asset
- apply:
  - `commission_cost = traded_notional * commission_bps / 10000`
  - `slippage_cost = traded_notional * slippage_bps / 10000`
- deduct costs from cash

8. Turnover
- define one-way turnover at each rebalance as:
  - `0.5 * sum(abs(target_weight_i - pre_trade_weight_i))`
- return both turnover percent and traded notional in base currency

================================
METRIC DEFINITIONS
================================

Use these definitions:

1. Equity returns
- `r_t = equity_t / equity_(t-1) - 1`

2. Total return
- cumulative net return from initial to final equity after costs

3. Annualized return
- CAGR based on calendar days:
- `((ending_equity / starting_equity) ** (365.25 / elapsed_days) - 1)`

4. Annualized volatility
- standard deviation of daily portfolio returns times `sqrt(252)`

5. Downside volatility
- standard deviation of `min(r_t, 0)` times `sqrt(252)`

6. Max drawdown
- minimum value of drawdown series where:
- `drawdown_t = equity_t / running_peak_t - 1`

7. Sharpe ratio
- preferred v2 formula:
- if no risk-free series is available, use zero-risk-free assumption consistently:
- `mean(r_t) / stdev(r_t) * sqrt(252)`

8. Sortino ratio
- `mean(r_t) / downside_stdev(r_t) * sqrt(252)`

9. Benchmark return
- cumulative benchmark return over the same aligned calendar using adjusted prices

10. Excess return
- portfolio cumulative return minus benchmark cumulative return over the same aligned period

11. Tracking error
- `stdev(r_portfolio_t - r_benchmark_t) * sqrt(252)`

12. Information ratio
- `mean(active_return_t) / stdev(active_return_t) * sqrt(252)`

13. Beta vs benchmark
- covariance of portfolio and benchmark daily returns divided by benchmark variance

14. Correlation vs benchmark
- sample correlation on aligned daily returns

15. Total turnover
- sum of one-way turnover across all rebalance events

================================
OUTPUT MODEL
================================

Suggested models:

```python
class AllocationBacktestAssumptions(BaseModel):
    price_basis: str
    execution_price_field: str
    execution_lag_days: int
    calendar_policy: str
    fractional_shares: bool
    long_only: bool
    leverage_allowed: bool
    tax_treatment: str
    investor_base_currency: str | None = None
```

```python
class AllocationBacktestInstrumentMeta(BaseModel):
    symbol: str
    trading_currency: str | None = None
    instrument_base_currency: str | None = None
    currency_hedged: bool | None = None
    distribution_policy: Literal["accumulating", "distributing", "unknown"] = "unknown"
```

```python
class AllocationBacktestWeight(BaseModel):
    symbol: str
    target_weight: float
```

```python
class AllocationBacktestTrade(BaseModel):
    date: str
    symbol: str
    action: Literal["buy", "sell"]
    quantity: float
    price: float | None = None
    traded_notional: float | None = None
    commission_cost: float | None = None
    slippage_cost: float | None = None
    total_cost: float | None = None
```

```python
class AllocationBacktestRebalanceEvent(BaseModel):
    decision_date: str
    execution_date: str
    turnover_pct: float | None = None
    traded_notional: float | None = None
    total_cost: float | None = None
```

```python
class AllocationBacktestPoint(BaseModel):
    date: str
    equity: float
    cash: float
    gross_exposure: float | None = None
    drawdown_pct: float | None = None
```

```python
class AllocationBacktestMetrics(BaseModel):
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    tracking_error_pct: float | None = None
    information_ratio: float | None = None
    beta_vs_benchmark: float | None = None
    correlation_vs_benchmark: float | None = None
    total_turnover_pct: float | None = None
    turnover_events_count: int = 0
    total_cost_paid: float | None = None
```

```python
class AllocationBacktestResult(BaseModel):
    portfolio_name: str | None = None
    benchmark_symbol: str | None = None
    start_date: str
    end_date: str
    observation_count: int
    rebalance_frequency: str
    drift_tolerance_pct: float | None = None
    commission_bps: float
    slippage_bps: float
    assumptions: AllocationBacktestAssumptions
    status: str
    instrument_metadata: list[AllocationBacktestInstrumentMeta] = []
    starting_weights: list[AllocationBacktestWeight]
    ending_weights: list[AllocationBacktestWeight]
    metrics: AllocationBacktestMetrics
    equity_curve: list[AllocationBacktestPoint]
    rebalance_events: list[AllocationBacktestRebalanceEvent]
    trades: list[AllocationBacktestTrade]
```

```python
class AllocationBacktestComparison(BaseModel):
    total_return_diff_pct: float | None = None
    annualized_return_diff_pct: float | None = None
    annualized_volatility_diff_pct: float | None = None
    downside_volatility_diff_pct: float | None = None
    max_drawdown_diff_pct: float | None = None
    sharpe_diff: float | None = None
    sortino_diff: float | None = None
    excess_return_diff_pct: float | None = None
    tracking_error_diff_pct: float | None = None
    information_ratio_diff: float | None = None
    beta_diff: float | None = None
    correlation_diff: float | None = None
    total_turnover_diff_pct: float | None = None
    total_cost_diff: float | None = None
```

```python
class PortfolioAllocationBacktestResponse(BaseModel):
    methodology: str
    reference_result: AllocationBacktestResult | None = None
    candidate_result: AllocationBacktestResult
    comparison: AllocationBacktestComparison | None = None
```

Methodology should remain factual only.

Suggested methodology string:
- `Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.`

Status handling requirement:
- return a structured `status` such as `ok`, `degraded`, or `rejected`
- degraded status examples include:
  - missing total-return-equivalent history for a distributing ETF
  - missing hedge-status metadata where requested but unavailable
  - shortened common history due to incomplete price coverage

================================
IMPLEMENTATION NOTES
================================

Suggested new functions:
- `run_portfolio_allocation_backtest(...)`
- `_align_price_matrix(...)`
- `_align_fx_matrix(...)`
- `_determine_rebalance_schedule(...)`
- `_generate_rebalance_orders(...)`
- `_execute_rebalance_orders(...)`
- `_compute_turnover(...)`
- `_apply_trade_costs(...)`
- `_build_equity_curve(...)`
- `_compute_allocation_backtest_metrics(...)`
- `_compare_allocation_backtest_results(...)`

Critical behavior rules:
- use the same aligned calendar for reference, candidate, and benchmark before comparison
- do not execute on the same daily bar that triggered the rebalance decision when only daily close data exists
- retain residual cash after costs
- use `None` when a metric lacks enough observations
- keep output deterministic and machine-readable
- if the user backtests tradable UCITS ETFs, replay those exact symbols rather than mapped US proxy symbols
- keep factor proxies and historical allocation replay as separate layers in the product

================================
FRONTEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `apps/desktop/src/features/backtest/BacktestWorkspacePanel.tsx`
- `apps/desktop/src/features/backtest/ResearchWorkspace.tsx`
- `apps/desktop/src/features/portfolio/types.ts`

Recommended UI sections:

1. Portfolio Builder
Inputs:
- symbols and target weights
- optional reference weights
- benchmark symbol
- date range
- initial capital
- rebalance frequency
- drift tolerance
- commission bps
- slippage bps

2. Assumptions block
Display structured values only:
- price basis
- execution field
- execution lag days
- calendar policy
- fractional shares
- long only
- tax treatment
- investor base currency

3. Instrument metadata block
Display structured values only:
- symbol
- trading currency
- base currency
- currency hedged
- distribution policy

4. Result Summary
Show numeric metrics only for candidate and optional reference.

5. Comparison Table
If reference exists, show diff metrics only.

6. Charts
Required:
- equity curve
- drawdown curve

If reference exists, overlay candidate and reference curves.

7. Tables
Show:
- starting weights
- ending weights
- rebalance events with decision date and execution date
- trade log with total costs

Formatting:
- percentages with 2 decimals
- costs as currency
- `n/a` for nulls
- no narrative helper copy

================================
ACCEPTANCE CRITERIA
================================

Backend:
- separate allocation replay engine exists
- no-look-ahead execution rule is enforced
- adjusted-price basis is used or run status degrades deterministically
- candidate and reference run on identical aligned calendars before comparison
- tradable UCITS instruments are replayed as provided, without hidden substitution to US proxy symbols
- pre-tax treatment is explicit in assumptions metadata
- instrument metadata includes currency and distribution fields when available
- metrics, equity curve, rebalance events, and trades are returned
- transaction costs and rebalance logic are applied consistently
- no narrative fields besides factual methodology

Frontend:
- user can define candidate weights and optional reference weights
- user can run the allocation backtest over a selected period
- assumptions, metrics, charts, and tables render correctly
- comparison block renders when reference exists
- null values show as `n/a`

================================
TESTING
================================

Add backend tests for:
- two-asset deterministic replay with known expected result
- next-day execution rule prevents same-bar rebalance execution
- monthly vs no rebalance produce different results when assets drift
- transaction costs reduce ending equity and increase cash drag
- reference and candidate comparison uses identical aligned dates
- invalid weights are rejected
- insufficient adjusted-price history handled by deterministic status rule
- distributing ETF without total-return-equivalent history triggers deterministic degraded or rejected status
- tradable UCITS symbol input is preserved in replay output and not silently proxy-mapped
- beta, correlation, tracking error, and information ratio are computed from aligned daily returns

Add frontend tests for:
- form validation works
- request payload matches schema
- assumptions block renders structured values only
- summary, comparison, charts, and tables render correctly

================================
DELIVERY NOTES
================================

Prioritize implementation in this order:
1. request/response schemas
2. adjusted-price and alignment logic
3. allocation replay engine with no-look-ahead execution
4. metrics computation
5. API route + service integration
6. frontend builder form
7. summary + assumptions + charts
8. tables
9. comparison mode
10. tests

When finished, report:
- files changed
- route added
- payload shapes added
- formulas used
- calendar, execution, and price assumptions used
```
