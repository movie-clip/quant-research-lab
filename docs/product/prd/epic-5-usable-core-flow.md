# PRD — Epic 5: Usable Core Flow

**Status:** Active epic
**Last updated:** 2026-05-22

## Problem

The technical foundation (Epics 1–4) is complete. The product has ranking,
construction, replay, and monitoring — but a researcher who imports their
portfolio cannot reliably walk the golden path to a portfolio decision.

Two confirmed problems from first-hand use:

1. **Tab order does not match the workflow.** The app has tabs for Dashboard,
   Exposure, Diagnostics, Workspace, Backtest, Strategy Lab, ETF Ranking, and
   Generic Ranking. Workspace — the core improvement workflow — is not positioned
   where a researcher expects it after reviewing the Dashboard. The tab order
   implies Exposure and Diagnostics are more important than Workspace; they are
   not for the primary use case.

2. **Workspace candidate section is not self-explanatory.** The ranking artifact
   browser shows columns labelled "As Of", "Peer Group", "Benchmark", "Lookback",
   "Confidence", "Universe", "Evaluated", "Artifact", "Action". A researcher who
   has not built the system does not know what they are selecting or why. More
   critically: selecting an artifact and clicking "Review in Construction" does
   not work — the flow is broken.

3. **Replay output reads as a methodology dump, not a decision.** After a
   construction run, the replay shows provenance blocks, trust classes, and
   methodology labels that are correct but do not answer the actual question:
   "is this proposed allocation better than what I hold today?"

Together, these problems make the product unusable as a portfolio research tool
even though all the underlying engine capability is shipped.

## Goals

- A researcher can open the app and understand immediately where to go after the Dashboard.
- A researcher can select a ranking artifact in Workspace without needing to understand internal system terminology.
- "Review in Construction" works end-to-end from every Workspace candidate browser.
- After a construction replay, the researcher sees a clear before/after comparison: returns, drawdown, turnover cost — framed as "current vs proposed", not as a methodology audit.

## Non-goals

- No new ranking factors, construction policies, or constraint types in this epic.
- No changes to the underlying engine math or trust semantics.
- No new backend routes (fixes may touch existing routes but this epic does not add capability).
- No execution — construction and optimizer outputs remain hypothetical.

## Users

- **Portfolio researcher** — has imported a portfolio and wants to find a better allocation.

## Success signals

- The researcher can complete the golden path (Dashboard → Workspace → select artifact → construct → replay → save) without reading documentation.
- "Review in Construction" does not fail for any supported artifact kind.
- The replay comparison view leads with: portfolio A returned X%, portfolio B returned Y%, max drawdown A vs B, turnover cost of switching.
- The tab order visibly follows the workflow: Dashboard → Workspace → then research tools.

## Shipped baseline

- Backend construction, replay, and policy discovery are complete.
- Three Workspace construction browsers (ETF, replacement, generic ranking) are shipped.
- Replay endpoint and provenance tracking are shipped.
- All trust semantics and fail-closed loading are shipped.

## Story list

Stories are delivered in order — earlier stories unblock later ones.

| Story | Title | Status |
|---|---|---|
| US-5.1 | Fix app navigation order | Next phase |
| US-5.2 | Make Workspace candidate selection self-explanatory | Backlog |
| US-5.3 | Fix "Review in Construction" end-to-end | Backlog |
| US-5.4 | Clear replay comparison output | Backlog |

History and slice log: `docs/product/epic-roadmap.md`.
