# Construction Run v1

`construction/run` is the first-class persisted backend construction engine for deterministic target-weight artifacts.

V1 supports a narrow persisted policy set and consumes ranked candidates as an input artifact rather than re-ranking inside construction.

## Persistence

- `POST /construction/run` persists the canonical artifact before returning it
- `GET /construction/policies` exposes backend-owned read-only discovery for the shipped persisted policy catalog
- persisted artifacts use stable `artifact_id` as the storage key under the construction artifact store
- storage is immutable with write-once semantics; identical rewrites are tolerated, conflicting rewrites are rejected
- `GET /construction/artifacts/{artifact_id}` loads the persisted artifact, validates it on read, and fails closed on corruption
- both feasible and infeasible valid artifacts persist; malformed requests do not persist

## Deterministic policy execution

- normalizes ranked candidates and current portfolio weights into a stable auditable input payload
- resolves the requested policy definition once, then executes the catalog-owned deterministic selection pipeline for that policy
- each shipped catalog definition carries a backend-owned immutable `policy_definition_id`, and newly persisted artifacts stamp the resolved definition id in `normalized_inputs.policy_definition_id`
- captures the ordered `selection_rule_trace` during policy execution and persists that trace on the artifact
- preserves the requested `policy_id` while also exposing the backend definition id through policy discovery and replay provenance
- separates deterministic selection from policy-specific weighting while keeping both behaviors catalog-owned
- shipped policy discovery is still intentionally narrow and returns only these weighting policies:
  - `top_n_equal_weight_v1`: equal weight across the selected names
  - `top_n_inverse_rank_weight_v1`: weights proportional to `1 / selected_order_rank`, normalized to sum to `1.0`
- execution now resolves shipped policy metadata, selection rule ordering, weighting behavior, and policy-derived failure or cutoff messaging from the backend policy catalog seam rather than scattering policy ids through the run service
- enforces only the shipped V1 constraint family: `full_investment`, `long_only`, `eligible_ranked_universe_only`, `max_position_weight`, and optional `max_turnover_weight`
- evaluates constraints against the actual generated target weights for the chosen policy
- defines turnover as `0.5 * sum(abs(target_weight - current_weight))` over the union of current and target symbols, so initiates and exits both count toward the cap
- canonical artifact identity treats omitted and explicit `null` `hard_constraints.max_turnover_weight` values as equivalent, while preserving `0.0` as a real turnover cap
- applies `hard_constraints.max_turnover_weight` only after target weights are generated; when omitted or explicit `null`, turnover is not constrained and prior behavior is unchanged
- returns an infeasible persisted artifact when the generated target portfolio exceeds `max_turnover_weight`, with an explicit turnover failure reason and a populated `max_turnover_weight` constraint evaluation
- fails closed on unsupported policy resolution before selection, weighting, or artifact persistence; no fallback execution path is applied

## Artifact provenance validation

- persisted construction artifact canonicalization now includes `normalized_inputs.policy_definition_id`, so definition provenance changes deterministically change both `fingerprint` and `artifact_id`
- artifact load validates that the persisted `policy_definition_id` still matches the currently resolved catalog definition for the persisted `policy_id`
- load-path compatibility repairs only the exact legacy case where `normalized_inputs.policy_definition_id` is absent by resolving the persisted `policy_id` during load, while canonical `fingerprint` and `artifact_id` validation still run against the original stored payload before hydration
- write-path behavior stays strict: newly persisted artifacts must stamp `normalized_inputs.policy_definition_id`, and populated null, malformed, or mismatched values still fail closed on load and replay
- replay continues to use persisted baseline and candidate weights; any replay provenance extension remains additive and does not alter replay math

## Replay provenance

- `POST /backtests/portfolio-allocation/construction-artifact-validation` is the canonical producer of the typed `preview_handoff` boundary for downstream open/preview
- `POST /backtests/portfolio-allocation/construction-artifact-preview` consumes that `preview_handoff` as the authoritative validation-to-preview contract
- compatibility with the legacy preview request shape remains additive only; when a payload presents the handoff shape it must validate as a complete supported handoff, and mixed handoff-plus-legacy payloads fail closed
- handoff consumption fails closed on missing or unsupported `handoff_kind` and on any construction artifact id mismatch surfaced by persisted artifact integrity validation
- replay provenance requires the persisted `selection_rule_trace` from the referenced artifact
- the trace is descriptive provenance only and does not drive replay weights or math

Legacy note:
- legacy persisted artifacts still normalize missing, null, or empty-object `selection_rule_trace` payloads to an empty trace during artifact loading only
- legacy persisted artifacts missing `normalized_inputs.policy_definition_id` are hydrated from the persisted `policy_id` during artifact loading only
- partial malformed traces are not repaired; populated-but-invalid traces fail schema validation on load and replay
