# quant-contract-sync

## Purpose

Protect contract integrity across backend schemas, route payloads, desktop types, docs, and regression tests.

Use this skill whenever work changes API request/response shapes, persisted artifact payloads, run metadata, diagnostics fields, replay payloads, or any backend field that desktop or docs rely on.

## Trigger Paths

Apply this skill if any changed file matches one or more of:

- `services/quant-engine/app/schemas/*.py`
- `services/quant-engine/app/api/routes/*.py`
- `services/quant-engine/app/services/*artifact*.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`
- `services/quant-engine/app/services/diagnostics_engine.py`
- `apps/desktop/src/features/portfolio/types.ts`
- `apps/desktop/src/features/portfolio/workspaceTypes.ts`
- `apps/desktop/src/app/App.tsx`
- `apps/desktop/src/app/portfolioWorkspaceStorage.ts`
- `docs/contracts/*.md`
- `docs/product/current-product-state.md`
- `docs/product/roadmap.md`
- `docs/product/technical-roadmap.md`
- `docs/architecture/system-architecture.md`
- `services/quant-engine/docs/*.md`

Apply it proactively for related test updates in:

- `services/quant-engine/app/tests/test_routes.py`
- `services/quant-engine/app/tests/test_analytics.py`
- `services/quant-engine/app/tests/test_portfolio_allocation_backtests.py`
- `services/quant-engine/app/tests/test_construction_run_service.py`
- `services/quant-engine/app/tests/test_strategy_lab.py`
- `services/quant-engine/app/tests/test_optimizer_service.py`
- `apps/desktop/src/app/*.test.ts*`
- `apps/desktop/src/features/**/*.test.ts*`

## Non-Negotiable Rules

### 1. Backend Schema Is The Contract Root

- Treat backend schemas and route serialization as the source of truth.
- Desktop types, docs, fixtures, and tests must follow shipped backend behavior.
- Do not leave frontend or docs on an older field shape after backend changes.

### 2. Additive First, Removal Later

- Prefer additive contract evolution before removing fields.
- If a field is deprecated, mark it clearly in code/tests/docs and keep a follow-up to remove it later.
- Do not silently repurpose an old field with new meaning.

### 3. One Meaning Per Field

- A field should have one precise semantic role.
- Do not overload provenance fields with execution settings, or status fields with unlock policy.
- If two concerns differ, use two fields.

### 4. Route, Type, And Doc Updates Travel Together

- If a route contract changes, update in the same pass:
  - backend route/service tests
  - desktop types and callers
  - contract docs
  - current-state / roadmap wording if shipped state changed

### 5. Preserve Truth Labels

- If a payload is hypothetical, preview-only, review-only, imported, persisted, or withheld, keep those semantics explicit.
- Never make the docs or desktop wording sound more production-truthful than the payload actually is.

### 6. Fail Closed On Ambiguous Contract States

- Missing required fields, malformed payloads, unsupported handoff kinds, mismatched ids, or partial invalid states should fail clearly.
- Do not silently coerce malformed present values just to keep the UI working.

## Preferred Workflow

1. Identify the contract surface changed:
   - request model
   - response model
   - persisted artifact shape
   - desktop review/storage shape
   - docs/roadmap/current-state wording
2. Check the backend schema and route behavior first.
3. Update or add backend tests for the changed contract.
4. Update desktop types and any call sites.
5. Update docs/contracts/current-state if the shipped behavior changed.
6. Verify there is no stale deprecated wording or mismatched field inventory left behind.

## Contract Sync Checklist

Before finishing, check all that apply:

- Backend schema matches route behavior.
- Route tests cover the changed contract shape.
- Desktop types match shipped backend payloads.
- Desktop callers use the new contract path, not stale reconstructed fields.
- Contract docs list the current fields accurately.
- Current-state / roadmap text reflects shipped vs future work correctly.
- Deprecated fields are marked and intentionally preserved or removed.
- Fixtures and cached-state normalization still match the contract.

## Common Failure Modes To Catch

- Backend field added but missing in desktop types.
- Docs still describing a removed or renamed field.
- Route accepts a new request shape but desktop still sends the old one.
- Deprecated fields kept alive without explicit docs/tests.
- Partial unlock / withheld semantics documented incorrectly.
- Roadmap still listing shipped work as future work.
- Current-state overclaiming a broader feature than what is actually shipped.

## Validation Commands

Run the smallest sufficient set, but default to the affected subset of:

```bash
python -m pytest app/tests/test_routes.py app/tests/test_analytics.py app/tests/test_portfolio_allocation_backtests.py app/tests/test_construction_run_service.py app/tests/test_strategy_lab.py app/tests/test_optimizer_service.py
```

If desktop types or consumers changed, also run:

```bash
npm test -- --run src/app/App.test.tsx src/app/portfolioWorkspaceStorage.test.ts src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx src/features/backtest/PortfolioAllocationBacktestPanel.test.tsx
```

## Expected Final Report Format

When closing work under this skill, explicitly state:

- which contract surface changed
- which backend schema/route tests were updated
- which desktop types/callers were updated
- which docs were updated
- whether any deprecated fields remain and why

## Manual Use In Current Environment

Because runtime skill loading is not yet wired up for this repo, invoke this skill manually in either of these ways:

1. Ask OpenCode: `Follow .opencode/skills/quant-contract-sync.md for this change.`
2. Paste the relevant sections into the session prompt before starting contract work.

## Future Automation Hook

When repo-level skill loading becomes available, register this file under the skill name:

- `quant-contract-sync`
