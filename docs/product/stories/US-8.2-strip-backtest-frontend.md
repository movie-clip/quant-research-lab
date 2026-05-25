# US-8.2: Strip Workspace and Monitoring frontend

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** docs/product/prd/epic-8-reset-to-analysis-core.md
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a developer, I want the `features/backtest/` directory gone so the codebase no longer carries ~35 components, hooks, and tests for a workflow (Workspace + Monitoring) that is no longer in the product.

## Acceptance criteria

- [x] `features/backtest/` directory does not exist
- [x] `npx tsc --noEmit` is clean (no new errors from our code changes)
- [x] `npx vitest run` passes
- [x] `App.tsx` has no imports from `features/backtest/`
- [x] All lazy-imports and JSX render blocks for `BacktestWorkspacePanel` removed from `App.tsx`

## Tickets

- [x] T-8.2.1 — Delete `features/backtest/` directory
- [x] T-8.2.2 — Remove `BacktestWorkspacePanel` lazy import and `{tab === 'workspace' ? ...}` JSX block from `App.tsx`
- [x] T-8.2.3 — Remove `WorkspaceResearchTool` type import and all state/callbacks that only served the deleted panel (`workspaceResearchIntent`, `workspaceShellActivationKey`, `workspaceOwnedResearchSessions`, `allocationBacktestRun`, `ensureWorkspaceOwnedResearchSession`, `updateWorkspaceOwnedResearchSession`, `routeIntoWorkspace`)
- [x] T-8.2.4 — Fix `workspaceResearchSessionState.ts` which imported from `features/backtest/rankingConstructionMaxPositionWeight`

## Out of scope

Deep removal of workspace-adjacent state variables that have tentacles into optimizer/construction review flows — that is US-8.4.
