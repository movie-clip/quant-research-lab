# Import Admission Fields

Contract source of truth: `services/quant-engine/app/schemas/import_bootstrap.py`.

`ImportAdmissionSummaryV1` is attached to imported bootstrap responses as `admission_summary`. It is read-only evidence about admission checks for an imported broker snapshot. It does not create, deny, or upgrade broker truth.

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
- No blocking workspace creation.
- No trust upgrades, automatic fixes, value rewriting, or reconstruction.
- Missing statement totals, parsed cash evidence, or parsed position market values degrade checks instead of fabricating a pass.
- Non-finite numeric admission inputs (`NaN`, `Infinity`, `-Infinity`) are treated as unavailable/degraded evidence and must not be emitted as numeric observed/comparison/delta evidence.
- NAV/market-value admission includes both statement arithmetic and parsed holdings market-value reconciliation.

## Removed: Review Disposition Metadata (US-23.9)

The `ImportAdmissionReviewDispositionV1` subsystem (desktop-local reviewer
disposition metadata: accept-known-exception / needs-source-correction /
deferred) was built but never wired to any UI producer or consumer. US-22.2
closed the disposition *workflow* as not-needed, and US-23.9 removed the dead
plumbing across the seam — the BE schemas + enum (`import_bootstrap.py`), the TS
types (`types.ts`), the `admissionReviewDispositions` workspace field
(`workspaceTypes.ts`), and the desktop save/sanitize/fingerprint subsystem
(`portfolioWorkspaceStorage.ts`).

Persisted-state safety: a workspace saved before US-23.9 may still carry an
`admissionReviewDispositions` blob in IndexedDB. The read path simply does not
carry the field forward — it is dropped on load, never crashes, and storage is
not rewritten. (Regression: `portfolioWorkspaceStorage.test.ts` — "drops a
legacy admissionReviewDispositions blob on read without rewriting storage".)

If reviewer-acknowledgement value ever returns, a lightweight "dismiss" is the
intended shape — not this schema.
