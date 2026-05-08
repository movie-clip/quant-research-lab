# Construction Run v1

`construction/run` is the first-class persisted backend construction engine for deterministic target-weight artifacts.

V1 supports a narrow persisted policy set and consumes ranked candidates as an input artifact rather than re-ranking inside construction.

## Persistence

- `POST /construction/run` persists the canonical artifact before returning it
- `POST /construction/ranking-artifacts/preflight/{artifact_id}` is the canonical validation/preflight producer for the typed ranking-artifact to construction handoff for the two shipped ranking families: `etf_ranking` and `intent_bound_etf_replacement_ranking`
- `GET /construction/policies` exposes backend-owned read-only discovery for the shipped persisted policy catalog
- persisted artifacts use stable `artifact_id` as the storage key under the construction artifact store
- storage is immutable with write-once semantics; identical rewrites are tolerated, conflicting rewrites are rejected
- `GET /construction/artifacts/{artifact_id}` loads the persisted artifact, validates it on read, and fails closed on corruption
- both feasible and infeasible valid artifacts persist; malformed requests do not persist

## Policy catalog discovery

- the shipped policy catalog remains intentionally narrow and currently includes:
  - `top_n_equal_weight_v1`: equal weight across the selected names
  - `top_n_inverse_rank_weight_v1`: weights proportional to `1 / selected_order_rank`, normalized to sum to `1.0`
  - `top_n_linear_rank_weight_v1`: weights proportional to selected-order linear numerators `N..1`, normalized to sum to `1.0`
- each shipped catalog definition carries a backend-owned immutable `policy_definition_id`, and newly persisted artifacts stamp the resolved definition id in `normalized_inputs.policy_definition_id`
- discovery metadata is additive, backend-owned, and descriptive only; it documents catalog fields such as `family`, `constraints`, `inputs`, `determinism`, `ranking_support`, explicit constraint capability flags, explicit required input flags, and canonical `launch_profile` metadata for the narrow ranking-artifact review/handoff launch boundary
- discovery metadata does not change persisted artifact truth, validation/preflight behavior, preview/open contracts, or replay math
- `GET /construction/policies` supports exact-match server-side filtering over backend-owned catalog metadata fields only: `family`, `constraints`, `inputs`, `determinism`, `ranking_support`, `full_investment_constraint`, `long_only_constraint`, `eligible_ranked_universe_constraint`, `max_position_weight_constraint`, `min_position_weight_constraint`, `max_turnover_weight_constraint`, `max_trade_intent_count_constraint`, `ranked_universe_input`, `current_portfolio_input`, and `launch_top_n`
- only those documented filter keys are accepted; requests with any unsupported query parameter key are rejected at the route boundary rather than ignored or widened
- the shipped ranking-artifact launch boundary is explicit in discovery: every catalog row stamps `launch_top_n = 2`, and every row also carries canonical `launch_profile` metadata for `ranking_artifact_review_handoff_v1`
- canonical launch-profile rules are fail-closed: exactly one profile default row must exist, `top_n_equal_weight_v1` must be that default row, `top_n_linear_rank_weight_v1` may only appear as `opt_in`, `top_n_inverse_rank_weight_v1` must remain `excluded`, and launch-profile metadata must agree with each row's `policy_id`, `policy_definition_id`, `ranking_support`, and `launch_top_n`
- desktop ranking-artifact launch consumers are expected to derive launch compatibility/default state from `launch_profile` and to block launch rather than fall back to hardcoded allowlists or hardcoded defaults when that metadata is malformed or contradictory
- filter evaluation is metadata-only and does not inspect persisted artifacts, client review state, replay inputs, or open/preview payloads
- malformed present values for supported filter keys, including empty strings and non-canonical typed values, fail closed at the route boundary; repeated instances of any supported scalar filter key also fail closed with `422`, even when every repeated value is individually valid or identical
- the route preserves single-value exact-match semantics only; it does not add list matching, OR semantics, widening, coercion, or broader catalog fallbacks
- `/construction/run`, persisted artifact fields and semantics, legacy load compatibility, and replay/open behavior remain unchanged by this discovery expansion

## Deterministic policy execution

- normalizes ranked candidates and current portfolio weights into a stable auditable input payload
- `POST /construction/run` now accepts exactly one ranking input source: the legacy inline `ranked_universe` payload or the backend-owned `ranking_artifact_handoff`
- the new handoff path is additive only and loads the authoritative persisted ETF ranking artifact before deriving the existing construction ranked-candidate input from artifact truth
- the shipped handoff launch boundary supports exactly two persisted ranking families: `etf_ranking` and `intent_bound_etf_replacement_ranking`
- mixed inline-plus-handoff payloads, malformed or unsupported handoff states, missing artifacts, unsupported artifact kind/schema states, identity mismatches, corrupt persisted artifacts, and empty or unusable eligible ranking states fail closed
- the shipped ranking-artifact handoff launch boundary also requires `policy.top_n = 2`; broader inline construction still remains available for backend/core tests and non-launch-boundary use, but the desktop launch path is intentionally frozen at `2`
- `ranked_universe.artifact_id` remains descriptive inline provenance only and is not treated as an implicit artifact-backed handoff substitute
- resolves the requested policy definition once, then executes the catalog-owned deterministic selection pipeline for that policy
- captures the ordered `selection_rule_trace` during policy execution and persists that trace on the artifact
- newly persisted artifacts also stamp additive `weighting_trace_v1` plus `weighting_trace_status` as the authoritative persisted explanation source for policy-specific weight derivation
- newly persisted artifacts also stamp additive `turnover_diagnostics_v1` plus `turnover_diagnostics_status` as the authoritative persisted explanation source for reported construction turnover diagnostics
- `weighting_trace_v1` is explicitly labeled `artifact_backed_hypothetical_construction_diagnostics_only`; it is artifact-backed diagnostics for hypothetical construction, not portfolio truth, advisory interpretation, or replay authorization
- `turnover_diagnostics_v1` is explicitly labeled `artifact_backed_hypothetical_construction_diagnostics_only`; it is artifact-backed diagnostics for hypothetical construction, not portfolio truth, advisory interpretation, or replay authorization
- the trace records the resolved `policy_id` and `policy_definition_id`, the canonical ordered weighting stages, per-selected-position pre/post values for already-computed engine steps, normalization decisions used to reach seed weights, and whether final target weights were persisted or withheld because the artifact is infeasible
- turnover diagnostics record the reported turnover value, the persisted basis/method label, explicit inclusion and exclusion flags, and persisted links to trade-intent, feasibility, and turnover-constraint diagnostic context already produced by the engine
- turnover diagnostics now also persist stable per-symbol `symbol_contributions` ordered by canonical symbol ascending so the reported aggregate turnover can be reconciled directly back to current weights, target weights, and existing trade-intent semantics without recomputing alternate math paths
- each `symbol_contributions[]` row uses weight units, not percent strings: `current_weight`, `target_weight`, and signed `delta_weight` are portfolio weights; `absolute_delta_weight = abs(delta_weight)`; `turnover_contribution_weight = 0.5 * absolute_delta_weight` after canonical 8-decimal reconciliation; `contribution_fraction_of_reported_turnover` is unitless in `[0,1]` and sums to `1.0` only when reported turnover is positive
- sign conventions stay diagnostic-only and match existing trade-intent semantics: positive `delta_weight` means net buy/initiation, negative `delta_weight` means net sell/exit, zero means hold; `action` is one of `initiate`, `buy`, `sell`, `exit`, or `hold` under the existing source-of-truth turnover inputs
- zero-delta names remain present when they are part of the current/target symbol union so diagnostics can explain unchanged positions; those rows set `included_in_reported_turnover = false`, `turnover_contribution_weight = 0.0`, and `contribution_fraction_of_reported_turnover = 0.0` when aggregate reported turnover is positive or `null` when aggregate reported turnover is zero
- empty behavior is strict and stable: when target weights are not generated, `reported_value_status = not_computed_no_generated_target_weights` and `symbol_contributions = []`; when turnover is computed over an empty union there are likewise no rows; otherwise the row shape is fixed for every symbol in the union of current and generated target weights
- weighting trace persistence is observational only and must not alter weighting math, normalization, constraint application, rounding, or final target weights
- turnover diagnostics persistence is observational only and must not alter construction math, turnover math, constraint math, feasibility logic, or replay math
- preserves the requested `policy_id` while also exposing the backend definition id through policy discovery and replay provenance
- separates deterministic selection from policy-specific weighting while keeping both behaviors catalog-owned
- execution now resolves shipped policy metadata, selection rule ordering, weighting behavior, and policy-derived failure or cutoff messaging from the backend policy catalog seam rather than scattering policy ids through the run service
- enforces only the shipped V1 constraint family: `full_investment`, `long_only`, `eligible_ranked_universe_only`, `max_position_weight`, optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count`
- evaluates constraints against the actual generated target weights for the chosen policy
- persists normalized `hard_constraints.min_position_weight` into canonical artifacts via both `hard_constraints.min_position_weight` and `normalized_inputs.min_position_weight`; downstream load, validation, preview, and replay consume that persisted artifact truth rather than reconstructing the field
- persists normalized `hard_constraints.max_trade_intent_count` into canonical artifacts via both `hard_constraints.max_trade_intent_count` and `normalized_inputs.max_trade_intent_count`; downstream load, validation, preview, and replay consume that persisted artifact truth rather than reconstructing the field
- `min_position_weight` is additive-only hard-constraint support for `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- `max_trade_intent_count` is additive-only hard-constraint support for `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- when present, `min_position_weight` is evaluated fail-closed as a hard feasibility constraint against canonical policy outputs; contradictory, malformed, unsupported, or infeasible present states are rejected on run, artifact load, validation, and replay/open consumption
- when present, `max_trade_intent_count` is evaluated fail-closed as a hard feasibility constraint against the persisted canonical `trade_intents` length from the artifact itself, not client-reconstructed state or turnover diagnostics
- explicit infeasibility reasons are emitted when `min_position_weight` exceeds `max_position_weight`, when full investment cannot accommodate the requested minimum across the selected count, or when the persisted policy output itself falls below the requested minimum
- when the generated canonical `trade_intents` exceed `max_trade_intent_count`, the artifact persists as infeasible with explicit `trade intent count exceeds max_trade_intent_count` failure semantics and the canonical `trade_intents` remain persisted on that failure path so the stored constraint evaluation can be validated from artifact truth
- defines turnover as `0.5 * sum(abs(target_weight - current_weight))` over the union of current and target symbols, so initiates and exits both count toward the cap
- canonical artifact identity treats omitted and explicit `null` `hard_constraints.max_turnover_weight` values as equivalent, while preserving `0.0` as a real turnover cap
- canonical artifact identity likewise treats omitted and explicit `null` `hard_constraints.min_position_weight` values as equivalent, while preserving positive present values as real hard constraints
- applies `hard_constraints.max_turnover_weight` only after target weights are generated; when omitted or explicit `null`, turnover is not constrained and prior behavior is unchanged
- returns an infeasible persisted artifact when the generated target portfolio exceeds `max_turnover_weight`, with an explicit turnover failure reason and a populated `max_turnover_weight` constraint evaluation
- fails closed on unsupported policy resolution before selection, weighting, or artifact persistence; no fallback execution path is applied

## Artifact provenance validation

- persisted construction artifact canonicalization now includes `normalized_inputs.policy_definition_id`, so definition provenance changes deterministically change both `fingerprint` and `artifact_id`
- handoff-backed construction artifacts also persist authoritative ranking provenance in `normalized_inputs`, including `ranked_universe_artifact_kind`, `ranked_universe_artifact_id`, and `ranked_universe_artifact_schema_version`
- artifact load validates that the persisted `policy_definition_id` still matches the currently resolved catalog definition for the persisted `policy_id`
- artifact load also fails closed on populated-but-invalid `weighting_trace_v1` states, including unsupported trace versions, malformed or partial stage payloads, mismatched policy metadata, inconsistent stage chaining, or binding states that contradict persisted artifact outputs
- artifact load also fails closed on populated-but-invalid `turnover_diagnostics_v1` states, including unsupported diagnostics versions, malformed or partial turnover payloads, mismatched requested/limit/evaluation states, inconsistent trade-intent counts, or feasibility links that contradict persisted artifact outputs
- load-path compatibility repairs only the exact legacy case where `normalized_inputs.policy_definition_id` is absent by resolving the persisted `policy_id` during load, while canonical `fingerprint` and `artifact_id` validation still run against the original stored payload before hydration
- load-path compatibility also repairs only the exact legacy case where the artifact predates turnover-diagnostics persistence and both `turnover_diagnostics_status` and `turnover_diagnostics_v1` are absent; those artifacts load with explicit `turnover_diagnostics_status = unavailable_legacy_artifact` and `turnover_diagnostics_v1 = null`
- load-path compatibility also repairs only the exact legacy case where the artifact predates this slice and both `weighting_trace_status` and `weighting_trace_v1` are absent; those artifacts load with explicit `weighting_trace_status = unavailable_legacy_artifact` and `weighting_trace_v1 = null`
- load-path compatibility also repairs only the exact legacy case where `hard_constraints.max_trade_intent_count`, `normalized_inputs.max_trade_intent_count`, and the matching constraint evaluation are absent; those artifacts hydrate as omitted/not-requested only during load
- write-path behavior stays strict: newly persisted artifacts must stamp `normalized_inputs.policy_definition_id`, and populated null, malformed, or mismatched values still fail closed on load and replay
- replay continues to use persisted baseline and candidate weights; any discovery metadata or replay provenance extension remains additive and does not alter replay math

## Replay provenance

- `POST /backtests/portfolio-allocation/construction-artifact-validation` is the canonical producer of the typed `preview_handoff` boundary for downstream open/preview
- `POST /backtests/portfolio-allocation/construction-artifact-preview` consumes that `preview_handoff` as the authoritative validation-to-preview contract
- compatibility with the legacy preview request shape remains additive only; when a payload presents the handoff shape it must validate as a complete supported handoff, and mixed handoff-plus-legacy payloads fail closed
- handoff consumption fails closed on missing or unsupported `handoff_kind` and on any construction artifact id mismatch surfaced by persisted artifact integrity validation
- replay provenance requires the persisted `selection_rule_trace` from the referenced artifact
- `selection_rule_trace` is descriptive provenance only and does not authorize replay/open behavior or drive replay weights or math
- replay/open now read turnover diagnostics from the persisted artifact only; they do not recompute turnover provenance from loose fields during preview/open
- artifact-backed preview/open fails closed when turnover diagnostics are present but missing, malformed, ambiguous, or unsupported for the persisted contract version
- replay/open now also echo persisted construction `hard_constraints`, including additive `min_position_weight` and additive `max_trade_intent_count`, directly from the artifact-backed contract without mutating replay methodology or portfolio analytics behavior
- replay provenance now also echoes the persisted `weighting_trace_status` and `weighting_trace_v1` fields without reconstructing or mutating them client-side
- replay provenance now also echoes the persisted `turnover_diagnostics_status` and `turnover_diagnostics_v1` fields without reconstructing or mutating them client-side

Legacy note:
- legacy persisted artifacts still normalize missing, null, or empty-object `selection_rule_trace` payloads to an empty trace during artifact loading only
- legacy persisted artifacts missing `normalized_inputs.policy_definition_id` are hydrated from the persisted `policy_id` during artifact loading only
- legacy persisted artifacts that predate weighting-trace persistence surface explicit trace-unavailable compatibility state only when the trace fields are wholly absent; malformed present weighting trace values are not repaired
- legacy persisted artifacts that predate turnover-diagnostics persistence surface explicit diagnostics-unavailable compatibility state only when the turnover fields are wholly absent; malformed present turnover diagnostics values are not repaired
- partial malformed traces are not repaired; populated-but-invalid traces fail schema validation on load and replay
