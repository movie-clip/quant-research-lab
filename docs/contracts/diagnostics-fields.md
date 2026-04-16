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

Contract rule:
- downstream consumers should treat `run_metadata` plus `provenance` as the authoritative interpretation layer for diagnostics availability and reliability

## Contract Rules

- `availability.historical_sections_available` answers whether historical diagnostics were successfully computed
- `availability.status` exposes the canonical availability state directly (`ok` or `unavailable`)
- `provenance` answers what kind of history basis those diagnostics used
- availability and provenance are separate dimensions and must not be conflated
- desktop review flows must not infer broker-truth history from `historical_sections_available = true` alone
- `historical_basis = market_data_history` must be treated as downgraded synthetic history, not as imported-history equivalence

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
