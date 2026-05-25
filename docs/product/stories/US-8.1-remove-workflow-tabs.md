# US-8.1: Remove workflow tabs from navigation

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** [`epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want to open the app and see only Dashboard and Exposure in the nav, so that the product surface matches what I actually use.

## Context

The app currently renders eight navigation tabs: Dashboard, Workspace, Exposure, Diagnostics, Backtest, Strategy Lab, ETF Ranking, Generic Ranking. Only Dashboard and Exposure are useful to the researcher. This story removes the six unused tabs from the nav bar by changing the `appTabs` array in App.tsx. All feature-directory code is left in place — this is a nav-only change. Subsequent Epic 8 stories delete the now-unreachable code.

## Acceptance criteria

- [x] AC1 — The app renders exactly two nav tabs: Dashboard and Exposure, in that order.
- [x] AC2 — No tab-navigation button for Workspace, Backtest, Strategy Lab, ETF Ranking, Generic Ranking, or Diagnostics exists in the DOM.
- [x] AC3 — `npx tsc --noEmit` is clean (feature code not yet deleted; all type references still compile).
- [x] AC4 — All frontend tests pass (`npx vitest run` green).

## Test plan

Frontend (vitest):
- `App.test.tsx` — `renders exactly Dashboard and Exposure tabs` asserts that the navigation contains exactly `['Dashboard', 'Exposure']` and no other buttons.

Regression / guardrail:
- Full vitest suite (421 tests, 22 files) must remain green. Tests for deleted-tab features that navigated via `getByRole('button', { name: 'Workspace' })` are removed in this story; tests for Dashboard and Exposure functionality are retained.

## Tickets

- [x] T-8.1.1 — Change `appTabs` in `apps/desktop/src/app/App.tsx` to contain only `[{ id: 'dashboard', label: 'Dashboard' }, { id: 'exposure', label: 'Exposure' }]`. Update `App.test.tsx`: delete all `it(...)` blocks that test removed-tab features or navigate via the Workspace button; fix the tab-order regression test to assert `['Dashboard', 'Exposure']`; clean up unused imports and helpers.

## Out of scope

- Deleting feature-directory code (`features/backtest/`, `features/strategy-lab/`, `features/generic-ranking/`, `features/optimizer/`) — that is US-8.2 and US-8.3.
- Removing App.tsx state and callbacks for removed features — that is US-8.4.
- Backend changes — those are US-8.5 and US-8.6.
- Changing the `AppTab` union type — it still includes `'workspace' | 'backtest' | ...` so that all `setTab('workspace')` call sites continue to compile until US-8.4.

## Notes / decisions

- `appTabs` is the single source of truth for which nav buttons are rendered. Changing it does not affect the conditional rendering blocks (`tab === 'workspace'` etc.) in App.tsx — those compile and are simply unreachable until US-8.4 removes them.
- About 240 of the original 259 App.test.tsx tests were deleted: they all depended on navigating to `getByRole('button', { name: 'Workspace' })` or tested features that are unreachable from the new nav. The 19 retained tests cover Dashboard import, Dashboard values, Exposure snapshot selection, and the tab-order assertion.
