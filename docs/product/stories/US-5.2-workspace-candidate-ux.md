# US-5.2: Make Workspace candidate selection self-explanatory

**Epic:** 5 — Usable Core Flow
**PRD:** [`epic-5-usable-core-flow.md`](../prd/epic-5-usable-core-flow.md)
**Status:** Done
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want the **Candidate Idea section to show
plain-English column labels and a brief orientation sentence**, so that **I can
pick a ranking run without needing to know internal system identifiers or enum
values**.

## Context

The Workspace "Candidate Idea" section lists saved ranking runs across three
browsers (ETF, Generic, Replacement). Today every browser exposes internal
system detail that means nothing to a researcher: full content-addressed
artifact IDs in an "Artifact" column, a raw SHA-256 "Score Config" hash, and
internal enum strings like `index_constituent` or `etf_peer_group` for
Universe Kind. Column headers are also inconsistently named ("Universe" could
mean size or identity depending on the browser, "Evaluated" is ambiguous, no
unit on "Lookback"). The fix is a pure frontend relabelling pass — no backend
change, no schema change, no methodology change.

## Acceptance criteria

- [x] AC1 — The ETF Ranking browser column order and labels are: Ranked On |
  Peer Group | Benchmark | Lookback (mo) | Confidence | Universe Size | # Ranked
  | Action. The "Artifact" column is absent.
- [x] AC2 — The Generic Ranking browser column order and labels are: Ranked On |
  Universe | Type | Benchmark | Confidence | # Ranked | Action. The "Score
  Config" and "Artifact" columns are absent.
- [x] AC3 — In the Generic Ranking browser, the "Type" cell maps internal enum
  values to readable text: `index_constituent` → "Index",
  `etf_peer_group` → "ETF Peer Group", `custom_list` → "Custom List",
  `broad_equity_screen` → "Screened", `sector_screen` → "Sector Screen". Unknown
  values fall back to the raw string.
- [x] AC4 — The Replacement Ranking browser column order and labels are: Ranked
  On | Incumbent | Candidate | Peer Group | Confidence | Eligible | Excluded |
  Action. The "Artifact" column is absent.
- [x] AC5 — The helper text beneath the "Candidate Idea" heading reads: "Pick a
  saved ranking run to seed a candidate allocation — then choose 'Review In
  Construction' to preview how it would be built."

## Test plan

Backend (pytest):
- None — pure frontend change.

Frontend (vitest):
- `PersistedGenericRankingConstructionBrowser.test.tsx` — assert the rendered
  table header row contains "Ranked On", "Type", "# Ranked" and does not contain
  "Score Config" or "Artifact"; assert that a row with `universe_kind:
  'index_constituent'` renders "Index", and `etf_peer_group` renders "ETF Peer
  Group".

Regression / guardrail:
- All existing `PortfolioImprovementWorkspaceShell.test.tsx` tests that check
  for "Candidate Idea" text or browser behaviour must stay green — no
  functionality removed, only labels changed.
- All existing `PersistedGenericRankingConstructionBrowser.test.tsx` tests must
  stay green.

## Tickets

- [x] T-5.2.1 — Frontend: relabel columns in all three Candidate Idea browsers,
  remove Artifact and Score Config columns, map Universe Kind enum values to
  readable labels, update section description text; add column-header and
  enum-mapping assertions to
  `PersistedGenericRankingConstructionBrowser.test.tsx`.

## Out of scope

- Any backend or schema change.
- Removing or reordering the three browsers themselves.
- Adding sorting or filtering to the tables.
- Changing the "Action" column content (buttons stay as-is).
- Renaming any tab label (covered by earlier discussion, separate if wanted).

## Notes / decisions

- No financial methodology involved — this is labelling only.
- The `artifact_id` is still needed internally (used as `key` prop and in
  button click handlers); only the displayed column is removed.
- The `score_config_id` field on `GenericRankingArtifactRecentRow` remains in
  the TS type — it is just not rendered in the table. No type deletion needed.
- Unknown `universe_kind` values should fall back to the raw string, not
  error, so new values added server-side don't break the UI.
