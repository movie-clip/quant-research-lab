# US-8.7: Prune portfolio feature directory

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** [`epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a **developer**, I want `features/portfolio/` to contain only components that Dashboard and Exposure actually render, so the directory is navigable without knowledge of removed features.

## Acceptance criteria

- [x] AC1 — `features/portfolio/` contains no files consumed exclusively by the removed Diagnostics/Workspace/Candidate workflow.
- [x] AC2 — `AppTab` type is `'dashboard' | 'exposure'` only; the dead `tab === 'diagnostics'` JSX block is removed from App.tsx.
- [x] AC3 — `npx tsc --noEmit` is clean.
- [x] AC4 — `npx vitest run` is green.

## Tickets

- [x] T-8.7.1 — Delete dead portfolio components and clean App.tsx.
