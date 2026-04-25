# Cross-Sectional Research Artifact Fields

This document captures the shipped backend contract for the initial persisted cross-sectional research run family.

Contract root:
- backend schemas and backend serialization are the authoritative contract root
- these outputs are hypothetical research artifacts only and are not portfolio, execution, or trading truth

## Shipped family

- canonical artifact kind: `cross_sectional_research_run`
- canonical schema version: `cross_sectional_research_artifact_v1`
- initial methodology slice: `alpha_quality_v1`
- scope: one persisted cross-sectional research run family that generalizes the narrow `alpha_quality_v1` methodology into a backend-owned research artifact contract

## Routes

- `POST /strategy-lab/cross-sectional-research/validate`
  - validates and builds the canonical preflight payload without persisting it
- `POST /strategy-lab/cross-sectional-research/run`
  - validates, builds, persists, and returns the canonical artifact
- `GET /strategy-lab/cross-sectional-research/artifacts/{artifact_id}`
  - reloads one persisted artifact by canonical artifact id with explicit response identity fields
- `GET /strategy-lab/cross-sectional-research/catalog`
  - lists persisted artifacts only
- `GET /strategy-lab/cross-sectional-research/recent`
  - lists newest persisted artifacts only

Boundary rules:
- validation and reload/open remain distinct
- validate is preflight only and does not persist
- reload, catalog, and recent consume persisted artifacts only
- new writes are strict and canonical
- load failures fail closed on missing file, invalid json, non-object payload, schema mismatch, integrity mismatch, summary/provenance contradictions, and reload identity mismatches

## Request contract

- `methodology_id`
  - current value: `alpha_quality_v1`
- `rebalance_date`
- `as_of_date`
- `holdout_start_date`
- `dataset_version`
- `universe_definition`
- `benchmark`
  - `benchmark_symbol`
  - `benchmark_name`
  - `benchmark_kind`
- `universe_symbols`
- `fundamental_snapshots`
  - uses the locked backend PIT alpha snapshot schema
  - each present array entry must be a complete snapshot object with canonical required fields including `symbol`, `statement_date`, and literal `period_type`; malformed, partial, or non-canonical present values fail closed
- `source_name`
- `replay_id`
- `top_ranked_count`

## Validation response

- `valid`
- `artifact_kind`
- `schema_version`
- `would_persist_artifact_id`
- `would_persist_fingerprint`
- `normalized_request`
- `methodology`
- `methodology_metadata_v1`
- `status_metadata_v1`
- `provenance_metadata_v1`
- `assumptions`
- `dataset_version`
- `universe_definition`
- `benchmark`
- `walk_forward_summary`
- `holdout_summary`
- `provenance`

## Persisted artifact

- `schema_version`
- `artifact_kind`
- `artifact_id`
  - canonical stable id with prefix `cross_sectional_research_artifact_`
- `fingerprint`
  - full sha256 digest of canonical payload content excluding identity fields
- `run_id`
- `persisted_at`
  - canonical UTC persistence timestamp in `YYYY-MM-DDTHH:MM:SSZ` form
- `methodology_id`
- `request`
- `methodology`
- `methodology_metadata_v1`
- `status_metadata_v1`
- `provenance_metadata_v1`
- `assumptions`
- `dataset_version`
- `universe_definition`
- `benchmark`
- `walk_forward_summary`
- `holdout_summary`
- `provenance`

Integrity rules:
- `artifact_kind` must remain `cross_sectional_research_run`
- `schema_version` must remain `cross_sectional_research_artifact_v1`
- `artifact_id` must match canonical artifact content
- `fingerprint` must match canonical artifact content
- `persisted_at` is the sole authoritative recency source for discovery ordering
- persisted values for `dataset_version`, `universe_definition`, `benchmark`, and `methodology_id` must remain aligned with `request`
- `methodology_metadata_v1` is strict, canonical, backend-owned metadata; blank, non-canonical, or contradictory present values fail closed on reload and discovery
- `status_metadata_v1` and `provenance_metadata_v1` are additive, descriptive-only metadata; malformed present values fail closed on reload and discovery
- current artifacts must persist both metadata blocks canonically; desktop consumers do not derive or backfill them locally
- `provenance.source_name` and `provenance.replay_id` must remain aligned with persisted `request`
- `walk_forward_summary` and `holdout_summary` must keep canonical split labels, request-aligned universe size, and request/provenance-aligned summary provenance fields
- summary symbol lists must stay canonical uppercase, duplicate-free, and bounded by `sample_count`

## Status metadata v1

- distinct from `methodology_metadata_v1`, compact summary provenance, and artifact provenance
- persisted and discovery-visible, but descriptive only; it does not change analytics logic, truth semantics, validation responsibilities, or discovery ordering
- explicit unknown/unsupported states are reserved for persisted payload compatibility and must not be silently coerced

Fields:
- `artifact_status`
  - allowed values: `complete`, `degraded`, `unknown`, `unsupported`
- `diagnostics_status`
  - allowed values: optimizer diagnostics `ok` or `invalid`, plus `unknown` and `unsupported`
- `coverage_status`
  - allowed values: `complete`, `partial`, `unknown`, `unsupported`

Status semantics:
- `artifact_status` and `coverage_status` are orthogonal descriptive fields
- coverage completeness does not imply artifact completeness
- degraded diagnostics/artifact state may coexist with `coverage_status=complete` when persisted diagnostics/provenance still justify full coverage
- `diagnostics_status` equality with persisted `provenance.alpha_diagnostics_status` remains required
- persisted `coverage_status` must still match `provenance.complete_coverage_ratio`

Current backend-owned write behavior:
- `artifact_status` is `complete` when alpha diagnostics are `ok`, otherwise `degraded`
- `diagnostics_status` mirrors persisted `provenance.alpha_diagnostics_status`
- `coverage_status` is `complete` when `provenance.complete_coverage_ratio == 1.0`, otherwise `partial`

Validation note:
- producer write behavior above remains canonical for new backend writes
- current persisted artifacts must carry canonical `status_metadata_v1`; missing metadata is legacy-only and may be hydrated only at backend reload/load boundaries for old payloads
- reload/discovery validation must not infer `artifact_status` solely from diagnostics if that would reject an otherwise valid persisted degraded-plus-complete status combination
- other malformed or contradictory present status combinations still fail closed

## Provenance metadata v1

- distinct from `methodology_metadata_v1`, compact summary provenance, and artifact provenance
- persisted, backend-owned, discovery-visible metadata; exact-match discovery filters may read these persisted fields only
- discovery filtering is descriptive only; it does not change methodology execution, truth semantics, validation or reload responsibilities, or recency ordering
- explicit unknown/unsupported states are reserved for persisted payload compatibility and must not be silently coerced

Fields:
- `input_source_kind`
  - allowed values: `direct_snapshot_input`, `replay_snapshot_input`, `backend_owned_other`, `unknown`, `unsupported`
- `replay_provenance_status`
  - allowed values: `present`, `absent`, `unknown`, `unsupported`
- `benchmark_source_kind`
  - allowed values: `request_benchmark_reference`, `unknown`, `unsupported`
- `alpha_source_kind`
  - allowed values: `optimizer_alpha_package`, `unknown`, `unsupported`

Current backend-owned write behavior:
- `input_source_kind` is sourced only from persisted request inputs: `replay_id` presence and canonical `source_name`
- `replay_provenance_status` is `present` only when persisted `request.replay_id` is present
- `benchmark_source_kind` remains `request_benchmark_reference`
- `alpha_source_kind` remains `optimizer_alpha_package`

Load boundary note:
- current persisted artifacts must carry canonical `provenance_metadata_v1`
- missing provenance metadata is legacy-only and may be hydrated only inside backend artifact load/reload for documented old payloads
- discovery/catalog/recent do not hydrate missing metadata and instead fail closed on those persisted payloads

## Methodology metadata v1

- `methodology_family_id`
- `methodology_family_version`
- `active_methodology_id`
- `active_methodology_version`
- `alpha_package_version`
- `alpha_methodology_id`
- `alpha_input_contract_id`
- `score_basis`
- `benchmark_role`
- `partition_rule`
- `output_shape`
- `component_signal_ids`

Semantics:
- descriptive-only metadata owned by backend research construction logic
- persisted, backend-owned, discovery-visible metadata; exact-match discovery filters may read supported persisted fields only
- does not replace or repurpose `methodology` or `assumptions`; those remain descriptive-only narrative fields
- discovery filtering is descriptive only; it does not change methodology execution, truth basis, validation or reload responsibilities, or recency ordering
- load and discovery continue to use persisted artifact metadata as the sole authority

## Compact summary fields

Both `walk_forward_summary` and `holdout_summary` expose only compact review outputs:

- `split_label`
- `sample_count`
- `universe_size`
- `coverage_ratio`
- `complete_coverage_ratio`
- `mean_score`
- `median_score`
- `positive_score_share`
- `top_ranked_symbols`
- `effective_start_date`
- `effective_end_date`
- `provenance`

Summary provenance fields:
- `alpha_package_id`
- `alpha_package_version`
- `alpha_methodology_id`
- `input_digest`
- `source_name`
- `as_of_date`
- `rebalance_date`
- `holdout_start_date`
- `benchmark_symbol`
- `benchmark_kind`
- `partition_rule`

Summary integrity rules:
- summary provenance remains artifact-backed metadata only; reload/catalog/recent must not rebuild it from query or request inputs
- `alpha_package_id`, `alpha_package_version`, and `input_digest` must match persisted artifact `provenance`
- `source_name`, dates, benchmark symbol, and benchmark kind must match persisted `request`
- `partition_rule` must remain the canonical backend-owned rule text

## Artifact provenance fields

- `source_name`
- `replay_id`
- `input_digest`
- `alpha_input_contract_id`
- `point_in_time_only`
- `alpha_package_id`
- `alpha_package_version`
- `alpha_diagnostics_status`
- `coverage_ratio`
- `complete_coverage_ratio`
- `missing_snapshot_symbols`
- `stale_symbols`
- `lag_blocked_symbols`
- `fallback_symbols`

## Reload response

- `contract_version`
  - current value: `cross_sectional_research_reload_v1`
- `requested_artifact_id`
- `artifact_id`
- `artifact_kind`
- `schema_version`
- `artifact`
  - full persisted artifact payload

Reload identity rules:
- `requested_artifact_id`, top-level `artifact_id`, and `artifact.artifact_id` must match exactly
- top-level `artifact_kind` and `schema_version` must match the persisted artifact body exactly
- missing artifact ids return `404`; malformed persisted artifacts, unsupported kind/schema, contradictions, and response identity mismatches fail closed with `400`

## Catalog row

- `artifact_id`
- `fingerprint`
- `artifact_kind`
- `schema_version`
- `methodology_id`
- `methodology_metadata_v1`
- `status_metadata_v1`
- `provenance_metadata_v1`
- `dataset_version`
- `universe_definition`
- `benchmark_symbol`
- `as_of_date`
- `rebalance_date`
- `holdout_start_date`
- `recent_order_persisted_at`
- `recent_order_artifact_id`
- `universe_size`
- `walk_forward_sample_count`
- `holdout_sample_count`
- `alpha_diagnostics_status`

Catalog row identity and validation rules:
- `artifact_kind` must remain `cross_sectional_research_run`
- `schema_version` must remain `cross_sectional_research_artifact_v1`
- `recent_order_artifact_id` must match `artifact_id`

## Recent row

- `artifact_id`
- `fingerprint`
- `methodology_id`
- `methodology_metadata_v1`
- `status_metadata_v1`
- `provenance_metadata_v1`
- `dataset_version`
- `universe_definition`
- `benchmark_symbol`
- `recent_order_persisted_at`
- `recent_order_artifact_id`
- `rebalance_date`
- `as_of_date`
- `holdout_start_date`
- `universe_size`
- `walk_forward_sample_count`
- `holdout_sample_count`

Recent row identity and validation rules:
- `recent_order_artifact_id` must match `artifact_id`
- `methodology_id` is currently required and must be the canonical non-null literal `alpha_quality_v1`; null, blank, or non-canonical present values fail closed
- malformed `methodology_metadata_v1`, `status_metadata_v1`, or `provenance_metadata_v1` objects fail closed

## Discovery filters

- `artifact_kind`
- `schema_version`
- `methodology_id`
- `dataset_version`
- `universe_definition`
- `benchmark_symbol`
- `rebalance_date`
- `as_of_date`
- `holdout_start_date`
- `methodology_family_id`
- `methodology_family_version`
- `active_methodology_version`
- `alpha_package_version`
- `alpha_methodology_id`
- `alpha_input_contract_id`
- `score_basis`
- `benchmark_role`
- `partition_rule`
- `output_shape`
- `artifact_status`
- `diagnostics_status`
- `coverage_status`
- `input_source_kind`
- `replay_provenance_status`
- `benchmark_source_kind`
- `alpha_source_kind`

Filter semantics:
- exact-match only
- persisted-artifact metadata only
- additive backend-owned metadata filters read only from authoritative persisted `methodology_metadata_v1`, `status_metadata_v1`, and `provenance_metadata_v1` fields
- discovery filtering is discovery-only and does not change methodology execution, truth semantics, validation or reload responsibilities, or widen legacy compatibility beyond documented load-time hydration
- descriptive metadata filters do not redefine recency ordering; `recent` stays `persisted_at` descending, then `artifact_id` descending for deterministic ties
- `recent` ordering is `persisted_at` descending, then `artifact_id` descending for deterministic ties
- blank or non-canonical present values fail closed
- `catalog` and `recent` fail closed if any persisted artifact contains malformed or contradictory present metadata instead of skipping or reconstructing rows

## Discovery metadata semantics

- `contract_version`: `cross_sectional_research_discovery_v1`
- `methodology_metadata_v1_semantics`: `descriptive_only`
- `status_metadata_v1_semantics`: `descriptive_only`
- `provenance_metadata_v1_semantics`: `descriptive_only`

Consumer contract note:
- desktop consumers must treat backend schema-backed payloads as the sole authoritative downstream input for validation previews, persisted artifact reload, catalog, and recent flows
- desktop rendering must display backend-owned research state labels from `status_metadata_v1` and `provenance_metadata_v1` directly rather than inferring substitute meanings locally
- any documented legacy metadata backfill is backend-owned at artifact load boundaries only; desktop reload parsing fails closed if those fields are absent or malformed in the response payload
