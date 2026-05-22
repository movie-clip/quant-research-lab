# US-5.1: Fix app navigation order

**Epic:** 5 — Usable Core Flow
**PRD:** [`epic-5-usable-core-flow.md`](../prd/epic-5-usable-core-flow.md)
**Status:** Done
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want the **app tabs to follow the natural
workflow order**, so that **after reviewing my Dashboard I immediately see
Workspace as the next step — not Exposure and Diagnostics**.

## Context

The current tab order is: Dashboard → Exposure → Diagnostics → Workspace →
Backtest → Strategy Lab → ETF Ranking → Generic Ranking. This buries the
primary action (Workspace — the improvement workflow) behind two supporting
analysis tabs. A researcher who clicks "Open Detailed Review" from the
Dashboard and lands in Workspace then has to work backwards against the tab
layout. The fix is a single reorder: move Workspace to position 2, immediately
after Dashboard. The supporting tools (Exposure, Diagnostics) remain available
but are positioned as secondary detail tabs, not primary flow steps.

No backend, schema, or methodology change. This is a single-line reorder in
`apps/desktop/src/app/App.tsx`.

## Acceptance criteria

- [x] AC1 — The tab bar renders in this order: Dashboard, Workspace, Exposure,
  Diagnostics, Backtest, Strategy Lab, ETF Ranking, Generic Ranking.
- [x] AC2 — All eight tabs are still present — none are removed.
- [x] AC3 — Clicking each tab still navigates to the correct panel (no
  functionality regressed).
- [x] AC4 — The default active tab on app launch is still Dashboard.

## Test plan

Backend (pytest):
- None — pure frontend change.

Frontend (vitest):
- `App.test.tsx` — assert that the rendered tab list is
  `['Dashboard', 'Workspace', 'Exposure', 'Diagnostics', 'Backtest',
  'Strategy Lab', 'ETF Ranking', 'Generic Ranking']` in that order (query
  all elements with `role="tab"` and check their text content sequence).

Regression / guardrail:
- All existing `App.test.tsx` tab-navigation tests must stay green — no panel
  should stop rendering when its tab is clicked.

## Tickets

- [x] T-5.1.1 — Frontend: reorder the `appTabs` array in
  `apps/desktop/src/app/App.tsx` (move `workspace` from index 3 to index 1);
  add a tab-order assertion to `App.test.tsx`.

## Out of scope

- Renaming any tab label (separate story if wanted).
- Hiding or conditionally showing tabs based on workflow state.
- Reordering panels within Workspace itself.
- Any change to Exposure or Diagnostics content.

## Notes / decisions

- The `appTabs` array at line 67 of `App.tsx` is the single source of truth
  for tab order — the reorder is one array entry moved, nothing else.
- No financial methodology is involved; no docs/contracts update needed.
- The `workspaceOwnedResearchTabs` constant at line 78 (`['backtest',
  'strategy_lab', 'etf_ranking']`) is independent of tab display order and
  must not be changed.
