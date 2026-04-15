# Backtest Field Inventory

This document inventories financially meaningful fields shown in the desktop portfolio-allocation backtest workspace and traces where they come from today.

It is the working contract for backtest replay accuracy work.

## Purpose

For each visible backtest value, we want a traceable chain:

- UI field
- UI/provider function
- app state source
- engine or backtest-service source
- replay or market-data source
- truth class: replay-derived, diagnostics-derived, synthetic-derived, or unavailable

## Current Root Sources

The portfolio-allocation backtest UI currently renders from two root inputs:

1. `analysis: PortfolioBaselineView | null`
   - produced in `apps/desktop/src/app/App.tsx`
   - used only to seed baseline/current imported holdings in the workspace form
   - this is not the backtest result itself

2. `result: PortfolioAllocationBacktestResponse | null`
   - returned by `POST /backtests/portfolio-allocation`
   - built in `services/quant-engine/app/services/portfolio_backtest_engine.py`
   - contains replay curves, summary metrics, diagnostics snapshots, diagnostics comparison, and implementation details

3. `hypotheticalReplayResult: HypotheticalReplacementReplayResponse | null`
   - returned by `POST /backtests/portfolio-allocation/replacement-intent-preview`
   - built in `services/quant-engine/app/services/portfolio_backtest_engine.py`
   - wraps a standard replay payload plus proposal/derivation metadata, derived baseline/candidate weights, and warnings

Important rules:

- imported holdings seed the workspace, but the replay result is hypothetical and must never be confused with imported broker-truth history
- backtest diagnostics are synthetic replay diagnostics with explicit provenance, not imported portfolio diagnostics
- financially meaningful formulas must be documented with both methodology and implementation location
- replacement-intent replay preview derives weights in backend only; desktop must not construct candidate weights for this workflow

## Truth Classes

- `replay-derived`
  - produced directly from the allocation replay engine using candidate/reference weights and aligned price histories
- `diagnostics-derived`
  - produced from replay-derived states plus historical benchmark/factor market data
- `synthetic-derived`
  - produced from synthetic replay snapshots created to support diagnostics calculations
- `unavailable-required`
  - must render `n/a`, hidden state, or explicit error when replay/diagnostics inputs are missing or misaligned

## Current Provenance Rule

Portfolio-allocation diagnostics currently expose typed provenance:

- `snapshot_basis = synthetic_replay_snapshot`
- `historical_basis = market_data_history`

This means diagnostics are built from:

- a synthetic snapshot from replay ending weights
- replay-derived daily states from the equity curve
- historical benchmark/factor market data

Implementation:

- schema: `services/quant-engine/app/schemas/backtest_engine.py` -> `PortfolioDiagnosticsProvenance`
- input assembly: `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `BacktestDiagnosticsInputs`, `_build_backtest_diagnostics_inputs(...)`
- synthetic snapshot builder: `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `_build_synthetic_snapshot_from_weights(...)`

## Key Formula / Methodology Notes

### Replay methodology

The current backtest methodology string is:

- `Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.`

Implementation:

- `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `METHODOLOGY`
- replay engine: `services/quant-engine/app/backtests/portfolio_engine.py` -> `PortfolioAllocationBacktestEngine`

### Comparison deltas

Comparison rows in the UI are built as:

- `delta = candidate - baseline`

Implementation:

- `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `_diff(...)`

UI tone semantics currently assume:

- higher is better for total/annualized return, max drawdown delta, Sharpe, Sortino, excess return, information ratio
- lower is better for annualized volatility, downside volatility, tracking error, turnover, and cost

Implementation:

- `apps/desktop/src/features/backtest/PortfolioAllocationBacktestPanel.tsx` -> `metricDeltaTone(...)`

## Field Inventory

### Workspace seeding section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Current Import | `analysis?.overview.total_market_value` in `PortfolioAllocationBacktestPanel.tsx` | imported baseline analysis | `synthetic-derived` for workspace only | if no analysis, render `n/a` helper state | seeds baseline form only, not replay output |
| Baseline Total | `referenceWeightTotal` | local form state | not financial truth | warn if not near `1.00` | local validation state |
| Candidate Total | `candidateWeightTotal` | local form state | not financial truth | warn if not near `1.00` | local validation state |
| Replay Setup | local form state | local form state | not financial truth | n/a | user-entered replay assumptions |

### Hypothetical replay section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Hypothetical Replay header/helper | `PortfolioAllocationBacktestPanel.tsx` static copy | none | explanatory only | always render when backtest workspace renders | frames the replacement-intent replay as draft-only |
| Baseline / Hypothetical Candidate / Intent Source / Replay Basis | static summary cards in `PortfolioAllocationBacktestPanel.tsx` | replacement-intent replay workflow | explanatory only | if no replacement intent, render explicit unavailable helper | not financial outputs |
| Proposal metadata | `hypotheticalReplayResult.proposal` | replacement-intent replay response | review metadata + replay input provenance | if no preview run, hidden | traces replay back to explicit replacement intent |
| Derivation metadata | `hypotheticalReplayResult.derivation` | replacement-intent replay response | replay-input provenance | if no preview run, hidden | current rule is `draft_snapshot_positions_normalized` plus `single_symbol_weight_substitution` |
| Baseline weights | `hypotheticalReplayResult.baseline_weights` | replacement-intent replay response | replay-input derived | if preview fails, hidden | derived on backend from draft snapshot position market values |
| Candidate weights | `hypotheticalReplayResult.candidate_weights` | replacement-intent replay response | replay-input derived | if preview fails, hidden | backend-only one-for-one incumbent-to-candidate substitution |
| Warnings | `hypotheticalReplayResult.warnings` | replacement-intent replay response | explanatory provenance | if none, hidden | may include cash-exclusion or hypothetical-only notes |

### Replay summary section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Total Return | `reference_result.metrics.total_return_pct`, `candidate_result.metrics.total_return_pct` | `result.reference_result.metrics`, `result.candidate_result.metrics` | `replay-derived` | if no comparison run, hide table | candidate/baseline replay result |
| Annualized Return | `annualized_return_pct` | replay metrics | `replay-derived` | if no comparison run, hide table | replay metric |
| Annualized Volatility | `annualized_volatility_pct` | replay metrics | `replay-derived` | if no comparison run, hide table | replay metric |
| Downside Volatility | `downside_volatility_pct` | replay metrics | `replay-derived` | if no comparison run, hide table | replay metric |
| Max Drawdown | `max_drawdown_pct` | replay metrics | `replay-derived` | if no comparison run, hide table | replay metric |
| Sharpe / Sortino | `sharpe_ratio`, `sortino_ratio` | replay metrics | `replay-derived` | if unavailable, render `n/a` | replay metric |
| Benchmark Return / Excess Return | `benchmark_return_pct`, `excess_return_pct` | replay metrics | `replay-derived` | if unavailable, render `n/a` | benchmark-relative replay metric |
| Tracking Error / Information Ratio | `tracking_error_pct`, `information_ratio` | replay metrics | `replay-derived` | if unavailable, render `n/a` | benchmark-relative replay metric |
| Beta / Correlation vs Benchmark | `beta_vs_benchmark`, `correlation_vs_benchmark` | replay metrics | `replay-derived` | if unavailable, render `n/a` | benchmark-relative replay metric |
| Turnover / Total Cost | `total_turnover_pct`, `total_cost_paid` | replay metrics | `replay-derived` | if unavailable, render `n/a` | implementation-sensitive replay metric |
| Delta column | `candidate - baseline` | comparison payload | `replay-derived` | if baseline absent, no comparison rows | delta semantics defined in `_diff(...)` |

### Replay curve section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Replay Equity | `candidate_result.equity_curve`, optional `reference_result.equity_curve` | replay result curves | `replay-derived` | if no result, hide whole section | chart values come directly from replay output |
| Replay Drawdown | `drawdown_pct` from replay curves | replay result curves | `replay-derived` | if unavailable, render `n/a` in tooltip/series gap | replay-derived drawdown path |

### Diagnostics comparison section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Before / After Diagnostics header note | `candidate_diagnostics.provenance.note` | diagnostics provenance | `synthetic-derived` + `diagnostics-derived` | if provenance absent, fallback helper text should remain explicit | must prevent confusion with imported diagnostics |
| Factor Exposure Change | `diagnostics_comparison.factor_exposure_changes` | diagnostics comparison payload | `diagnostics-derived` | if diagnostics comparison missing, hide whole diagnostics section | built from synthetic replay diagnostics snapshots |
| Volatility / Drawdown Change | `diagnostics_comparison.volatility_changes` | diagnostics comparison payload | `diagnostics-derived` | if diagnostics comparison missing, hide whole diagnostics section | built from replay diagnostics |
| Risk Contribution Change | `diagnostics_comparison.risk_contribution_changes` | diagnostics comparison payload | `diagnostics-derived` | if diagnostics comparison missing, hide whole diagnostics section | synthetic snapshot + historical factor data |
| Concentration Change | `diagnostics_comparison.concentration_changes` | diagnostics comparison payload | `diagnostics-derived` | if diagnostics comparison missing, hide whole diagnostics section | derived from diagnostics snapshots |
| Stress Scenario Change | `diagnostics_comparison.stress_scenario_changes` | diagnostics comparison payload | `diagnostics-derived` | if diagnostics comparison missing, hide whole diagnostics section | uses diagnostics model outputs, not imported truth |
| Top diagnostics callouts | `diagnostics_comparison.top_*` fields | diagnostics comparison payload | `diagnostics-derived` | if the backend cannot select a reliable group callout, render no callout for that group | authoritative backend-selected summary rows; desktop must not infer these from array order |

Each `top_*` callout now includes:

- `key`
- `label`
- `baseline_value`
- `candidate_value`
- `delta_value`
- `selection_rule`
- `rationale`

Stable `selection_rule` API values:

- `largest_absolute_delta`
  - meaning: backend selected the eligible row with the largest absolute `candidate - baseline` delta in that group
  - current groups using it: factor exposure, risk contribution, stress / scenario
- `fixed_priority`
  - meaning: backend selected the first eligible row in a pre-declared priority list for that group
  - current groups using it: volatility / drawdown, concentration

API stability rule:

- these `selection_rule` values are contract values and should be treated as stable API surface
- desktop may format them for display, but must not reinterpret them into different semantic categories
- if a new rule is introduced, the contract doc and typed schemas must be updated together

UI rule:

- desktop must render the backend-provided `rationale` directly for callout explanation
- desktop must not substitute a generic heuristic explanation when authoritative rationale is available

Current backend selection semantics for `diagnostics_comparison.top_*`:

- `top_factor_exposure_change`
  - selected as the eligible factor row with the largest absolute `delta_value`
  - eligibility requires non-null baseline, candidate, and delta values
- `top_volatility_change`
  - selected by fixed priority order, not cross-metric magnitude ranking
  - priority: `max_drawdown` -> `annualized_volatility` -> `downside_volatility`
  - each selected row must have non-null baseline, candidate, and delta values
- `top_risk_contribution_change`
  - selected as the eligible risk-contribution row with the largest absolute `delta_value`
  - current implementation ranks only factor-contribution comparison rows, not mixed factor/position rows
- `top_concentration_change`
  - selected by fixed priority order, not cross-metric magnitude ranking
  - priority: `factor_hhi` -> `top_1_position_risk_share`
  - each selected row must have non-null baseline, candidate, and delta values
- `top_stress_scenario_change`
  - selected as the eligible stress-scenario row with the largest absolute `delta_value`
  - delta remains `candidate - baseline` in the scenario return unit

Important semantics:

- these callouts are `diagnostics-derived` summaries of the existing group arrays, not new truth classes
- the callout means `most salient valid change in this group` under the documented backend rule, not `best`, `recommended`, or `approved`
- desktop must render the returned callout fields as-is and must not recompute ranking from array order
- if no eligible row exists for a group, the corresponding `top_*` field must be `null`

### Implementation details section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Candidate status | `candidate_result.status` | replay result | `replay-derived` | must remain explicit (`ok`, `degraded`, `rejected`) | replay engine status |
| Calendar policy | `candidate_result.assumptions.calendar_policy` | replay assumptions | `replay-derived` | if unavailable, render `n/a` | aligned-date replay rule |
| Price basis / execution field / execution lag | replay assumptions | `candidate_result.assumptions` | `replay-derived` | if unavailable, render `n/a` | implementation assumptions |
| Tax treatment / fractional shares / base currency | replay assumptions | `candidate_result.assumptions` | `replay-derived` | if unavailable, render `n/a` | implementation assumptions |

### Holdings / trade details section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Starting Weights | `candidate_result.starting_weights` | replay result | `replay-derived` | if absent, render empty state | replay starting allocation |
| Ending Weights | `candidate_result.ending_weights` | replay result | `replay-derived` | if absent, render empty state | replay ending allocation |
| Instrument Metadata | `candidate_result.instrument_metadata` | replay result | `replay-derived` | if missing, render `n/a` fields | descriptive replay metadata |
| Rebalance Events | `candidate_result.rebalance_events` | replay result | `replay-derived` | if none, show `No rebalances` | implementation event log |
| Trade Log | `candidate_result.trades.slice(0, 12)` | replay result | `replay-derived` | if none, render empty list | candidate replay trade log |

## Current Accuracy Rules

1. Imported portfolio data seeds the workspace, but replay results are hypothetical and must not be presented as imported broker-truth performance.
2. Backtest diagnostics are synthetic replay diagnostics with explicit provenance, not imported diagnostics.
3. Diagnostics comparison deltas are always `candidate - baseline`.
4. If candidate/reference/benchmark date windows do not share enough common dates, the route must fail explicitly rather than compare incompatible replays.
5. If a financially meaningful backtest formula or assumption changes, methodology text and this inventory should be updated together.
6. Replacement-intent replay preview must reject invalid substitution cases rather than invent renormalization or portfolio-construction behavior.

## Current Coverage Status

- backend route coverage verifies weight validation, execution-lag validation, proxy-history fallbacks, typed diagnostics provenance, insufficient common-date rejection, and replacement-intent replay validation/derivation rules
- backend service coverage verifies synthetic snapshot creation and explicit diagnostics input assembly
- desktop coverage verifies workspace rendering, imported baseline seeding, manual replay submission payloads, replacement-intent replay preview payloads, and diagnostics provenance messaging
