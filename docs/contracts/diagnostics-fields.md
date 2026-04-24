# Diagnostics Field Inventory

This document captures the key contract fields for diagnostics outputs that are reused across desktop review flows.

## Core Provenance Fields

Source schema:
- `services/quant-engine/app/schemas/diagnostics.py`

### `provenance.snapshot_basis`
- `imported_snapshot`
  - diagnostics were computed from an imported portfolio snapshot payload
- `snapshot_request`
  - diagnostics were computed from a snapshot-style request assembled outside imported broker replay

### `provenance.historical_basis`
- `imported_portfolio_history`
  - historical diagnostics come from imported portfolio history replay plus external benchmark/factor market data
- `market_data_history`
  - historical diagnostics come from synthetic snapshot-history states built from the current snapshot plus external market data
- `unavailable`
  - no valid historical portfolio path was available, so historical diagnostics remain unavailable

### `provenance.note`
- user-facing explanation of the diagnostics basis
- must remain explicit about synthetic vs imported history

### `provenance.history_truth_class`
- `imported_history_equivalent`
  - the historical diagnostics path is grounded in imported portfolio history replay semantics
- `synthetic_history_derived`
  - the historical diagnostics path is built from synthetic snapshot-history states plus market data and must not be read as broker-truth history
- `unavailable`
  - no valid historical path was available

### `provenance.price_basis`
- `close`
  - diagnostics histories and portfolio path inputs are interpreted on the current close-price basis used by the diagnostics engine
- `unavailable`
  - no historically grounded diagnostics basis was available

## Run Metadata

Diagnostics now expose explicit grouped run metadata:

- `run_metadata.diagnostics_id`
- `run_metadata.methodology_id`
- `run_metadata.price_basis`
- `run_metadata.source_status`
- `run_metadata.investor_economics_status`
- `run_metadata.investor_economics_partial_unlock`
- `run_metadata.confidence`
- `run_metadata.factor_model_parameters`
- `run_metadata.reproducibility`

### `run_metadata.source_status`

- grouped source-health context for the diagnostics run
- current fields:
  - `portfolio_history`
    - `imported_replay`
      - historical diagnostics are based on imported portfolio replay semantics
    - `synthetic_snapshot_history`
      - historical diagnostics are based on synthetic snapshot-history construction
    - `unavailable`
      - no valid portfolio-history path was available
  - `benchmark_history`
    - `live_market_data_verified_adjusted_close`
    - `live_market_data_unverified_return_basis`
    - `unavailable`
  - `factor_history`
    - `live_market_data_verified_adjusted_close`
    - `live_market_data_unverified_return_basis`
    - `unavailable`

### `run_metadata.investor_economics_status`

- explicit investor-economics interpretation for the diagnostics run
- current values:
  - `available`
    - diagnostics investor-economics outputs that depend on verified total-return equivalence are allowed to render
  - `withheld`
    - drawdown-family and benchmark-relative investor-economics outputs are intentionally refused until total-return equivalence is verified

Contract rule:
- treat `withheld` as deliberate output suppression, not as a synonym for `availability.status = unavailable`
- use the explicit status and reason to interpret `null` history-derived fields

### `run_metadata.investor_economics_partial_unlock`

- explicit narrow exception contract that can be present while `run_metadata.investor_economics_status = withheld`
- current fields:
  - `mode`
    - `allowlisted_exact_slice_scalars_only`
    - only the named exact-slice scalars are admitted; broader investor-economics families remain withheld
  - `exact_slice_scalar_allowlist`
    - `range_metrics[*].summary.time_weighted_return_pct`
      - `unlock_condition = identical_admitted_exact_slice_only`
    - `range_metrics[*].summary.benchmark_return_pct`
      - `unlock_condition = identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only`
    - `range_metrics[*].summary.excess_return_pct`
      - `unlock_condition = identical_admitted_exact_slice_pair_only`
    - `runtime_enabled` is authoritative per allowlisted scalar
  - `client_derivation_rule`
    - `server_side_scalar_only_no_daily_series_subtraction_equivalence`
    - clients must not derive benchmark-relative or other path-derived outputs from daily series, local subtraction, rewindowing, or rebucketing
  - `withheld_families`
    - `benchmark_relative_series`
    - `benchmark_relative_path_derived_outputs`
    - `drawdown_family`
    - `rebucketed_window_summaries`
    - `rewindowed_range_summaries`
    - `diagnostics_benchmark_relative_outputs`
    - `replay_benchmark_relative_outputs`
    - `strategy_lab_benchmark_relative_outputs`

Contract rule:
- `run_metadata.investor_economics_status = withheld` remains the overall investor-economics state even when this partial unlock admits one or more exact-slice scalars
- clients must treat server-emitted allowlisted scalars as scalar-only exceptions and must not derive benchmark-relative, drawdown, or other path-derived outputs from daily series or from combinations of emitted fields

Contract rule:
- downstream consumers should treat `run_metadata` plus `provenance` as the authoritative interpretation layer for diagnostics availability and reliability
- `run_metadata.source_status` must not simply mirror `provenance.historical_basis`; it should describe actual source-health dimensions known at runtime

### `run_metadata.factor_model_parameters`

- grouped audit fields for the diagnostics factor-model configuration already known at runtime
- current fields:
  - `rolling_windows_days`
  - `current_reliability_window_days`
  - `minimum_window_observations`
  - `collinearity_warning_threshold`
  - `orthogonalization_basis`
  - `ridge_lambda`

Contract rule:
- these fields are the canonical diagnostics-side audit surface for factor-model windowing and regularization assumptions that would otherwise be buried in implementation details

### `run_metadata.reproducibility`

- grouped audit fields for reconstructing the effective input time basis of the diagnostics run
- current fields:
  - `input_imported_at`
  - `snapshot_as_of_date`
  - `history_start_date`
  - `history_end_date`
  - `dataset_version`

Contract rule:
- these fields are the current diagnostics-side reproducibility minimum for time-basis and dataset lineage; later contracts can add richer request hashes or dataset timestamps without reinterpreting this grouped shape

## Contract Rules

- `availability.historical_sections_available` answers whether historical diagnostics were successfully computed
- `availability.status` exposes the canonical availability state directly (`ok` or `unavailable`)
- `provenance` answers what kind of history basis those diagnostics used
- availability and provenance are separate dimensions and must not be conflated
- desktop review flows must not infer broker-truth history from `historical_sections_available = true` alone
- `historical_basis = market_data_history` must be treated as downgraded synthetic history, not as imported-history equivalence
- diagnostics can have `availability.status = ok` while `run_metadata.investor_economics_status = withheld`; this can coexist with `run_metadata.investor_economics_partial_unlock` for the narrow exact-slice scalar exception, while broader investor-economics families remain intentionally refused

## Unavailable-Path Messaging Rules

- snapshot-request diagnostics with no usable `PortfolioHistoryContext` must say that history context is missing and keep `history_context_required = true`
- imported-snapshot diagnostics with no reconstructable broker history must say imported history is insufficient and set `history_context_required = false`
- any diagnostics run that fails because benchmark or symbol market data cannot be loaded must describe that as a market-data availability problem and set `history_context_required = false`
- unavailable provenance and stress-scenario notes must match the actual failure reason rather than reusing the snapshot-request `PortfolioHistoryContext` wording for all paths

## Stress Scenario Availability

- unavailable diagnostics must not fabricate stress scenario returns
- when stress scenario support is unavailable, the diagnostics contract now returns:
  - `estimated_return_pct = null`
  - `status = unavailable`
- desktop should render that state explicitly rather than treating missing support as a true `0.0%` scenario outcome

## History-Derived Summary Fields

These summary blocks exist so downstream consumers can read key diagnostics fields without scraping deeper payload sections.

### `drawdown_summary`
- `current_drawdown_pct`
  - sourced from `volatility_regime.snapshot.current_drawdown_pct`
- `max_drawdown_pct`
  - sourced from `volatility_regime.snapshot.max_drawdown_pct`

Refusal rule:
- these fields may be `null` even when historical diagnostics are otherwise available
- when `run_metadata.investor_economics_status = withheld`, treat `null` drawdown values as intentionally refused outputs rather than generic unavailable history

### `volatility_summary`
- `portfolio_volatility_pct`
  - sourced from `risk_summary.portfolio_volatility_pct`
- `benchmark_volatility_pct`
  - sourced from `risk_summary.benchmark_volatility_pct`
- `downside_volatility_pct`
  - sourced from `volatility_regime.snapshot.downside_vol_60d`
- `tracking_error_pct`
  - sourced from `relative_risk.tracking_error_pct`

Benchmark-relative refusal rule:
- benchmark-relative investor-economics outputs such as `relative_risk.active_return_pct` and `relative_risk.information_ratio` may be `null` even when `availability.status = ok`
- in that case, `run_metadata.investor_economics_status` is the authoritative explanation for intentional refusal

### `risk_concentration_summary`
- `top_1_factor_risk_share`
- `top_3_factor_risk_share`
- `top_1_position_risk_share`
- `top_5_position_risk_share`
- `factor_hhi`
- `position_hhi`
- each field is sourced from `risk_contribution_breakdown.concentration`

## Summary Rules

- these summary blocks are history-derived diagnostics only
- unavailable diagnostics must return the summary objects with `null` field values rather than inferred placeholders
- withheld investor-economics outputs must also remain `null`; consumers must distinguish intentional withholding from broader diagnostics unavailability
- `risk_concentration_summary` must remain separate from any future current-state holdings concentration summary
- current-state holdings concentration belongs to the exposure-side contract, not the diagnostics history-derived summary contract
