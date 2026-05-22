# US-5.3: Fix "Review in Construction" end-to-end

**Epic:** 5 — Usable Core Flow
**PRD:** [`epic-5-usable-core-flow.md`](../prd/epic-5-usable-core-flow.md)
**Status:** Done
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want the **"Review In Construction" flow to show
clear, plain-English labels and feedback at every step**, so that **I know where
I am before I click, what went wrong if it fails, and what I'm looking at after
it succeeds**.

## Context

After US-5.1 (tab order) and US-5.2 (column labels), the remaining friction in
the "Review In Construction" path is not in the code logic — tests confirm the
end-to-end handoff is wired correctly — but in the copy and visual treatment at
three specific moments: (1) the Candidate Idea browser section headings still
use internal system names, (2) the success state banner inside
`PortfolioImprovementWorkspaceShell.tsx` says "Artifact Review Mode" with
opaque technical helper text, and (3) if the App-level construction validation
or preview phase fails, the error renders as an unstyled paragraph in
`App.tsx` that is easy to miss. All three are pure frontend copy and styling
changes — no backend, schema, or methodology change.

## Acceptance criteria

- [x] AC1 — The three Candidate Idea browser panel-labels read: "ETF Ranking
  Runs" (was "Persisted ETF Ranking Construction"), "Generic Ranking Runs" (was
  "Persisted Generic Ranking Construction"), "Replacement Ranking Runs" (was
  "Persisted Replacement Reviews").
- [x] AC2 — After a successful "Review In Construction" handoff, the banner that
  marks artifact review mode (construction artifact case only, not the optimizer
  handoff case) shows the heading "Construction Review" and the helper text
  "You're now previewing a saved construction. Scroll down to see the
  allocation and replay details."
- [x] AC3 — When a workspace error is set (App-level construction validation or
  preview failure), it renders as a styled error card above the workspace
  content — not as a bare `<p>` element. The card must have
  `data-testid="workspace-error-banner"`.
- [x] AC4 — The cross-reference in `GenericRankingView.tsx` that names
  "Persisted Generic Ranking Construction" is updated to match the new label
  "Generic Ranking Runs".
- [x] AC5 — All existing "Review In Construction" button behaviour is
  unchanged: disabled-reason `<small>` text is still shown for every blocking
  condition, phase-1 errors (browser-level handoff failures) still appear in
  the browser's own error panel, and the optimizer handoff banner copy is
  untouched.

## Test plan

Backend (pytest):
- None — pure frontend change.

Frontend (vitest):
- `PortfolioImprovementWorkspaceShell.test.tsx` — update the existing assertion
  `getByText('Artifact Review Mode')` to `getByText('Construction Review')`;
  assert the new helper text "You're now previewing a saved construction." is
  present in that same test; assert the optimizer-handoff banner test at the
  adjacent `it` block still passes (its helper text is distinct and must not
  change).
- `PortfolioImprovementWorkspaceShell.test.tsx` — update the four tests that
  use `findByText('Persisted ETF Ranking Construction')` or
  `findByText('Persisted Replacement Reviews')` as render-wait synchronizers
  to use the new labels "ETF Ranking Runs" and "Replacement Ranking Runs"
  respectively.
- `PersistedGenericRankingConstructionBrowser.test.tsx` — update the existing
  assertion `findByText('Persisted Generic Ranking Construction')` to
  `findByText('Generic Ranking Runs')`.
- `App.test.tsx` — update all occurrences of `findByText('Persisted ETF Ranking
  Construction')` used as render-wait synchronizers to `findByText('ETF Ranking
  Runs')`; add an assertion that when `workspaceError` state is set, the
  element `getByTestId('workspace-error-banner')` is present in the DOM.

Regression / guardrail:
- All existing tests that check the "Review In Construction" button is enabled,
  disabled, or fires the callback must stay green — no button logic changes.
- The optimizer handoff banner test (`getByText('This workspace reopens a
  hypothetical artifact-backed optimizer review...')`) must stay green.
- All `PersistedEtfRankingConstructionBrowser.test.tsx` tests must stay green.

## Tickets

- [x] T-5.3.1 — Frontend: rename browser panel-labels in
  `PersistedEtfRankingConstructionBrowser.tsx`,
  `PersistedGenericRankingConstructionBrowser.tsx`, and
  `PersistedReplacementRankingBrowser.tsx`; replace "Artifact Review Mode"
  heading and helper text with "Construction Review" copy in
  `PortfolioImprovementWorkspaceShell.tsx` (construction artifact case only);
  wrap `workspaceError` in a styled card with `data-testid="workspace-error-banner"`
  in `App.tsx`; update cross-reference in `GenericRankingView.tsx`; update all
  affected test assertions across `PortfolioImprovementWorkspaceShell.test.tsx`,
  `PersistedGenericRankingConstructionBrowser.test.tsx`, and `App.test.tsx`.

## Out of scope

- Changing the optimizer handoff banner copy (distinct flow, separate concern).
- Changing the "Review In Construction" button disabled logic or the `<small>`
  disabled-reason text (already readable per AC5 guardrail).
- Renaming the `data-testid="persisted-construction-artifact-banner"` attribute
  (internal test identifier, stable, no researcher impact).
- Any backend route, schema, or methodology change.
- Adding sorting, filtering, or pagination to the candidate browsers.

## Notes / decisions

- No financial methodology is involved — this is copy and styling only.
- The optimizer handoff banner uses a separate code branch
  (`isPersistedOptimizerHandoffMode`) and its copy is intentionally different;
  do not merge the two cases.
- `App.tsx` line 3303 currently renders `<p className="error">{workspaceError}</p>`.
  The upgrade to a card should keep the "error" class on an inner element and
  add a wrapping `<div data-testid="workspace-error-banner">` so the existing
  CSS error styling is preserved and the new testid is addressable.
- `GenericRankingView.tsx` line 140 cross-references the old label in an
  explanatory sentence visible to researchers navigating from the Generic
  Ranking tab. It must be updated in the same pass to avoid contradicting the
  UI label the researcher will see in Workspace.
