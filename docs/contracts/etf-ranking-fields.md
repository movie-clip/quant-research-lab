# ETF Ranking Field Inventory

This document captures the current backend contract for shipped ETF ranking outputs, persisted artifacts, and recent-run discovery.

Additive rollout note:
- existing ETF-native ranking routes and replacement routes remain unchanged
- backend-only generalized ranking artifact discovery is now also shipped on additive strategy-lab routes
- persisted artifacts are the authoritative source for catalog and recent discovery; discovery does not recompute rankings
- persisted artifacts are now also the authoritative source for additive generalized ranking artifact preflight/open handoffs and typed review reopen payloads

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
- `recent.jsonl`
  - internal ETF-only operational index used to preserve ETF recent-listing discovery order
  - not part of the artifact payload contract, generalized artifact output, or deliverable surface

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
- additive generalized replacement open now also emits a backend-owned typed consumer handoff derived only from the persisted artifact after validation succeeds
- new writes are strict and canonical; no silent repair is performed for malformed present values
- load failures remain fail-closed on missing file (`404`) and invalid json, non-object payload, schema failure, lineage contradiction, or canonical id mismatch (`400`)

## Generalized Ranking Artifact Catalog And Recent Discovery v1

Routes:
- `GET /strategy-lab/ranking-artifacts/catalog`
  - additive backend-only catalog over supported persisted ranking artifact kinds
- `GET /strategy-lab/ranking-artifacts/recent`
  - additive backend-only recent discovery over supported persisted ranking artifact kinds

Request filter fields shared by both routes:
- `artifact_kind`
- `schema_version`
- `metadata_truth`
  - current supported value: `authoritative_persisted_metadata`
- `metadata_provenance`
  - supported values:
    - `persisted_artifact_body`
    - `persisted_etf_recent_index`
- `recency_same_day_provenance`
  - supported values:
    - `artifact_id`
    - `etf_recent_index`
- `methodology_id`
- `benchmark_symbol`
  - ETF-family only
- `effective_peer_group`
  - ETF-family only
- `base_symbol`
  - replacement-family only
- `candidate_symbol`
  - replacement-family only
- `peer_group`
  - replacement-family only
- `confidence`
- `status`
  - replacement-family only
- `as_of_date`
- `ranking_basis_date`
- `basis_date`
  - replacement-family only

Response metadata additions:
- `metadata.artifact_kind_registry_version`
  - current value: `ranking_artifact_kind_registry_v1`
  - explicit version for the backend-owned artifact-kind capability registry
- `metadata.supported_filters`
  - additive inventory of all discovery filter names recognized by the generalized discovery contract
- `metadata.artifact_kind_registry[].supported_schema_versions`
  - backend-owned closed enum sourced from a single canonical allowlist at the contract root
  - registry declarations must use explicit allowlisted values only; unknown, malformed, duplicate, or deprecated values fail closed before capabilities are advertised
  - expanding supported schema versions requires an explicit backend allowlist update; docs and tests must ship in the same change
- `metadata.artifact_kind_registry[]`
  - one entry per supported artifact kind
  - each entry declares:
    - `artifact_kind`
    - `supported_schema_versions`
    - `supported_filters`
  - this registry is discovery metadata only; it does not change persisted artifact truth, ranking behavior, replay behavior, or row payload derivation

Filter semantics:
- filters are additive exact-match constraints over authoritative persisted metadata only
- unsupported or malformed metadata states fail closed
- if a caller supplies `artifact_kind`, only the registry-declared filters for that kind are allowed; unsupported kind/filter combinations fail closed with `400`
- family-specific filters do not fabricate cross-family meanings; they simply exclude rows from other families

Supported kinds:
- `etf_ranking`
  - sourced from persisted ETF ranking artifacts
  - supported schema versions:
    - `etf_ranking_artifact_v1`
  - supported discovery filters:
    - `artifact_kind`
    - `schema_version`
    - `metadata_truth`
    - `metadata_provenance`
    - `recency_same_day_provenance`
    - `methodology_id`
    - `confidence`
    - `as_of_date`
    - `ranking_basis_date`
    - `benchmark_symbol`
    - `effective_peer_group`
- `intent_bound_etf_replacement_ranking`
  - sourced from persisted intent-bound ETF replacement ranking artifacts
  - supported schema versions:
    - `intent_bound_etf_replacement_ranking_artifact_v1`
  - supported discovery filters:
    - `artifact_kind`
    - `schema_version`
    - `metadata_truth`
    - `metadata_provenance`
    - `recency_same_day_provenance`
    - `methodology_id`
    - `confidence`
    - `as_of_date`
    - `ranking_basis_date`
    - `base_symbol`
    - `candidate_symbol`
    - `peer_group`
    - `status`
    - `basis_date`

Generalized row identity and ordering fields:
- `artifact_kind`
  - stable supported kind discriminator
- `artifact_id`
  - stable persisted artifact identity
- `schema_version`
  - persisted artifact schema version; unsupported versions fail closed
- `ranking_id`
- `methodology_id`
- `as_of_date`
- `ranking_basis_date`
- `recent_order_primary_date`
  - deterministic primary recent-order key
- `recent_order_secondary_date`
  - deterministic secondary recent-order key
- `recent_order_artifact_id`
  - deterministic final tie-break key
- `metadata`
  - `metadata_truth`
    - current shipped value: `authoritative_persisted_metadata`
  - `metadata_provenance`
    - labels the provenance of the returned row body metadata: `persisted_artifact_body` or fallback `persisted_etf_recent_index`
  - `matched_metadata_provenance`
    - additive rollout field; coexists with `metadata_provenance` during discovery-contract migration
    - labels the provenance that satisfied ETF recent discovery filtering/selection
    - for ETF recent rows enriched from the persisted artifact body after a recent-index match, this remains `persisted_etf_recent_index` while `metadata_provenance` remains `persisted_artifact_body`
  - `recency_same_day_provenance`
    - labels whether same-day ordering truth comes from `artifact_id` ordering or `etf_recent_index`

Kind-specific shallow summaries:
- ETF rows populate `etf_summary`
  - `benchmark_symbol`
  - `lookback_months`
  - `effective_peer_group`
  - `universe_size`
  - `evaluated_universe_size`
  - `confidence`
- replacement rows populate `replacement_summary`
  - `basis_date`
  - `status`
  - `base_symbol`
  - `candidate_symbol`
  - `peer_group`
  - `eligible_count`
  - `excluded_count`
  - `confidence`

Authoritative persisted metadata inventory:
- common authoritative metadata fields:
  - `artifact_kind`
  - `artifact_id`
  - `schema_version`
  - `ranking_id`
  - `methodology_id`
  - `as_of_date`
  - `ranking_basis_date`
  - `recent_order_primary_date`
  - `recent_order_secondary_date`
  - `recent_order_artifact_id`
  - `metadata.*`
- ETF authoritative metadata fields:
  - `etf_summary.benchmark_symbol`
  - `etf_summary.lookback_months`
  - `etf_summary.effective_peer_group`
  - `etf_summary.universe_size`
  - `etf_summary.evaluated_universe_size`
  - `etf_summary.confidence`
- replacement authoritative metadata fields:
  - `replacement_summary.basis_date`
  - `replacement_summary.status`
  - `replacement_summary.base_symbol`
  - `replacement_summary.candidate_symbol`
  - `replacement_summary.peer_group`
  - `replacement_summary.eligible_count`
  - `replacement_summary.excluded_count`
  - `replacement_summary.confidence`

Family-specific summaries:
- `etf_summary` and `replacement_summary` are shallow family-specific metadata summaries for discovery
- they are authoritative for the listed persisted metadata fields only
- they are not a substitute for loading the full artifact body when consumers need full ranking payloads

Recent discovery ordering rules:
- ETF recent discovery reuses the persisted ETF `recent.jsonl` index as the authoritative same-day ordering source; within the same `ranking_basis_date` and `as_of_date`, generalized recent preserves the persisted index sequence instead of re-sorting ETF ties by `artifact_id`
- replacement recent discovery derives ordering from authoritative persisted artifact metadata only: `ranking_basis_date`, then `as_of_date`, then `artifact_id`, descending
- generalized recent results merge supported kinds and apply deterministic descending ordering by `recent_order_primary_date` then `recent_order_secondary_date`; non-ETF kinds keep their explicit persisted metadata tie-breakers, while ETF same-day ties keep the ETF recent-index sequence
- generalized catalog uses persisted authoritative metadata only and does not recompute ranking outputs
- generalized recent evaluates ETF filters from persisted recent-index metadata first and only loads ETF artifact bodies where the existing response contract already requires row enrichment
- `metadata.applied_filters` is unchanged in this additive rollout; the new provenance field is row metadata only

Failure behavior:
- malformed persisted artifact json, non-object payloads, schema failures, unsupported schema versions, or canonical integrity mismatches fail closed
- malformed ETF recent-index json, non-object ETF recent-index rows, and ETF recent-index schema-invalid rows also fail closed on generalized catalog/recent discovery instead of being skipped
- unsupported artifact kinds or unsupported persisted schema states fail closed instead of being silently skipped or coerced
- unsupported `artifact_kind` and `schema_version` combinations also fail closed before discovery execution; callers cannot pair a kind with another kind's schema version
- malformed ranking artifact registry declarations also fail closed before discovery capability metadata is returned; this includes empty `supported_schema_versions`, misspelled values, unknown values, duplicates, and deprecated versions
- generalized ETF recent discovery remains index-backed for ordering and ETF filter narrowing only; when the shipped response contract requires enriched ETF row metadata, missing ETF artifact files fail closed rather than falling back to partial recent-index summaries
- ETF recent-index metadata is never allowed to contradict persisted ETF artifact identity or shallow summary fields; contradictions fail closed

## Generalized Ranking Artifact Preflight And Open v1

Routes:
- `POST /strategy-lab/ranking-artifacts/preflight/{artifact_id}`
  - additive backend-only preflight over supported persisted ranking artifact kinds
  - validates persisted artifact identity, kind support, schema support, integrity, and replay/open eligibility
  - does not produce the review/open payload directly
- `POST /strategy-lab/ranking-artifacts/open`
  - additive backend-only typed reopen route
  - accepts only the backend-owned `open_handoff` contract
  - does not accept loose `artifact_id` plus client overrides or mixed request shapes

Authoritative boundary rules:
- the persisted artifact body is the authoritative downstream truth for both preflight and open
- preflight and open remain distinct responsibilities: preflight proves eligibility and returns a typed handoff; open consumes that handoff and returns the typed review payload
- for replacement artifacts only, preflight computes open/replay eligibility from successful backend-owned consumer-handoff construction against the persisted artifact; it still does not return the consumer payload itself
- replacement artifacts no longer advertise a shipped state where review open succeeds but `consumer_handoff_supported = false`; truthful replacement eligibility is now exactly the canonical consumer-handoff/openability result
- review payloads are artifact-backed only and explicitly labeled with review truth semantics; they do not fabricate imported portfolio truth or synthetic current-state semantics
- new writes remain strict and canonical; legacy compatibility was not widened for this additive slice

Preflight response contract:
- `contract_version`
  - current value: `ranking_artifact_preflight_v1`
- `artifact`
  - authoritative persisted identity and audit metadata:
    - `artifact_kind`
    - `artifact_id`
    - `schema_version`
    - `ranking_id`
    - `methodology_id`
    - `as_of_date`
    - `ranking_basis_date`
- `eligibility`
  - current fields:
    - `review_truth_basis`
      - current value: `authoritative_persisted_ranking_artifact`
    - `review_scope`
      - current value: `artifact_backed_review_only`
    - `open_supported`
      - `true` when the specific persisted artifact instance can actually be reopened under the shipped contract
      - `false` when replacement consumer-handoff construction fails closed for that artifact instance
    - `replay_eligible`
      - `true` when the specific persisted artifact instance is replayable/openable under the shipped contract
      - `false` when replacement consumer-handoff construction fails closed for that artifact instance
    - `consumer_handoff_supported`
      - `false` for ETF ranking artifacts in this slice
      - `true` only when an intent-bound replacement artifact instance successfully passes canonical consumer-handoff construction
      - `false` when that replacement artifact instance fails closed as unreplayable or otherwise unconstructible for downstream handoff
    - `ineligibility_reason`
      - `null` when the artifact instance remains openable/replay-eligible
      - explicit fail-closed reason when `open_supported = false` and `replay_eligible = false`
- `open_handoff`
  - backend-owned typed handoff consumed verbatim by open:
    - `handoff_kind`
      - current value: `ranking_artifact_open_handoff_v1`
    - `artifact_kind`
    - `artifact_id`
    - `schema_version`
  - this exact object is the authoritative downstream input for open; desktop callers must not reconstruct or widen it locally

Open request contract:
- request body must be the exact `open_handoff` object
- `handoff_kind` is required and must be `ranking_artifact_open_handoff_v1`
- missing or unsupported `handoff_kind` fails at request binding with `422` even when `artifact_kind`, `artifact_id`, and `schema_version` otherwise match a real persisted artifact produced by preflight
- mixed payloads fail closed; callers cannot add loose fields, client overrides, or alternate artifact identity fields

Open response contract:
- `contract_version`
  - current value: `ranking_artifact_open_v1`
- `open_handoff`
  - echoes the validated typed handoff
- `review_payload_kind`
  - current supported values:
    - `etf_ranking_review_payload_v1`
    - `intent_bound_etf_replacement_ranking_review_payload_v1`
- `review_payload`
  - typed review payload with explicit truth labels
  - desktop consumers must branch on `review_payload.review_payload_kind` and `review_payload.artifact_kind`, not inferred local fields or persisted artifact assumptions alone
- `consumer_handoff`
  - present only for `intent_bound_etf_replacement_ranking` when `eligibility.consumer_handoff_supported = true`
  - backend-owned typed downstream handoff derived strictly from the reopened persisted replacement artifact after validation
  - omitted for ETF ranking opens in this slice to preserve the current ETF open payload shape

Typed review payload semantics:
- common truth labels on all review payloads:
  - `review_truth_basis`
    - current value: `authoritative_persisted_ranking_artifact`
  - `review_scope`
    - current value: `artifact_backed_review_only`
- ETF review payload:
  - `review_payload_kind = etf_ranking_review_payload_v1`
  - `artifact_kind = etf_ranking`
  - `schema_version = etf_ranking_artifact_v1`
  - `artifact`
    - full persisted `EtfRankingArtifact` body reopened from the authoritative artifact only
- intent-bound replacement review payload:
  - `review_payload_kind = intent_bound_etf_replacement_ranking_review_payload_v1`
  - `artifact_kind = intent_bound_etf_replacement_ranking`
  - `schema_version = intent_bound_etf_replacement_ranking_artifact_v1`
  - `artifact`
    - full persisted `IntentBoundEtfReplacementRankingArtifact` body reopened from the authoritative artifact only

Replacement consumer handoff semantics:
- `contract_version`
  - current value: `intent_bound_etf_replacement_ranking_consumer_contract_v1`
- `handoff_kind`
  - current value: `intent_bound_etf_replacement_ranking_consumer_handoff_v1`
- `artifact_kind`
  - current value: `intent_bound_etf_replacement_ranking`
- `artifact_id`
- `schema_version`
  - current value: `intent_bound_etf_replacement_ranking_artifact_v1`
- `ranking_id`
- `methodology_id`
- `basis_date`
- lineage identity fields:
  - `draft_id`
  - `workspace_id`
  - `base_node_id`
  - `base_symbol`
  - `candidate_symbol`
  - `seed_ranking_id`
  - `seed_methodology_id`
  - `seed_ranking_basis_date`
  - `peer_group`
  - `benchmark_symbol`
  - `lookback_months`
- replayability summary fields:
  - `eligible_count`
  - `excluded_count`
- `selected_candidate`
  - replacement-ranked row for the lineage-selected `candidate_symbol`
  - current required fields:
    - `symbol`
    - `rank`
    - `composite_score`
    - `basis_date`
    - `draft_id`
    - `base_node_id`
    - `base_symbol`
    - `seed_ranking_id`
    - `seed_methodology_id`

Replacement consumer handoff validation rules:
- open rejects replacement artifacts with unsupported status, empty ranked candidates, or missing lineage-selected candidate rows as unreplayable
- open rejects malformed consumer-handoff states when required selected-candidate fields are absent
- open rejects internal identity drift between consumer handoff fields and authoritative artifact lineage, run metadata, effective inputs, or ranked-candidate counts
- open rejects selected-candidate lineage drift when the ranked candidate no longer matches `candidate_symbol`, `base_symbol`, `seed_ranking_id`, `seed_methodology_id`, or `basis_date`
- no consumer handoff is synthesized from client request fields, preflight payloads, or loose overrides; persisted artifact truth is the only source
- preflight reuses this same canonical consumer-handoff construction path to determine replacement replay/open eligibility; it does not maintain a second weaker eligibility code path
- replacement preflight stays contract-synced with open: for shipped replacement artifacts, `open_supported`, `replay_eligible`, and `consumer_handoff_supported` now rise and fall together from that one canonical path
- desktop callers must fail closed on ambiguous replacement states and must not assume `consumer_handoff` exists for every replacement open payload

Failure behavior:
- missing artifact file fails closed with `404`
- request-shape and binding failures for missing or unsupported `handoff_kind`, mixed payloads, and other schema-invalid open request bodies fail closed with `422`
- invalid json, non-object payload, unsupported kind, unsupported schema version, integrity mismatch, handoff/artifact kind mismatch, handoff/artifact schema mismatch, preflight/open artifact identity mismatch, malformed replacement consumer handoff state, identity drift, and unreplayable replacement artifacts all fail closed with `400`
- preflight never silently becomes open and never returns the review payload
- replacement preflight eligibility also fails closed when persisted artifact integrity succeeds but canonical consumer-handoff construction does not; callers receive `open_handoff` plus `eligibility.ineligibility_reason`, not a synthesized consumer handoff

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
- current shipped behavior uses recent metadata discovery to populate available peer-group filters, recent artifact discovery to browse saved runs, then generalized ranking-artifact preflight plus typed open to reopen one selected run
- a loaded persisted ETF ranking artifact can also seed the current desktop draft-review replacement flow
- the desktop draft-review seed now stores backend-owned ranking artifact identity, typed `open_handoff`, and the shipped review-payload discriminator for the selected ETF review context
- desktop cached seeded-ranking restore accepts only canonical persisted review inputs with authoritative `artifactId` plus typed `openHandoff`; older raw draft records that lack those backend-owned fields are rejected instead of being reopened with inferred defaults
- the only documented legacy cache hydration on seeded-ranking restore is load-time backfill of missing `artifactKind`, `schemaVersion`, and `reviewPayloadKind` from the already-present canonical `openHandoff`; present malformed or contradictory fields still fail closed and new writes remain strict/canonical

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
- this ETF-native route is intentionally narrower than generalized discovery: it treats `recent.jsonl` as ephemeral operational state and does not widen generalized artifact-contract guarantees

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
