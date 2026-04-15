# ETF Ranking Field Inventory

This document captures the current backend contract for ETF ranking outputs used by the quant framework work.

## Core Request Fields

Source schema:
- `services/quant-engine/app/schemas/research.py`

### `universe`
- requested symbols to rank
- symbols are normalized to uppercase in the backend

### `benchmark_symbol`
- benchmark used for benchmark-relative strength and aligned ranking windows

### `lookback_months`
- ranking lookback window in monthly bars
- must be at least `1`

### `peer_group`
- optional request-level eligibility filter
- current implementation matches against `InstrumentRegistry` ETF `category`
- examples:
  - `Sector UCITS ETF`
  - `Bond UCITS ETF`
  - `Broad Market UCITS ETF`

### `weights`
- component weights for the ranking composite
- normalized server-side before scoring

## Core Response Fields

Source schema:
- `services/quant-engine/app/schemas/research.py`

### `effective_peer_group`
- echoes the applied request-level peer-group filter
- `null` means no peer-group filter was requested

### `effective_component_weights`
- normalized weights actually used by the engine
- must be treated as the scoring truth, not the raw request payload

### `ranked_universe[]`
- ranked eligible rows after deterministic exclusions

#### `ranked_universe[].instrument`
- metadata context from `InstrumentRegistry`
- current fields:
  - `symbol`
  - `name`
  - `asset_class`
  - `sector`
  - `category`
  - `currency`

#### `ranked_universe[].component_scores`
- component-by-component scoring breakdown
- current keys:
  - `momentum`
  - `benchmark_relative_strength`
  - `realized_volatility`
  - `downside_volatility`
  - `max_drawdown`
  - `liquidity`
  - `implementation_fit`

#### Current component labels / units
- `momentum`
  - label: `Blended momentum`
  - unit: `pct`
- `benchmark_relative_strength`
  - label: `Benchmark-relative strength`
  - unit: `pct`
- `realized_volatility`
  - label: `Realized volatility`
  - unit: `pct`
- `downside_volatility`
  - label: `Downside volatility`
  - unit: `pct`
- `max_drawdown`
  - label: `Max drawdown`
  - unit: `pct`
- `liquidity`
  - label: `Median dollar volume`
  - unit: `score`
- `implementation_fit`
  - label: `Implementation fit`
  - unit: `score`

### `excluded_symbols[]`
- deterministic exclusions that were evaluated but not ranked
- each row carries:
  - `symbol`
  - `reason`

Current explicit exclusion paths include:
- known non-ETF instrument metadata
- peer-group mismatch against known ETF category
- insufficient aligned price history for the benchmark-relative ranking window

### `warnings`
- non-fatal contract metadata for interpreting ranking quality

#### `warnings.confidence`
- current values:
  - `high`
  - `medium`
  - `low`

Current implementation uses conservative downgrade-to-`medium` rules when:
- some symbols lack instrument metadata
- some symbols could not be classified into the requested peer group
- implementation-fit support is incomplete across ranked rows

#### `warnings.warnings[]`
- human-readable warning messages
- should be shown as contract interpretation guidance, not ranking exclusions

#### `warnings.unknown_metadata_symbols[]`
- symbols that remained eligible using price history but had no `InstrumentRegistry` metadata

#### `warnings.peer_group_unclassified_symbols[]`
- symbols that remained eligible while a peer-group filter was requested, but no metadata classification existed to confirm the match

## Formula Notes

Current implemented ranking formulas in `services/quant-engine/app/services/strategy_lab.py`:
- momentum uses blended monthly momentum with conservative fallback on shorter histories
- liquidity uses `log(1 + median(close * volume))`
- volatility and drawdown are computed from the aligned ranking window
- implementation fit currently uses ETF holdings support as a proxy, not a full mandate-quality model

## Contract Rules

- ranking is deterministic; no hidden ML or non-deterministic scoring is allowed
- request-time eligibility and response-time warnings are separate concepts and must not be conflated
- excluded symbols must remain explicit through `excluded_symbols[]`; do not silently drop them
- `effective_peer_group` must echo the actual applied filter so downstream consumers can interpret exclusions correctly
- symbols without metadata may remain eligible if price history is sufficient; this must produce warnings rather than fabricated classification certainty
- peer-group filtering currently uses instrument category metadata only; do not overstate it as a full mandate-classification system
