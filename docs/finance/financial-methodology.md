# Financial Methodology

This document is the project-level reference for the financial and economic methodology implemented in the codebase.

It is intended to describe:
- what financial concepts the project uses
- what formulas are implemented
- what each model is trying to measure
- where the implementation lives
- what the important assumptions and limitations are

This file should be updated whenever financially meaningful formulas, assumptions, or truth classes change.

This document is the core finance-methodology reference for the `Quant Research Lab` direction of the project.

For the canonical shipped-scope boundary of what is actually live today, use `docs/product/current-product-state.md`.

This document should explain implemented financial methodology without overstating transitional or future-only capabilities.

## Terminology

The project uses the term `factor` rather than `quant`.

Implemented factor families include:
- `market`
- `style`
- `sector`
- `macro`

Examples:
- `SPY` -> market beta proxy
- `QQQ` -> growth proxy
- `IWD` -> value proxy
- `IWM` -> small-cap proxy
- `XLK`, `XLI`, `XLF`, `XLE`, `XLV`, `XLP`, `XLU`, `XLY` -> sector factor proxies
- `IEF`, `TLT`, `LQD`, `DBC` -> macro proxies

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
- `replay-derived hypothetical outputs`
  - hypothetical allocation replay, candidate comparison, and overlay-aware replay artifacts built from explicit candidate/reference weights and market data

This distinction matters because some panels can be financially exact for imported history, while variant/snapshot workflows may be approximate.

Relevant implementation:
- `services/quant-engine/app/services/diagnostics_engine.py`

Diagnostics contract rule:
- diagnostics responses must carry explicit provenance for snapshot basis and historical basis so imported portfolio history and synthetic snapshot-history analytics are not conflated
- diagnostics responses must also carry `history_truth_class` and `price_basis` so consumers can distinguish imported-history-equivalent, synthetic-history-derived, and unavailable states
- diagnostics summary fields must only expose history-derived diagnostics values and must not mix in current-state holdings concentration

Investor-economics status rule:
- `withheld` means investor-economics outputs are intentionally suppressed even though a broader diagnostics/history or replay artifact exists
- `unavailable` means the required source inputs or trustworthy computation path do not exist for the requested output
- consumers must use shipped `investor_economics_status` semantics rather than treating all `null` return-family fields as generic missing data

## Market Data Basis

The project uses historical price series, benchmark series, ETF holdings, and security metadata supplied through `MarketDataService`.

Primary implementation:
- `services/quant-engine/app/services/market_data.py`

Important financial rule:
- financially meaningful analytics should use adjusted-close or total-return-equivalent price series when measuring returns, volatility, drawdown, or factor behavior

Current risk note:
- some model paths rely on the incoming `price` field being total-return-aware; this should be treated as a financial assumption until explicitly hardened in code and metadata

Current diagnostics note:
- diagnostics engine run metadata currently reports `price_basis = close` when history-aware diagnostics are available
- unavailable diagnostics report `price_basis = unavailable`
- diagnostics engine now degrades `run_metadata.source_status.{benchmark_history,factor_history}` to `live_market_data_unverified_return_basis` until return-basis trust is explicitly verified for those histories
- this degradation is intentional: diagnostics may still run, but the contract must not overclaim adjusted-close or total-return-aware trust for benchmark/factor return math
- while that unverified return-basis state is present, diagnostics run-level confidence must degrade to `low` even if imported history exists, because the return-input trust required for stronger benchmark/factor claims is not yet proven
- current narrow detection rule: a history is marked `live_market_data_verified_adjusted_close` only when every loaded row explicitly carries `adjClose` or `adjusted_close`; otherwise it remains `live_market_data_unverified_return_basis`
- this is adjusted-close field detection only, not proof of full total-return equivalence, split correctness across all vendors, or economically complete dividend treatment
- diagnostics now also degrade `statistical_factor_model.status`, `model_reliability.status`, and `risk_contribution_breakdown.status` to `degraded_unverified_return_basis` whenever benchmark/factor adjusted-close support is incomplete, so those outputs no longer present close-based factor math as clean `ok`/`partial` status
- a first explicit price-series selector now exists in `risk.py`; it prefers adjusted-close when every dated row provides it, otherwise it falls back to raw `price` with `unverified_close_only` semantics
- this selector now covers a broader but still narrow subset: position-risk contributions, benchmark-relative summary inputs, rolling volatility benchmark inputs, and factor-model benchmark/factor return inputs
- the selector now also feeds the deeper covariance/contribution helper builders used inside risk-contribution breakdowns, reducing residual raw-price dependence in factor-risk math
- outside the risk stack, the next narrow migration now covers dashboard-history benchmark series and benchmark comparison readouts, so those paths also prefer adjusted-close when it is fully available
- remaining unmigrated return paths should keep using the same selector pattern rather than direct raw-price reads
- a centralized selector-policy helper now exists for analytics entry points: use `selected_history_price_map(...)` / `select_history_price_series(...)` rather than rebuilding benchmark or return series directly from raw rows
- Stage 1 intent is now enforceable in code review: direct raw-price history construction should be treated as suspicious unless the path is explicitly non-return/display-only
- diagnostics now expose grouped subsection-level trust in `run_metadata.section_trust` for benchmark-relative, factor-model, and risk-contribution paths
- these subsection trust states are intentionally narrow: `verified_adjusted_close`, `degraded_unverified_return_basis`, or `unavailable`; mixed or unprovable sections stay degraded rather than claiming stronger certainty
- dashboard-history now exposes its own compact `run_metadata.section_trust` for `portfolio_path`, `benchmark_path`, and `monthly_returns_path`
- these dashboard trust states are also intentionally conservative: imported portfolio replay can be explicit, benchmark return basis can degrade independently, and monthly returns can be marked `suppressed_unstable_path` rather than implied reliable
- a first `return_basis_contract` slice now exists for dashboard-history benchmark investor-return semantics; current reachable states are intentionally conservative (`price_return_only`, `unverified_adjusted_proxy`, `unavailable`)
- adjusted-close field presence alone does not upgrade dashboard benchmark returns to investor-economics truth; benchmark cumulative return / excess return now refuse (`None`) until `verified_total_return` can be justified
- narrow pilot exception: imported dashboard-history may label only the benchmark path as `verified_total_return` when and only when the benchmark slice is exactly `SPY`, fetched directly from FMP `historical-price-eod/light`, with no fallback, no symbol override, no mixed-source stitching, and explicit provenance scope evidence proving ordered, unique, in-window `adjClose` coverage
- this pilot does not upgrade any portfolio path, any non-`SPY` symbol, any other vendor or endpoint, or any diagnostics / replay / strategy path
- dashboard-history now hard-codes a narrower investor-economics boundary: only three exact-slice scalar outputs may unlock
- allowlisted output 1: portfolio-only exact-slice `time_weighted_return_pct`, and only for an admitted exact portfolio slice
- allowlisted output 2: exact-slice `benchmark_return_pct`, and only when that same slice is exact and the benchmark basis is independently `verified_total_return`
- dashboard-history contracts now also surface this as explicit partial-unlock metadata while overall `investor_economics_status` remains `withheld`; consumers must use that allowlist metadata rather than inferring family-wide enablement from a present scalar
- dashboard-history now also allows exact-slice `excess_return_pct`, but only as same-slice subtraction of those two already-admitted scalars with no independent recomputation, no daily-series subtraction, no client-side equivalence path, and no scope transfer beyond the identical admitted slice
- if either source leg is withheld, null, unverified, or scope-mismatched, exact-slice `excess_return_pct` must remain withheld
- this runtime enablement is scalar-only and exact-slice-only; consumers must not derive or render broader benchmark-relative outputs from subtraction
- the drawdown-loss family remains withheld for dashboard-history; `range_metrics[*].max_drawdown_pct` stays refused even if an exact-slice scalar unlock occurs
- monthly/rebucketed/rolling/non-identical-window outputs also remain outside the unlock boundary; the exact-slice allowance must not be generalized to broader windows or rebucketed summaries
- this exact-slice policy does not extend to diagnostics, replay, backtest, or strategy-lab surfaces; benchmark-relative logic must stay fenced to the dashboard exact-slice admission rule
- this slice is intentionally narrow and does not claim that broker-replayed portfolio paths are generally proven total-return investor economics
- shipped contracts surface that policy through `investor_economics_status = withheld`; this is intentional suppression tied to policy and return-basis limits, not generic source unavailability

## Portfolio Return Methodology

### Cash-Flow-Neutral Daily Returns

For historical risk and factor diagnostics, the portfolio return series is built from daily portfolio states using a cash-flow-neutral formula.

Implemented formula:

```text
daily_return_t = ((total_portfolio_value_t - external_cash_flow_t) / total_portfolio_value_(t-1)) - 1
```

Purpose:
- remove distortion from deposits and withdrawals
- measure investment performance rather than capital movements

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `_portfolio_time_weighted_return_series(...)`

Economic meaning:
- approximates a daily time-weighted return framework for portfolio analytics

## Benchmark Return Methodology

Benchmark returns are built from a price series using simple daily returns.

Implemented formula:

```text
benchmark_return_t = (price_t / price_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `_benchmark_return_series(...)`
- helper: `_series_to_returns(...)`

Assumption:
- the benchmark price series should be adjusted-close or total-return-equivalent for financially correct comparison work

## Wealth Index and Drawdown

### Wealth Index

The project builds a compounded return index from daily returns.

Implemented logic:

```text
wealth_0 = 100
wealth_t = wealth_(t-1) * (1 + daily_return_t)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `_build_wealth_index(...)`

### Drawdown

Drawdown is computed from the compounded return index rather than raw portfolio value.

Implemented formula:

```text
drawdown_t = (wealth_t / running_peak_t) - 1
```

The code reports this as a percent value.

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `_build_drawdown_from_return_index(...)`

Economic meaning:
- drawdown measures path-dependent loss from the prior peak
- this is a better risk measure than raw volatility for many portfolio users

## Volatility Methodology

### Annualized Realized Volatility

Implemented formula:

```text
realized_vol = stdev(daily_returns) * sqrt(252)
```

The UI generally displays volatility in percent form.

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- helper: `_calculate_annualized_volatility(...)`

### Downside Volatility

The project uses downside deviation with minimum acceptable return `mar = 0`.

Implemented formula:

```text
downside_t = min(return_t - mar, 0)
downside_vol = stdev(downside_t) * sqrt(252)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- downside-deviation helper near the volatility payload logic

Economic meaning:
- measures harmful volatility rather than total volatility

### Tracking Error

Implemented formula:

```text
active_return_t = portfolio_return_t - benchmark_return_t
tracking_error = stdev(active_return_t) * sqrt(252)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- aligned through `_aligned_active_return_series(...)`

Economic meaning:
- measures active risk versus benchmark

### Volatility Regime

The project derives a simple regime label from the percentile rank of current `20d` realized volatility relative to observed history.

Implemented logic:
- percentile < 0.30 -> `calm`
- percentile <= 0.80 -> `normal`
- otherwise -> `stressed`

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_calculate_percentile_rank(...)`
- `_classify_volatility_regime(...)`

Economic meaning:
- provides a simple market-state classification

Limitation:
- this is a practical dashboard regime model, not a full institutional regime framework

## Relative Risk Summary

The project includes benchmark-relative risk metrics such as:
- tracking error
- active return
- information ratio

Information ratio concept:

```text
information_ratio = active_return / tracking_error
```

The exact payload is defined in:
- `services/quant-engine/app/schemas/reconciliation.py`

## Rolling Risk Summary

The project also computes rolling beta and correlation windows.

Typical windows:
- `20d`
- `60d`
- `252d`

Economic meaning:
- beta measures benchmark sensitivity
- correlation measures co-movement

These are different from factor loadings and should not be interpreted as the same thing.

Schema location:
- `services/quant-engine/app/schemas/reconciliation.py`

## Statistical Factor Model

### High-Level Approach

The project implements a rolling ETF-proxy factor model.

Methodology string in code:

```text
Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `factor_model_methodology()`

### Factor Definitions

Factor definitions are declared in:
- `services/quant-engine/app/analytics/risk.py`
- `DEFAULT_FACTOR_DEFINITIONS`

Each factor includes:
- key
- label
- category
- US ETF proxy
- target exposure
- UCITS mapping metadata
- default enabled flag
- orthogonalization order
- description

### Factor Returns

Factor proxy return series are built from ETF price histories using simple daily returns.

Implemented formula:

```text
factor_return_t = (price_t / price_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- helper: `_series_to_returns(...)`

### Orthogonalization

The factor model orthogonalizes later factor series against earlier ones in the configured order.

Conceptually:

```text
f_i = a + b_1 f_1 + ... + b_(i-1) f_(i-1) + u_i
orthogonalized_factor_i = u_i
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- function: `_orthogonalize_factor_series(...)`

Economic meaning:
- reduces overlap between highly correlated proxies such as `SPY`, `QQQ`, and `XLK`

Important limitation:
- factor interpretation is sensitive to the chosen order

### Regression Fit

After orthogonalization, the project fits a regression of portfolio returns on factor returns.

Conceptually:

```text
portfolio_return_t = alpha + beta_1 f_1 + ... + beta_n f_n + error_t
```

Implementation uses a least-squares solver with very light ridge stabilization:

```text
ridge_lambda = 1e-5
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_fit_factor_model(...)`
- `_least_squares(...)`

Economic meaning:
- estimated coefficients are factor loadings / exposures

### Rolling Factor Loadings

The project refits the factor model over rolling windows.

Current windows:
- `20d`
- `60d`
- `252d`

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_build_rolling_factor_loadings(...)`

Economic meaning:
- shows how exposures evolve through time rather than assuming one fixed factor profile

### R-squared

The project calculates standard regression `R²`.

Implemented formula:

```text
ss_total = sum((y_t - mean_y)^2)
ss_resid = sum(error_t^2)
r_squared = 1 - ss_resid / ss_total
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_fit_factor_model(...)`

### Residual Volatility / Specific Risk

Residual volatility is built from regression residuals.

Implementation:
- residuals come from `_fit_factor_model(...)`
- annualization uses `_calculate_annualized_volatility(...)`

Economic meaning:
- the part of portfolio behavior not explained by the chosen factor set

## Collinearity Diagnostics

The project checks pairwise factor correlation and flags highly overlapping factors.

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_build_factor_collinearity_warnings(...)`
- `_build_collinearity_diagnostics(...)`

Economic meaning:
- warns when factor interpretation may be unstable because ETF proxies are too similar

Limitation:
- pairwise correlation is a useful but basic collinearity diagnostic

## Factor Shift Diagnostics

The project tracks changes in factor loadings across windows and recent history.

Current concepts include:
- current loading by window
- 20d / 60d change
- stability gaps across windows
- heuristic flags for large shifts or unstable windows

Schema location:
- `services/quant-engine/app/schemas/reconciliation.py`

Implementation:
- `services/quant-engine/app/analytics/risk.py`

Economic meaning:
- intended as change monitoring for exposures

Current status:
- useful operationally
- should be treated as diagnostics/monitoring rather than a complete institutional balancing framework

## Risk Contribution

The project includes risk contribution by factor and by position.

### Position Risk Contribution

Position-level risk uses:
- weights
- covariance matrix of historical returns
- marginal contribution
- component contribution

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_build_position_risk_contributions(...)`
- `_compute_covariance_matrix(...)`
- `_component_risk_contributions(...)`

Economic meaning:
- identifies which holdings drive portfolio risk most strongly

### Factor Risk Contribution

The project also reports factor contribution metrics.

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_build_factor_risk_contributions(...)`

Current status:
- useful as an initial diagnostics layer
- should be interpreted carefully until the production-grade covariance-based hardening work is complete

### Concentration Metrics

The project reports concentration metrics such as:
- top factor risk shares
- top position risk shares
- HHI (Herfindahl-Hirschman style concentration index)

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_sum_top_risk_shares(...)`
- `_herfindahl_index(...)`

Economic meaning:
- helps identify concentration risk and diversification weakness

Contract rule:
- diagnostics summary concentration fields are derived from historical risk contribution outputs
- current-state holdings concentration is a separate truth class and should live in exposure-side contracts instead

## Stress Scenarios

The project estimates stress scenario returns by shocking current factor exposures.

Conceptually:

```text
estimated_scenario_return = sum(current_factor_loading_i * shock_i)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `build_stress_scenarios(...)`

Economic meaning:
- provides first-pass scenario sensitivity based on current factor profile

Limitation:
- this is an exposure-based approximation, not a full market replay

Contract rule:
- unavailable stress scenario support must not fabricate `0.0%` returns
- when unavailable, diagnostics should return `estimated_return_pct = null` with `status = unavailable`

## Market Overlap and Look-Through

The project includes benchmark overlap and ETF look-through logic.

Implemented concepts include:
- benchmark overlap weight
- active share
- ETF constituent overlap
- look-through sector exposure

Relevant implementation:
- `services/quant-engine/app/analytics/risk.py`
- `services/quant-engine/app/services/exposure_engine.py`

Economic meaning:
- helps distinguish apparent diversification from hidden overlap

## Current-State Concentration

The exposure contract now includes a current-state concentration block sourced only from snapshot holdings and current holdings metadata.

Implemented concepts include:
- top position weights
- top sector weights
- position HHI
- sector HHI
- effective holdings

Implemented formulas:

```text
position_hhi = sum(weight_i^2)
sector_hhi = sum(sector_weight_j^2)
effective_holdings = 1 / position_hhi
```

Implementation:
- `services/quant-engine/app/analytics/overview.py`
- `services/quant-engine/app/services/exposure_engine.py`

Truth-class rule:
- this block is current-state concentration only
- it must remain separate from diagnostics-side history-derived risk concentration

## Allocation Backtest Methodology

The project also includes a separate allocation replay engine.

Core methodology string:

```text
Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.
```

Relevant implementation:
- `services/quant-engine/app/backtests/portfolio_engine.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`

Key ideas:
- weighted portfolio replay
- scheduled rebalancing
- turnover and transaction costs
- reference vs candidate portfolio comparison

Current request assumptions:
- replay request contract currently uses `price_basis = adjusted_close`
- execution uses `execution_price_field = close`
- execution lag is explicit and must be at least one day
- candidate/reference comparisons fail explicitly when there are not enough common aligned dates

Current shipped replay surfaces:
- canonical allocation replay at `POST /backtests/portfolio-allocation`
- hypothetical replacement replay at `POST /backtests/portfolio-allocation/replacement-intent-preview`
- overlay-aware hypothetical replay at `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`

Current replay provenance state:
- hypothetical replay can consume a backend-constructed candidate built from either `same_weight_substitution_v1` or `fixed_split_50_50_substitution_v2`
- the replay response now explicitly preserves whether the replay used direct preview derivation or a supplied constructed candidate
- the replay response now explicitly preserves the actual construction rule consumed by the hypothetical replay
- the replay response also carries upstream draft/workspace/base-node lineage and ranking seed lineage for the current single-replacement replay slice
- when constraint validation is supplied to replay routes, the replay response also echoes validation-supplied status, validation result, and constraint-set lineage
- replay now rejects provable lineage mismatches between supplied validation artifacts and constructed-candidate artifacts
- immutable saved proposal artifacts now reject provable internal contradictions between saved replay-basis provenance and the saved replay snapshot provenance

Replay investor-economics semantics:
- replay and replay-derived diagnostics can expose evidence-rich paths while still reporting `investor_economics_status = withheld`
- in that state, return-family, drawdown-family, and benchmark-relative investor-economics outputs are intentionally suppressed because `verified_total_return` has not been justified
- this must be documented and rendered as withholding, not as generic replay failure or missing history

### Single-Replacement Candidate Construction

The current shipped construction logic is narrow and review-oriented rather than a generalized portfolio construction engine.

Current implemented rules:
- `same_weight_substitution_v1`
  - fully remove the incumbent weight and assign that full starting weight to the candidate symbol
- `fixed_split_50_50_substitution_v2`
  - retain half of the incumbent starting weight and assign the other half to the candidate symbol

Construction basis rules:
- baseline weights are derived from positive-market-value draft snapshot positions only
- draft cash balances are excluded from the current construction basis
- constructed candidates are hypothetical candidate inputs only and do not mutate `PortfolioSnapshot`

Relevant implementation:
- `services/quant-engine/app/services/candidate_construction.py`
- `services/quant-engine/app/services/candidate_formation.py`

### Overlay-Aware Hypothetical Replay

The current shipped overlay-aware replay is a narrow methodology layer on top of hypothetical replay, not a general overlay engine.

Current overlay behavior:
- supported overlay id: `benchmark_trend_overlay_v1`
- supported replayable overlay states: `risk_on`, `risk_reduced`
- `risk_on` leaves candidate weights unchanged
- `risk_reduced` scales non-cash candidate weights by `0.35`
- residual weight is assigned to synthetic replay cash symbol `__CASH__`
- overlay is applied to the hypothetical candidate only, not to baseline/reference weights

Methodology rule:
- synthetic replay cash `__CASH__` is an internal replay artifact used to preserve candidate total weight under overlay risk reduction
- it must not be interpreted as imported broker cash truth

Relevant implementation:
- `services/quant-engine/app/services/portfolio_backtest_engine.py`

## Financial Accuracy Rules

The project has an explicit rule that financially meaningful formulas must be documented and traceable.

Relevant documentation and policy references:
- `docs/product/roadmap.md`
- `README.md`

Important project rule:
- any metric shown in UI should be traceable to one engine response field and further back to code-level implementation and data truth class

## Current Known Financial Limitations

At the time of writing, the main finance-related limitations are:

- some factor/benchmark return paths still rely on the incoming price field being adjusted or total-return-aware
- orthogonalized factor interpretation depends on factor ordering
- factor-model reliability diagnostics are present but still need production-grade hardening
- synthetic snapshot-history diagnostics are useful but not equivalent to broker-truth historical replay
- overlay support is currently a narrow hypothetical replay path, not a generalized overlay methodology family
- candidate construction is currently narrow single-replacement review logic, not generalized portfolio construction
- replay provenance is now explicit for constructed-candidate consumption and echoed constraint-validation lineage, and replay rejects provable artifact mismatches, but replay still does not enforce validation status in the current contract
- immutable saved proposal artifacts and active thesis restore now reject provable internal replay-lineage contradictions rather than silently trusting inconsistent review artifacts
- some diagnostics panels are more monitoring-oriented than portfolio-manager-decision-oriented

## Recommended Maintenance Rule

When any of the following changes, update this file:
- financial formulas
- methodology strings
- factor definitions
- risk assumptions
- degradation semantics
- truth-class semantics
- economically meaningful backtest assumptions

At minimum, updates should remain aligned with:
- code implementation
- schema fields
- methodology strings
- test expectations
