# ETF Ranking Field Inventory

This document captures the current backend contract for shipped ETF ranking outputs, persisted artifacts, and recent-run discovery.

The preferred authoritative contract shape is now grouped into:
- `request`
- `effective_inputs`
- `run_metadata`

The grouped contract is now the authoritative shape for new consumers.

Legacy top-level ETF ranking fields remain present only for compatibility with existing consumers and should not be treated as the primary contract going forward.

Contract intent:
- `request` = normalized request intent
- `effective_inputs` = scoring-truth inputs actually used by the engine
- `run_metadata` = audit metadata describing run basis and reproducibility boundaries

Reproducibility guardrail:
- these fields describe only metadata that is truthfully authoritative at runtime today
- they do not imply dataset revision ids, holdings snapshot revision ids, exact execution timestamps, or code version pinning

## Persisted Artifact Surface

Routes:
- `POST /strategy-lab/etf-ranking`
  - runs the ETF ranking analysis and persists an immutable artifact before returning it
- `GET /strategy-lab/etf-ranking/artifacts/{artifact_id}`
  - reloads one persisted ETF ranking artifact by stable `artifact_id`

Current persisted artifact envelope:
- `schema_version`
  - current value: `etf_ranking_artifact_v1`
- `artifact_id`
  - stable persisted ETF ranking artifact identity
  - current ids use the `etf_ranking_artifact_` prefix

## Intent-Bound ETF Replacement Ranking Artifact v1

Routes:
- `POST /strategy-lab/etf-ranking/replacements`
  - additive strategy-lab alias that runs the same intent-bound ETF replacement ranking, persists the same immutable artifact, and returns the same persisted artifact contract
- `GET /strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}`
  - additive strategy-lab alias that reloads the same persisted replacement ranking artifact by stable `artifact_id`
- `POST /ranking/etf-replacements`
  - compatibility route that runs the same persisted intent-bound ETF replacement ranking flow but maps the canonical persisted result back into the legacy non-artifact POST response shape
- `GET /ranking/etf-replacements/artifacts/{artifact_id}`
  - compatibility alias that reloads the same persisted replacement ranking artifact by stable `artifact_id`

Current persisted artifact envelope:
- `schema_version`
  - current value: `intent_bound_etf_replacement_ranking_artifact_v1`
- `artifact_id`
  - stable persisted replacement ranking artifact identity
  - current ids use the `intent_bound_etf_replacement_ranking_artifact_` prefix

Authoritative boundary rules:
- persisted replacement artifacts are now the authoritative downstream truth for this ranking slice
- `POST /ranking/etf-replacements` preserves the legacy external response shape; artifact identity remains an internal persistence handoff on that route
- artifact-backed response access remains additive on `POST /strategy-lab/etf-ranking/replacements` and both artifact-load routes
- reload is artifact-id based only; it does not reconstruct request state, run preflight validation, or perform preview/open side effects
- validation/open/review semantics are intentionally unchanged in this slice
- new writes are strict and canonical; no silent repair is performed for malformed present values
- load failures remain fail-closed on missing file (`404`) and invalid json, non-object payload, schema failure, lineage contradiction, or canonical id mismatch (`400`)

Grouped artifact fields:
- `request`
  - persisted request envelope for intent binding
  - current fields:
    - `replacement_intent`
    - `seed_context`
    - `prefer_live_data`
    - `normalized_request`
- `effective_inputs`
  - canonical evaluated ranking inputs actually used by the engine
- `run_metadata`
  - deterministic methodology, date basis, source status, confidence, tie-break, and factor-weight metadata

Intent-binding lineage fields:
- `lineage.draft_id`
- `lineage.workspace_id`
- `lineage.base_node_id`
- `lineage.base_symbol`
- `lineage.candidate_symbol`
- `lineage.seed_ranking_id`
- `lineage.seed_methodology_id`
- `lineage.seed_ranking_basis_date`
- `lineage.peer_group`
- `lineage.benchmark_symbol`
- `lineage.lookback_months`

Candidate payload rules:
- `ranked_candidates[]` persists the full eligible ranked payload, including raw factors, normalized scores, and seeded lineage references
- `excluded_candidates[]` persists the full excluded payload with explicit exclusion reasons
- both candidate groups remain explicit; excluded names are not silently dropped

## Core Request Fields

Source schema:
- `services/quant-engine/app/schemas/research.py`

### `universe`
- requested symbols to rank
- symbols are normalized to uppercase in the backend

### `benchmark_symbol`
- benchmark used for benchmark-relative strength and aligned ranking windows
- ETF ranking routes preserve the shipped default of `SPY` when omitted
- intent-bound replacement ranking requests remain strict and require explicit seeded benchmark agreement

### `lookback_months`
- ranking lookback window in monthly bars
- must be at least `1`
- ETF ranking routes preserve the shipped default of `3` when omitted
- intent-bound replacement ranking requests remain strict and require explicit seeded lookback agreement

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

## Preferred Grouped Response Fields

Source schema:
- `services/quant-engine/app/schemas/research.py`
- ETF-specific grouped models now compose shared ranking base contracts from `services/quant-engine/app/schemas/ranking.py`

### `request`
- normalized request intent fields preserved for audit and downstream presentation
- current fields:
  - `universe`
  - `benchmark_symbol`
  - `lookback_months`
  - `prefer_live_data`
  - `peer_group`
  - `weights`
- `universe` is uppercase-normalized server-side before execution
- `weights` reflect request intent, not necessarily effective scoring truth

### `effective_inputs`
- engine-applied scoring truth used to produce the ranked output
- current fields:
  - `benchmark_symbol`
  - `lookback_months`
  - `price_basis`
  - `requested_universe`
  - `evaluated_universe`
  - `effective_peer_group`
  - `effective_component_weights`
  - `excluded_symbols`

#### `effective_inputs.requested_universe`
- uppercase-normalized universe after backend normalization

#### `effective_inputs.evaluated_universe`
- symbols that were actually ranked after deterministic exclusions
- should match `ranked_universe[].symbol` in rank order

#### `effective_inputs.effective_peer_group`
- echoes the applied request-level peer-group filter
- `null` means no peer-group filter was requested
- does not imply all ranked symbols had metadata-confirmed membership; warnings may still report unclassified symbols that remained eligible on price-history-only grounds

#### `effective_inputs.effective_component_weights`
- normalized weights actually used by the engine
- must be treated as scoring truth, not the raw request payload

#### `effective_inputs.excluded_symbols[]`
- deterministic exclusions applied before ranking
- mirrors the explicit top-level exclusion list for compatibility in slice one

### `run_metadata`
- run-basis audit metadata that explains how to interpret the result
- current fields:
  - `ranking_id`
  - `methodology_id`
  - `methodology`
  - `as_of_date`
  - `ranking_basis_date`
  - `price_basis`
  - `source_status`
  - `confidence`

#### `run_metadata.price_basis`
- current value is always `close` for shipped ETF ranking outputs and persisted artifacts

#### `run_metadata.methodology_id`
- stable methodology identifier for contract/audit use
- current value: `etf_ranking_methodology_v1`

#### `run_metadata.as_of_date`
- date basis used for the ranking output

#### `run_metadata.ranking_basis_date`
- currently the same as `as_of_date`
- split explicitly so later contracts can evolve without reinterpreting `as_of_date`

#### `run_metadata.source_status`
- explicit run-basis source context already known at runtime

#### `run_metadata.confidence`
- explicit audit-level copy of ranking confidence
- mirrors `warnings.confidence` for grouped contract readability in slice one

## Current Consumer Flow

- the desktop `ETF Ranking` surface is a current consumer of the persisted artifact contract
- current shipped behavior uses recent metadata discovery to populate available peer-group filters, recent artifact discovery to browse saved runs, and artifact loading to reopen one selected run
- a loaded persisted ETF ranking artifact can also seed the current desktop draft-review replacement flow

## Compatibility Top-Level Response Fields

The following top-level fields remain present for current consumers and must remain compatible in this slice:
- `ranking_id`
- `title`
- `as_of_date`
- `benchmark_symbol`
- `universe`
- `lookback_months`
- `price_basis`
- `methodology`
- `effective_peer_group`
- `effective_component_weights`
- `source_status`
- `warnings`
- `ranked_universe`
- `excluded_symbols`

## Recent Artifact Listing

Route:
- `GET /strategy-lab/etf-ranking/artifacts/recent`

Query params:
- `limit`
  - optional
  - current max: `100`
  - applied after invalid-row skipping, exact-match filtering, newest-first traversal, and `artifact_id` dedupe
- `effective_peer_group`
  - optional exact-match discovery filter against stored recent index rows
  - current values follow persisted artifact output, for example `Sector UCITS ETF`
  - `null` / omitted preserves current unfiltered behavior

Behavior rules:
- listing remains index-backed from `recent.jsonl`
- filtering is applied during the recent index scan before final dedupe/limit assembly
- ordering remains newest-first
- dedupe remains by `artifact_id`
- invalid index rows are skipped
- missing or corrupt artifact files do not affect recent listing because the index row is authoritative for this route

## Recent Artifact Discovery Metadata

Route:
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata`

Response fields:
- `available_effective_peer_groups`
  - unique non-null `effective_peer_group` values discovered from the same recent index scan used by the recent listing route
  - derived from `recent.jsonl` only; persisted artifact file presence or integrity does not matter
  - traversal remains newest-first and dedupe remains by `artifact_id` before value collection
  - invalid index rows are skipped
  - current response omits `null` values entirely

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
- warnings remain explicit and separate from `run_metadata`
- do not move warning interpretation into generic metadata or imply stronger certainty than the engine provides today

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
- downstream consumers should prefer `request`, `effective_inputs`, and `run_metadata` as the authoritative grouped shape
- top-level fields remain a compatibility surface in slice one and should not be treated as the long-term preferred audit shape
- excluded symbols must remain explicit through `excluded_symbols[]`; do not silently drop them
- `effective_peer_group` must echo the actual applied filter so downstream consumers can interpret exclusions correctly
- symbols without metadata may remain eligible if price history is sufficient; this must produce warnings rather than fabricated classification certainty
- peer-group filtering currently uses instrument category metadata only; do not overstate it as a full mandate-classification system
- do not imply dataset-version precision, holdings revision precision, persisted run identity, or exact execution-time provenance that the engine does not currently capture
