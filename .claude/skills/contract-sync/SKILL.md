---
name: contract-sync
description: Use after modifying any Pydantic schema in services/quant-engine/app/schemas/ to keep desktop TypeScript types and contract docs aligned. Triggers on schema field add/remove/rename, schema type changes, or when auditing whether the three layers (Pydantic ↔ TS ↔ docs) are in sync.
---

# Contract Sync

Three representations of every API contract must stay aligned:

1. **Pydantic schemas** — `services/quant-engine/app/schemas/` (source of truth)
2. **Desktop TypeScript types** — `apps/desktop/src/` (must mirror schemas)
3. **Contract docs** — `docs/contracts/` (field inventory, must reflect both)

## Sync process

### Step 1 — Identify what changed

```bash
git diff --name-only HEAD~1 HEAD -- services/quant-engine/app/schemas/
```

Read each changed schema file completely before touching downstream.

### Step 2 — Audit desktop types

For each changed Pydantic model, find the matching TypeScript type:

```bash
# Find by model name (e.g. PortfolioSummary)
grep -r "PortfolioSummary" apps/desktop/src/ --include="*.ts" --include="*.tsx"
```

Compare field by field:
- Field added in schema but missing in TS → add it
- Field removed from schema but still in TS → remove it
- Field renamed → update name + all usages
- Type changed (e.g. `Optional[str]` → `Optional[float]`) → update TS

### Step 3 — Update contract docs

The 7 inventory files in `docs/contracts/` map every field to source/type/UI usage. Update the relevant doc to reflect current state.

### Step 4 — Verify no stale references

```bash
grep -r "old_field_name" apps/desktop/src/ --include="*.ts" --include="*.tsx"
grep -r "old_field_name" services/quant-engine/app/ --include="*.py"
```

## Pydantic → TypeScript type mapping

| Pydantic | TypeScript |
|----------|-----------|
| `str` | `string` |
| `int` | `number` |
| `float` | `number` |
| `bool` | `boolean` |
| `Optional[X]` | `X \| null` |
| `List[X]` | `X[]` |
| `Dict[str, X]` | `Record<string, X>` |
| `Literal["a", "b"]` | `"a" \| "b"` |
| `Enum` | union type or string enum |
| `BaseModel` (nested) | `interface` |
| `datetime` | `string` (ISO) |

## Trust-level fields

The backend uses `Literal["verified", "degraded", "withheld", "unavailable"]` for trust state. Desktop types must mirror exactly — never widen to plain `string`.

For confidence: `Literal["full", "partial", "degraded"]` (newer schemas) or `Literal["high", "medium", "low"]` (legacy ETF ranking). Don't conflate them; check the source schema.

## Guardrails

- **Schema is always source of truth** — never change a schema to match a TS type
- **Don't add new fields during a sync pass** — that's a backend feature task; sync only mirrors
- **If a removal would break the UI**, flag it before proceeding rather than silently dropping
- **Confirm zero stale refs** with grep before reporting done

## Non-negotiable rules

### 1. Backend schema is the contract root
Backend schemas and route serialization are the source of truth. Desktop types, docs, fixtures, and tests must follow shipped backend behavior. Don't leave frontend or docs on an older field shape after backend changes.

### 2. Additive first, removal later
Prefer additive contract evolution before removing fields. If a field is deprecated, mark it clearly in code/tests/docs and keep a follow-up to remove it later. Don't silently repurpose an old field with new meaning.

### 3. One meaning per field
A field has one precise semantic role. Don't overload provenance fields with execution settings, or status fields with unlock policy. If two concerns differ, use two fields.

### 4. Route, type, and doc updates travel together
If a contract changes, in the same pass update: backend route/service tests, desktop types and callers, contract docs, current-state / roadmap wording if shipped state changed.

### 4a. Shipped-state docs must move together
Keep `docs/product/current-product-state.md`, `docs/product/roadmap.md`, `docs/product/technical-roadmap.md`, and `docs/product/epic-roadmap.md` aligned. Don't leave one doc describing a surface as future work while another describes it as shipped.

### 5. Preserve truth labels
If a payload is hypothetical, preview-only, review-only, imported, persisted, or withheld, keep those semantics explicit. Never make docs or desktop wording sound more production-truthful than the payload actually is.

### 6. Fail closed on ambiguous contract states
Missing required fields, malformed payloads, unsupported handoff kinds, mismatched ids, or partial invalid states should fail clearly. Don't silently coerce malformed present values just to keep the UI working.

## Common failure modes

- Backend field added but missing in desktop types
- Docs still describing a removed or renamed field
- Route accepts a new request shape but desktop still sends the old one
- Deprecated fields kept alive without explicit docs/tests
- Partial unlock / withheld semantics documented incorrectly
- Roadmap still listing shipped work as future work
- Current-state overclaiming a broader feature than what is actually shipped

## Output template

```
Synced: schemas/<name>.py → apps/desktop/src/.../<name>.ts
  - Added: `field_name: type`
  - Removed: `legacy_field`
  - Renamed: old_name → new_name

Updated: docs/contracts/<area>.md
  - Added field_name row
  - Removed legacy_field row

Stale ref check: clean
```
