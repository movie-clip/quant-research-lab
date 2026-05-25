# US-8.3: Strip ranking and optimizer frontend

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** docs/product/prd/epic-8-reset-to-analysis-core.md
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a developer, I want the `features/strategy-lab/`, `features/generic-ranking/`, and `features/optimizer/` directories gone so the codebase no longer carries components and tests for ETF ranking, generic ranking, and optimizer tabs that are not in the product.

## Acceptance criteria

- [x] `features/strategy-lab/` directory does not exist
- [x] `features/generic-ranking/` directory does not exist
- [x] `features/optimizer/` directory does not exist (was already empty)
- [x] `npx tsc --noEmit` is clean (no new errors from our code changes)
- [x] `npx vitest run` passes
- [x] `App.tsx` has no imports or JSX render blocks for `GenericRankingView`, `EtfRankingPanel`, or `StrategyLabPanel`

## Tickets

- [x] T-8.3.1 — Delete `features/strategy-lab/`, `features/generic-ranking/`, and `features/optimizer/` directories
- [x] T-8.3.2 — Remove `GenericRankingView` lazy import and `{tab === 'generic_ranking' ? ...}` JSX block from `App.tsx`
- [x] T-8.3.3 — Remove `WorkspaceOwnedResearchSessions` type, `StrategyBacktestPanelState`, `StrategyLabPanelState`, `EtfRankingPanelState` imports and related state from `App.tsx`
- [x] T-8.3.4 — Trim `AppTab` union to `'dashboard' | 'exposure' | 'diagnostics'`

## Out of scope

Removing the `workspaceResearchSessionState.ts` file from `features/portfolio/` (it still exists but is now unused by App.tsx) — that is US-8.4.
