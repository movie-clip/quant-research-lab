# Financial Methodology

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
- `persisted construction artifacts`
  - deterministic target-weight artifacts produced by backend construction policy execution
- `hypothetical optimizer previews and handoffs`
  - optimizer outputs and persisted handoff references used only for downstream evaluation
- `replay-derived hypothetical outputs`
  - historical replay, candidate comparison, and overlay-aware replay artifacts built from explicit candidate/reference weights and market data

Relevant implementation:
- `services/quant-engine/app/services/diagnostics_engine.py`
- `services/quant-engine/app/services/construction_run_service.py`
- `services/quant-engine/app/services/optimizer_preview_service.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`

## Trust, Degradation, Withholding, and Unavailability

This is shipped baseline behavior across diagnostics, dashboard-history, replay, construction replay, and optimizer handoff replay.

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
- replay and optimizer-handoff replay use persisted or normalized return-basis attestation to suppress benchmark-relative outputs when trust is narrower than the raw engine surface
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
- benchmark-relative replay outputs may be computed internally but still withheld or suppressed at the contract boundary when trust attestation is weaker than required

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

## Allocation Replay Methodology

Core methodology string:

```text
Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.
```

Relevant implementation:
- `services/quant-engine/app/backtests/portfolio_engine.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`

Current shipped replay surfaces:
- `POST /backtests/portfolio-allocation`
- `POST /backtests/portfolio-allocation/replacement-intent-preview`
- `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
- `POST /backtests/portfolio-allocation/construction-artifact-preview`
- `POST /backtests/portfolio-allocation/optimizer-handoff-preview`

Current replay provenance rules:
- replay preserves direct-preview vs persisted-artifact vs optimizer-handoff source lineage explicitly
- replacement-intent replay preserves the actual construction rule consumed by the replay
- construction-artifact replay preserves the persisted `selection_rule_trace`
- optimizer-handoff replay preserves persisted return-basis attestation and uses it to suppress benchmark-relative output families when required
- replay rejects provable lineage mismatches between supplied or persisted artifacts where the contract can verify contradiction

Replay investor-economics semantics:
- replay and replay-derived diagnostics can expose evidence-rich paths while still reporting `investor_economics_status = withheld`
- in that state, investor-economics families remain intentionally suppressed because stronger return-basis claims have not been justified for the contract path

## Construction Methodology

The codebase now has two shipped construction surfaces.

### Persisted construction engine

- route: `POST /construction/run`
- policy discovery route: `GET /construction/policies`
- persisted load route: `GET /construction/artifacts/{artifact_id}`
- current persisted policies: `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- current deterministic selection pipeline: `eligible_only` then `take_top_n`
- policy execution captures and persists `selection_rule_trace` provenance
- replay consumption happens through `POST /backtests/portfolio-allocation/construction-artifact-preview`
- policy discovery exposes additive backend-owned catalog metadata only: `family`, `constraints`, `inputs`, `determinism`, and `ranking_support`
- policy discovery filtering is server-side exact-match filtering over catalog metadata only; it does not inspect client payloads, persisted artifacts, replay inputs, or review state

Current basis rules:
- consumes ranked candidates plus current portfolio weights as explicit input artifacts
- resolves shipped policy metadata and weighting behavior from a backend-owned catalog seam
- keeps deterministic selection separate from weighting
- `top_n_equal_weight_v1` seeds equal weights across selected names
- `top_n_inverse_rank_weight_v1` assigns weights proportional to inverse selected-order rank and normalizes them to sum to `1.0`
- `top_n_linear_rank_weight_v1` assigns weights proportional to selected-order linear numerators and normalizes them to sum to `1.0`
- policy discovery does not expand construction breadth; the shipped catalog still contains only those three policies
- policy discovery metadata is additive only and does not change persisted construction artifact shape, run behavior, validation/preflight, or preview/open contracts
- enforces only the shipped constraint family for this policy slice
- evaluates constraints against the actual generated target weights for the selected policy
- fails closed on infeasible requests rather than repairing or silently relaxing the policy

### Review-oriented single-replacement construction

- current rules:
  - `same_weight_substitution_v1`
  - `fixed_split_50_50_substitution_v2`
- basis uses positive-market-value draft snapshot positions
- draft cash balances are excluded from the current review construction basis
- outputs remain hypothetical review artifacts and do not mutate `PortfolioSnapshot`

Relevant implementation:
- `services/quant-engine/app/services/construction_run_service.py`
- `services/quant-engine/app/services/construction_artifact_service.py`
- `services/quant-engine/app/services/candidate_construction.py`
- `services/quant-engine/app/services/candidate_formation.py`

## Optimizer Preview and Handoff Methodology

The shipped optimizer workflow is hypothetical and lineage-first.

- preview route: `POST /optimizer/preview`
- replay route: `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
- validation route: `POST /backtests/portfolio-allocation/optimizer-handoff/constraints`

Methodology rules:
- optimizer preview produces hypothetical output only; it is not applied portfolio truth
- feasible previews can persist immutable handoff references for downstream replay and validation
- downstream replay consumes the explicit persisted reference rather than reconstructed inline state
- benchmark-relative replay output suppression follows the persisted return-basis attestation on the handoff
- trusted PIT alpha can be attached for the narrow `alpha_quality_v1` path when requested by preview

## Current Known Financial Limitations

At the time of writing, the main finance-related limitations are:

- some return paths still remain intentionally degraded or withheld because total-return-equivalent trust is not yet proven broadly enough to unlock stronger claims everywhere
- factor interpretation still depends on factor ordering and proxy quality
- persisted construction is shipped, but the persisted policy set and constraint breadth are still narrow
- optimizer is shipped only as a hypothetical preview and handoff workflow, not an execution or applied-allocation workflow
- overlay support remains a narrow hypothetical replay slice

## Maintenance Rule

When any of the following changes, update this file:
- financial formulas
- methodology strings
- factor definitions
- trust, degradation, withholding, or unavailability semantics
- economically meaningful replay, construction, or optimizer assumptions
