# US-3.3: Set Top N directly in the ETF Ranking tab

**Epic:** 3 — Construction & Optimizer Methodology
**PRD:** [`epic-3-construction-optimizer-methodology.md`](../prd/epic-3-construction-optimizer-methodology.md)
**Status:** Cancelled — Epic 3's construction/optimizer features were removed in Epic 8 (reset to the portfolio-analysis core). Kept for provenance; the story index has said Cancelled since then, while this file still read "Backlog".
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want to **set the construction Top N directly
in the legacy ETF Ranking tab**, so that **I can launch construction with a
chosen Top N without having to route through the Workspace browsers**.

## Context

The configurable-`top_n` slice (`[2, 20]`) shipped a Top N input in the three
Workspace construction browsers but intentionally left `EtfRankingPanel` (the
legacy ETF Ranking tab) hardcoded at `top_n = 2` as a deferred follow-up. This
story closes that gap so the ETF Ranking tab matches the Workspace browsers.

## Acceptance criteria

- [ ] AC1 — The ETF Ranking tab exposes a Top N input, defaulting to 2,
  validating to the `[2, 20]` range with the shared validator.
- [ ] AC2 — Launching construction from the ETF Ranking tab uses the entered
  Top N; an out-of-range or non-integer value blocks the launch with a clear
  message.
- [ ] AC3 — Behaviour matches the Workspace construction browsers — same
  validator, same range, same error copy.

## Test plan (rough — refine when ticketed)

Frontend (vitest):
- `EtfRankingPanel.test.tsx` — Top N input defaults to 2, accepts in-range
  values, blocks out-of-range / non-integer values.
- The entered Top N reaches the construction run request.

Regression:
- Existing ETF Ranking tab tests stay green.

## Tickets

Not yet ticketed — backlog story. Ticketed when pulled into the active phase.

## Out of scope

- Any backend change — `top_n` `[2, 20]` is already supported end-to-end.
- Other construction constraints in the ETF Ranking tab (separate story if
  wanted).

## Notes / decisions

- UI-completeness story; reuses the shared `validateRankingConstructionTopNInput`
  validator already used by the Workspace browsers.
