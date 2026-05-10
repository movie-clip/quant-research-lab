# Import Admission Fields

Contract source of truth: `services/quant-engine/app/schemas/import_bootstrap.py`.

`ImportAdmissionSummaryV1` is attached to imported bootstrap responses as `admission_summary`. It is read-only evidence about admission checks for an imported broker snapshot. It does not create, deny, or upgrade broker truth.

`ImportAdmissionReviewDispositionV1` is optional desktop-local reviewer metadata for non-pass checks. It is stored outside imported snapshot and admission summary payloads, and it never changes broker truth, admission decision, trust level, workspace creation, imported values, or derived portfolio truth. Desktop runtime loads sanitize this local metadata on read/build boundaries without rewriting IndexedDB, and saves require captured evidence to match the current non-pass check evidence after null/default normalization.

## Summary

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `'import_admission_summary_v1'` | Stable contract version. |
| `decision` | `'admitted' \| 'degraded' \| 'withheld'` | Any exception can only lower the decision. |
| `trust_level` | `'verified' \| 'degraded' \| 'withheld' \| 'unavailable'` | Uses platform trust semantics. |
| `checks` | `ImportAdmissionCheckV1[]` | Exactly the current admission check families. |
| `provenance` | `ImportAdmissionProvenanceV1` | Importer, statement/source names, generation timestamp, tolerance policy. |

## Checks

Each check carries:

| Field | Type | Notes |
|---|---|---|
| `check_id` | string | Current IDs: `residual_cash_comparability`, `symbol_security_identity_consistency`, `parsed_position_market_value_comparability`, `nav_market_value_comparability`. |
| `status` | `'pass' \| 'warn' \| 'fail' \| 'unavailable'` | Missing evidence is unavailable, never pass. |
| `severity` | `'info' \| 'warning' \| 'error'` | Display severity only. |
| `trust_impact` | `'none' \| 'degraded' \| 'withheld' \| 'unavailable'` | Drives summary trust lowering. |
| `message` | string | Human-readable evidence statement. |
| `affected_fields` | string[] | Optional field lineage for the check. |
| `observed`, `comparison` | `{ label, value } \| null` | Optional values used by comparable checks; numeric `value` must be finite, never `NaN`/`Infinity`. |
| `delta` | finite number \| null | Optional observed minus comparison delta; never `NaN`/`Infinity`. |
| `currency` | string \| null | Present only when values are same-currency comparable. |

## Boundary

- Read-only admission summary only.
- Desktop-local review disposition metadata may be stored separately for non-pass checks only.
- Review disposition metadata is anchored to the imported source node that supplied the admission summary. Derived nodes such as drafts and variants may display inherited admission evidence, but they must not receive review metadata directly.
- Runtime load/build boundaries return sanitized clones of local review metadata: valid stale fingerprints are preserved for stale labeling, malformed records are dropped, pass-status evidence is not admitted, and unknown extra fields are stripped by reconstructing the known `ImportAdmissionReviewDispositionV1` shape.
- Read-time sanitization is non-mutating: the desktop must not rewrite IndexedDB just because malformed local metadata was dropped from the returned clone.
- Save-time validation requires the disposition to reference a current non-pass admission check and to carry non-pass captured evidence that matches the current check evidence after canonical null/default normalization.
- Save-time evidence validation does not reject stale or mismatched `snapshot_fingerprint` or `admission_summary_fingerprint`; fingerprints remain local stale-labeling evidence only.
- No backend persistence endpoint for review disposition metadata.
- No blocking workspace creation.
- No trust upgrades, automatic fixes, value rewriting, or reconstruction.
- Missing statement totals, parsed cash evidence, or parsed position market values degrade checks instead of fabricating a pass.
- Non-finite numeric admission inputs (`NaN`, `Infinity`, `-Infinity`) are treated as unavailable/degraded evidence and must not be emitted as numeric observed/comparison/delta evidence.
- NAV/market-value admission includes both statement arithmetic and parsed holdings market-value reconciliation.

## Review Disposition Metadata

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `'import_admission_review_disposition_v1'` | Stable local metadata contract version. |
| `check_id` | string | Must reference a non-pass `ImportAdmissionCheckV1`. |
| `disposition` | `'accepted_known_exception' \| 'needs_source_correction' \| 'deferred'` | Reviewer classification only; not an admission input. |
| `rationale` | non-empty string | Required local reviewer rationale. |
| `reviewed_at` | datetime | Local review timestamp. |
| `reviewer_label` | string | Local reviewer label, not an identity authority. |
| `snapshot_fingerprint` | string | Deterministic fingerprint of the imported snapshot/source metadata reviewed. |
| `admission_summary_fingerprint` | string | Deterministic fingerprint of the admission summary reviewed. |
| `evidence_summary` | object | Captured non-pass check evidence at review time: `status` (`warn`/`fail`/`unavailable` only), `trust_impact`, `message`, `affected_fields`, plus finite `observed`, `comparison`, `delta`, and `currency` when available. |

Review disposition metadata must be shown as stale when either fingerprint differs from the current imported snapshot/source metadata or current admission summary. Stale fingerprints do not block saving when the current non-pass check evidence matches the captured `evidence_summary`.

Desktop storage sanitization rejects malformed local review metadata with non-finite numeric observed/comparison values or delta. This is local metadata hardening only; it does not create a backend persistence endpoint and does not mutate broker truth, admission decisions, or trust levels.

For derived dashboard views, fingerprints and saved dispositions must be computed from the imported-source anchor rather than the derived node snapshot. Saving a disposition updates only local desktop metadata on the imported workspace source or imported snapshot node; it never mutates backend trust/admission state, broker truth, or variant portfolio payloads.
