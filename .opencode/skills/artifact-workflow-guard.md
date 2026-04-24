# artifact-workflow-guard

## Purpose

Protect persisted artifact workflows from contract drift, truth-mixing, and accidental weakening of validation, preview, replay, and review boundaries.

Use this skill whenever work touches ranking artifacts, construction artifacts, optimizer handoffs, artifact-backed review flows, replay preflight/open paths, or docs/contracts that describe those flows.

## Trigger Paths

Apply this skill if any changed file matches one or more of:

- `services/quant-engine/app/services/*artifact*.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`
- `services/quant-engine/app/services/optimizer_*service.py`
- `services/quant-engine/app/api/routes/backtests.py`
- `services/quant-engine/app/api/routes/construction.py`
- `services/quant-engine/app/api/routes/optimizer.py`
- `services/quant-engine/app/api/routes/strategy_lab.py`
- `services/quant-engine/app/schemas/backtest_engine.py`
- `services/quant-engine/app/schemas/construction.py`
- `services/quant-engine/app/schemas/optimizer.py`
- `services/quant-engine/app/schemas/research.py`
- `apps/desktop/src/app/App.tsx`
- `apps/desktop/src/app/portfolioWorkspaceStorage.ts`
- `apps/desktop/src/features/backtest/*.tsx`
- `apps/desktop/src/features/portfolio/workspaceTypes.ts`
- `apps/desktop/src/features/portfolio/types.ts`

Apply it proactively for related tests and contract/docs updates in:

- `services/quant-engine/app/tests/test_routes.py`
- `services/quant-engine/app/tests/test_portfolio_allocation_backtests.py`
- `services/quant-engine/app/tests/test_construction_run_service.py`
- `services/quant-engine/app/tests/test_strategy_lab.py`
- `services/quant-engine/app/tests/test_optimizer_service.py`
- `apps/desktop/src/app/App.test.tsx`
- `apps/desktop/src/app/portfolioWorkspaceStorage.test.ts`
- `apps/desktop/src/features/backtest/*.test.tsx`
- `docs/contracts/*.md`
- `docs/product/current-product-state.md`
- `services/quant-engine/docs/*.md`

## Non-Negotiable Rules

### 1. Persisted Artifact Is Authoritative

- After persistence, the artifact is the source of truth for downstream consumption.
- Do not rebuild canonical downstream input from ad hoc client state if the artifact or typed handoff already carries it.
- Prefer explicit artifact ids or typed handoff objects over loose field bundles.

### 2. Validation, Preview, And Open Must Stay Distinct

- Validation/preflight proves eligibility, integrity, and input correctness.
- Preview/open produces replay or review payloads.
- Do not let validation silently become preview unless the contract explicitly says it returns an open payload.
- If validation emits a handoff, preview must consume that handoff directly.

### 3. Truth Separation Must Remain Explicit

- Imported/current portfolio truth must stay separate from hypothetical candidate or artifact-backed review truth.
- Do not materialize fake holdings, fake market values, or fake imported snapshot semantics just to fit an existing UI shape.
- If a review is artifact-only, label it as review/artifact basis, not imported basis.

### 4. Legacy Compatibility Belongs Only At Load Boundaries

- New writes must be strict and canonical.
- Legacy compatibility is allowed only when reading old persisted payloads.
- Load-time hydration may fill missing legacy fields only for documented cases.
- Do not auto-repair present malformed or conflicting values.

### 5. Fail Closed On Artifact Problems

- Missing artifact -> fail.
- Invalid JSON/schema/integrity mismatch -> fail.
- Unsupported handoff kind/version -> fail.
- Infeasible or unreplayable artifact -> fail.
- Mismatched artifact identity between handoff and open payload -> fail.
- Never silently fall back to weaker semantics.

### 6. Contract Changes Must Be Backed By Tests And Docs

- If a route/request/response shape changes, update the matching backend tests, desktop callers, and contract docs in the same pass.
- Prefer additive evolution first; remove deprecated fields only after callers are migrated and tests prove it.

## Preferred Workflow

1. Identify the authoritative artifact or handoff object.
2. Identify the boundary under change:
   - persistence
   - retrieval
   - validation/preflight
   - preview/open
   - desktop review/open flow
3. Confirm whether the change affects:
   - artifact identity/fingerprint
   - legacy load compatibility
   - truth-separation semantics
   - desktop cached review restore
   - route/docs/test alignment
4. Keep validation/preflight and preview/open responsibilities separate unless the contract explicitly combines them.
5. Update route tests, service tests, desktop tests, and docs in the same pass.

## Artifact Workflow Checklist

Before finishing, check all that apply:

- Persisted artifact or typed handoff is the authoritative downstream input.
- Validation and preview/open responsibilities are clear and non-overlapping.
- Client is not reconstructing canonical preview input from loose fields.
- Imported/current truth is not mixed with hypothetical artifact review state.
- Legacy compatibility is load-only and documented.
- Missing/malformed/infeasible/mismatched artifacts fail closed.
- Desktop cached review restore remains backward-compatible if needed.
- Contract/docs/tests all reflect the same boundary.

## Common Failure Modes To Catch

- Validation route secretly doing full preview/open work.
- Preview route accepting both handoff and loose fields with no precedence rule.
- Desktop rebuilding preview input from `artifact_id` plus defaults instead of using the handoff.
- Artifact review persisting synthetic imported snapshot data.
- Legacy hydration mutating persisted data or widening to unsupported malformed cases.
- New route shape shipped without updating desktop types and route tests.
- Deprecated compatibility fields left behind with no explicit follow-up.

## Validation Commands

Run the smallest sufficient set, but default to the affected subset of:

```bash
python -m pytest app/tests/test_routes.py app/tests/test_portfolio_allocation_backtests.py app/tests/test_construction_run_service.py app/tests/test_strategy_lab.py app/tests/test_optimizer_service.py
```

If desktop artifact-review/open flow changed, also run:

```bash
npm test -- --run src/app/App.test.tsx src/app/portfolioWorkspaceStorage.test.ts src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx src/features/backtest/PortfolioAllocationBacktestPanel.test.tsx
```

## Expected Final Report Format

When closing work under this skill, explicitly state:

- what the authoritative artifact/handoff boundary is after the change
- whether validation/preflight and preview/open responsibilities changed
- whether legacy compatibility was added, preserved, or intentionally rejected
- which fail-closed cases were covered
- which backend/desktop validation commands passed

## Manual Use In Current Environment

Because runtime skill loading is not yet wired up for this repo, invoke this skill manually in either of these ways:

1. Ask OpenCode: `Follow .opencode/skills/artifact-workflow-guard.md for this change.`
2. Paste the relevant sections into the session prompt before starting artifact workflow work.

## Future Automation Hook

When repo-level skill loading becomes available, register this file under the skill name:

- `artifact-workflow-guard`
