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
    - `live_market_data`
    - `unavailable`
  - `factor_history`
    - `live_market_data`
    - `unavailable`

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

### `volatility_summary`
- `portfolio_volatility_pct`
  - sourced from `risk_summary.portfolio_volatility_pct`
- `benchmark_volatility_pct`
  - sourced from `risk_summary.benchmark_volatility_pct`
- `downside_volatility_pct`
  - sourced from `volatility_regime.snapshot.downside_vol_60d`
- `tracking_error_pct`
  - sourced from `relative_risk.tracking_error_pct`

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
- `risk_concentration_summary` must remain separate from any future current-state holdings concentration summary
- current-state holdings concentration belongs to the exposure-side contract, not the diagnostics history-derived summary contract
