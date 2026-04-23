# Construction Run v1

`construction/run` is the first-class persisted backend construction engine for deterministic target-weight artifacts.

V1 is intentionally frozen to `top_n_equal_weight_v1` and consumes ranked candidates as an input artifact rather than re-ranking inside construction.

## Persistence

- `POST /construction/run` persists the canonical artifact before returning it
- persisted artifacts use stable `artifact_id` as the storage key under the construction artifact store
- storage is immutable with write-once semantics; identical rewrites are tolerated, conflicting rewrites are rejected
- `GET /construction/artifacts/{artifact_id}` loads the persisted artifact, validates it on read, and fails closed on corruption
- both feasible and infeasible valid artifacts persist; malformed requests do not persist

## Deterministic policy execution

- normalizes ranked candidates and current portfolio weights into a stable auditable input payload
- executes the internal deterministic selection pipeline for `top_n_equal_weight_v1` using `eligible_only` then `take_top_n`
- captures the ordered `selection_rule_trace` during policy execution and persists that trace on the artifact
- preserves the external route and artifact contract; `policy_id` remains `top_n_equal_weight_v1`
- seeds final target weights as equal weight across the selected names
- enforces only the shipped V1 constraint family: `full_investment`, `long_only`, `eligible_ranked_universe_only`, and `max_position_weight`
- fails closed on infeasible requests; no repair logic or fallback construction is applied

## Replay provenance

- `POST /backtests/portfolio-allocation/construction-artifact-preview` consumes the persisted artifact through an explicit artifact-reference boundary
- replay provenance requires the persisted `selection_rule_trace` from the referenced artifact
- the trace is descriptive provenance only and does not drive replay weights or math

Legacy note:
- legacy persisted artifacts still normalize missing, null, or empty-object `selection_rule_trace` payloads to an empty trace during artifact loading only
- partial malformed traces are not repaired; populated-but-invalid traces fail schema validation on load and replay
