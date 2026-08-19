# US-8.4 — Strip App.tsx workflow state and workspace storage

**Status:** Done (2026-05-25)

## Story statement

As a developer maintaining the codebase post-Epic-8 pivot, I want all dead state, callbacks, and persistence code for deleted workflow features (Workspace, Backtest, Monitoring, Construction, Optimizer, Ranking, Proposal) removed from `App.tsx` and `portfolioWorkspaceStorage.ts`, so that the codebase reflects only the Dashboard + Exposure surface that is actually shipped.

## Acceptance criteria

1. `App.tsx` contains no `useState`, `useEffect`, callbacks, or imports for Workspace/Backtest/Monitoring/Construction/Optimizer/Ranking/Proposal features.
2. `portfolioWorkspaceStorage.ts` exposes only the functions required by the active `App.tsx` import: `buildImportAdmissionSummaryFingerprint`, `buildImportSnapshotFingerprint`, `buildPersistedImportedSource`, `canonicalizeForFingerprint`, `buildDeterministicImportAdmissionFingerprint`, `clearPortfolioWorkspaceState`, `createDraftFromNode`, `createWorkspaceFromImport`, `getDraft`, `getLastOpenedWorkspaceState`, `getNode`, `getWorkspace`, `getWorkspaceNodes`, `getWorkspaceState`, `resetLocalPortfolioDatabase`, `saveImportAdmissionReviewDisposition`, `saveImportedSnapshotNode`, `setActiveNode`, `setSelectedExposureSnapshot`, `saveDraft`.
3. `portfolioWorkspaceStorage.test.ts` tests only functions that still exist.
4. `App.test.tsx` references no removed storage functions.
5. All vitest tests pass (116/116).
6. TypeScript emits no new errors beyond pre-existing worktree baseline.

## Test plan

- `npx vitest run` from `apps/desktop` — all 116 tests pass.
- `tsc --noEmit` from `apps/desktop` — no new errors beyond pre-existing baseline (missing react/vitest types in worktree context, pre-existing implicit any parameters).

## Tickets

- [x] Remove dead `useState` declarations from `App.tsx` (construction/optimizer/monitoring/proposal/candidate/replacement/replay state)
- [x] Remove dead callback functions from `App.tsx` (`handlePreviewExposure`, `handleDraftSnapshotChange`, `handleDiscardDraft`, `handleSaveVariant`, `handleOpenNode`, `loadWorkspaceProposalArtifacts`, monitoring/proposal callbacks)
- [x] Remove dead imports from `App.tsx`
- [x] Rewrite `portfolioWorkspaceStorage.ts` — remove 2600+ lines of proposal/construction/optimizer/monitoring CRUD, keep import-admission, fingerprint, workspace, draft, and exposure-snapshot primitives
- [x] Rewrite `portfolioWorkspaceStorage.test.ts` — remove tests for deleted functions, keep tests for retained functions (727 lines from 5537)
- [x] Fix `App.test.tsx` — remove `beforeEach` spy on deleted `getWorkspaceProposalArtifacts`
- [x] Update `docs/product/stories/README.md` — mark US-8.4 Done
- [x] Update `docs/product/epic-roadmap.md` — advance current slice to US-8.7

## Status

**Done** — 2026-05-25

## Line counts (before → after)

| File | Before | After |
|---|---|---|
| `App.tsx` | 3138 | 901 |
| `portfolioWorkspaceStorage.ts` | 3293 | 707 |
| `portfolioWorkspaceStorage.test.ts` | 5537 | 727 |
