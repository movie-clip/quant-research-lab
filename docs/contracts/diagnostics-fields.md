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

## Contract Rules

- `availability.historical_sections_available` answers whether historical diagnostics were successfully computed
- `provenance` answers what kind of history basis those diagnostics used
- availability and provenance are separate dimensions and must not be conflated
- desktop review flows must not infer broker-truth history from `historical_sections_available = true` alone

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
