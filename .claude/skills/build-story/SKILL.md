---
name: build-story
description: Use when implementing a user story or ticket from docs/product/stories/. Triggers when the user says "build US-X.Y", "pick up ticket T-...", "implement the next story", or points at a file under docs/product/stories/. Walks delivery end-to-end — read PRD context, work tickets in order, write tests, satisfy acceptance criteria, update docs, open a PR.
---

# Build Story

This project is developed as **PRD → User Story → Ticket**. A user story is a
vertical slice that delivers user-visible value; it is never an isolated
technical feature. This skill is the delivery workflow for one story.

## Where things live

| Path | Purpose |
|---|---|
| `docs/product/prd/<epic>.md` | PRD per epic — problem, goals, non-goals, success signals, the story list |
| `docs/product/stories/US-<n>-<slug>.md` | One file per user story — story statement, acceptance criteria, **test plan**, tickets, status |
| `docs/product/stories/_TEMPLATE.md` | Story file template — copy it to create a new story |
| `docs/product/stories/README.md` | Story index + lifecycle states |
| `docs/product/epic-roadmap.md` | Epic snapshot + slice log (the index that links PRDs and stories) |

## Before writing any code

1. **Read the story file end to end.** It owns the acceptance criteria and the
   test plan — those are the contract for "done".
2. **Read the linked PRD section.** Understand the problem and the non-goals so
   you do not over-build.
3. **Read `docs/finance/financial-methodology.md`** if the story touches any
   analytics, factor formula, weighting, replay basis, or trust-state logic.
   That doc is the source of truth for every implemented formula.
4. **Confirm the tickets.** A story carries an ordered ticket list
   (`T-<n>.<m>`). Work them top to bottom. If the story has no tickets yet
   (a backlog story), break it into tickets first — append them to the story
   file and stop for review before implementing.
5. If the premise looks wrong (acceptance criteria contradict the methodology
   doc, a ticket is infeasible), **stop and surface it** — do not silently
   reinterpret the story.

## Delivering a ticket

Each ticket is a focused, reviewable change. For every ticket:

1. **Schemas first.** If the ticket changes a Pydantic schema in
   `services/quant-engine/app/schemas/`, change the schema before routes,
   services, or UI. Then mirror it in the desktop TS types and the matching
   `docs/contracts/<area>-fields.md`.
2. **Backend before frontend.** Engine/service/route, then desktop.
   Desktop stays thin on finance — no portfolio math in components.
3. **Tests in the same pass.** Never land a ticket without the tests its slice
   of the story's test plan calls for. A methodology change must include or
   update a regression test.
4. **Honour the guardrails** (see below).
5. Tick the ticket checkbox in the story file.

## Guardrails (non-negotiable — from CLAUDE.md)

1. **Methodology traceability** — every UI metric maps to one engine formula
   and one code path.
2. **Truth-class separation** — broker truth, snapshot analytics, synthetic
   history, persisted artifacts, optimizer previews, replay are distinct.
   Never mix them in one response.
3. **Trust semantics over fabrication** — `verified > degraded > withheld >
   unavailable`. Surface the level; never fabricate, never silently fallback,
   never collapse `withheld` into `unavailable`.
4. **No execution** — optimizer and construction are hypothetical previews.
5. **Fail-closed loading** must not be weakened.

## Verifying the story

A story is done only when **every acceptance criterion is met** and **the whole
test plan passes**:

```bash
python scripts/run_all_tests.py        # canonical: regenerates dashboard goldens, backend pytest, frontend vitest
cd apps/desktop && npx tsc --noEmit    # type-check (NOT run by run_all_tests.py)
```

- `run_all_tests.py` is canonical. Bare `pytest` will fail fast on stale
  dashboard goldens via the autouse freshness fixture — that is expected;
  regenerate with `python -m app.scripts.export_dashboard_goldens`.
- If `run_all_tests.py` leaves `apps/desktop/src/test/dashboardGoldens.ts`
  modified, that is an FMP-cache environment artifact — revert it unless your
  story actually changed dashboard output.

## Closing out

1. Tick every ticket and acceptance-criterion checkbox in the story file; set
   its status to `Done`.
2. Update `docs/finance/financial-methodology.md` + the relevant
   `docs/contracts/*.md` if the story changed methodology or a contract.
3. Add a slice-log entry to `docs/product/epic-roadmap.md` and update the
   epic snapshot row.
4. Commit (one commit per ticket is fine, or one per story), push, open a PR
   that names the story (`US-<n>: <title>`). Squash-merge, prune the branch
   local + remote, fast-forward the primary worktree.

## Definition of Done checklist

- [ ] Every acceptance criterion in the story file is satisfied
- [ ] Every test in the story's test plan exists and passes
- [ ] `python scripts/run_all_tests.py` is green
- [ ] `npx tsc --noEmit` is clean
- [ ] Methodology + contract docs updated if methodology/contract changed
- [ ] Story status set to `Done`; tickets checked off
- [ ] epic-roadmap.md slice log + snapshot updated
- [ ] PR opened naming the story
