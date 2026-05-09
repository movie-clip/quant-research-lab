---
name: artifact-workflow
description: Use when creating, loading, or extending persisted artifact storage (rankings, constructions, optimizer handoffs, monitor observations). Triggers on work involving data/artifacts/ directories, content-addressed IDs, fingerprint schemes, write-once persistence, or fail-closed validation.
---

# Persisted Artifact Workflow

The platform persists deterministic decision-support artifacts as auditable records. They live in `data/artifacts/` and are committed to git.

## Artifact kinds shipped today

| Kind | Directory | Schema version |
|---|---|---|
| `etf_ranking` | `data/artifacts/etf-ranking-artifacts/` | `etf_ranking_artifact_v1` |
| `intent_bound_etf_replacement_ranking` | `data/artifacts/etf-replacement-ranking-artifacts/` | `intent_bound_etf_replacement_ranking_artifact_v1` |
| `generic_ranking` | `data/artifacts/generic-ranking-artifacts/` | `generic_ranking_artifact_v1` |
| `cross_sectional_research_run` | `data/artifacts/cross-sectional-research-artifacts/` | `cross_sectional_research_artifact_v1` |
| Construction artifacts | `data/artifacts/construction-artifacts/` | per-policy schemas |
| Optimizer handoffs | `data/artifacts/optimizer-handoffs/` | manifest + content split |

## Required properties of every artifact

1. **Stable identity** — `artifact_id` is content-addressed: `<prefix>_<sha256(canonical_json_without_artifact_id)[:16]>`
2. **Immutable payload** — once written, never modified; same input produces same artifact_id
3. **Explicit upstream references** — full lineage to inputs (selection rules, source artifact IDs, ranking seeds)
4. **Methodology and policy IDs** — versioned, digestible (e.g. `score_config_digest`)
5. **Trust / return-basis attestation** — required where financially meaningful
6. **Fail-closed loading** — invalid/missing/corrupted artifact raises, never silently degrades

## Persistence pattern (canonical)

Model new artifact stores after `etf_ranking_artifact_service.py`:

```python
def build_stable_<kind>_artifact(response: <Kind>Response) -> <Kind>Artifact:
    pending = <Kind>Artifact(**response.model_dump(), artifact_id=PREFIX + "pending")
    canonical = json.dumps(
        {k: v for k, v in pending.model_dump().items() if k != "artifact_id"},
        sort_keys=True, separators=(",", ":"), default=str,
    )
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return pending.model_copy(update={"artifact_id": PREFIX + fingerprint})

class <Kind>ArtifactStore:
    def persist(self, artifact: <Kind>Artifact) -> None:
        self._validate_integrity(artifact)
        path = self.base_dir / f"{artifact.artifact_id}.json"
        canonical = json.dumps(artifact.model_dump(), sort_keys=True, separators=(",", ":"), default=str)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != canonical:
                raise <Kind>PersistenceError("artifact_id collision with different content")
            return  # idempotent
        path.write_text(canonical, encoding="utf-8")
        self._append_recent_index(artifact)
```

## Recent index (JSONL) pattern

```
data/artifacts/<kind>/recent.jsonl
```

- Append-only, one row per artifact
- Each row is a flat summary (no nested objects)
- Read in reverse, deduplicate by `artifact_id` (last write wins on duplicates)
- Never rely on it for primary storage — always rebuild possible by globbing `*.json`

## Required error class hierarchy

```python
class <Kind>PersistenceError(Exception): ...
class <Kind>ReadError(<Kind>PersistenceError): ...
class <Kind>MissingFileError(<Kind>ReadError): ...
class <Kind>InvalidJsonError(<Kind>ReadError): ...
class <Kind>NonObjectPayloadError(<Kind>ReadError): ...
class <Kind>SchemaValidationError(<Kind>ReadError): ...
class <Kind>IntegrityValidationError(<Kind>ReadError): ...
```

Routes that load artifacts must catch these and translate to HTTP 404 / 422 explicitly.

## Validation rules (fail-closed)

On load:
1. File exists → else `MissingFileError`
2. JSON parses → else `InvalidJsonError`
3. Top-level is object → else `NonObjectPayloadError`
4. `schema_version` field matches expected → else `SchemaValidationError`
5. Pydantic model validates → else `SchemaValidationError`
6. Recompute artifact_id from content; equals stored → else `IntegrityValidationError`
7. `artifact_id` starts with expected prefix → else `IntegrityValidationError`

## Replay vs preview boundary

- **Preview** = compute fresh, may persist
- **Replay** = load persisted artifact, re-derive analytics from its frozen inputs (never re-resolve from live data)
- Replay outputs must echo persisted lineage explicitly; never blend live data into replay

## Cross-kind discovery

`RankingArtifactCatalogService` aggregates across artifact kinds. To add a new kind:

1. Register in `RANKING_ARTIFACT_KIND_REGISTRY` with supported schema versions and discovery filters
2. Add `_list_all_<kind>_rows()` and `_list_recent_<kind>_rows()` methods
3. Wire dispatch in `list_catalog()` and `list_recent()`
4. Extend `_matches_filters()` and `_row_confidence()` for the new kind
5. Update route handler `except` clauses to catch new kind's error classes

## Truth class boundaries

Never mix in a single response or computation:

- Broker truth (imported positions / ledger)
- Snapshot analytics (point-in-time computed)
- Synthetic history (reconstructed)
- Persisted artifacts (saved decision outputs)
- Optimizer previews (hypothetical, never executed)
- Replay (re-running persisted workflows)

If a route produces multiple truth classes, label each section explicitly with provenance.
