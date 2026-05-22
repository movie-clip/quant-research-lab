# Product Requirements & Delivery Model

This project is built as **PRD → User Story → Ticket**. Work is delivered in
vertical slices that produce user-visible value — never as isolated technical
features.

## The three layers

| Layer | Lives in | Owns | Granularity |
|---|---|---|---|
| **PRD** | `docs/product/prd/<epic>.md` | Problem, goals, non-goals, success signals, the ordered list of user stories for an epic | One per epic |
| **User Story** | `docs/product/stories/US-<n>-<slug>.md` | A vertical slice of value: story statement, acceptance criteria, **test plan**, tickets, status | One file per story |
| **Ticket** | A checklist item inside a story file (`T-<n>.<m>`) | One focused, reviewable change | Several per story |

## Rules

1. **A story is a unit of value, not a unit of code.** "As a `<role>`, I want
   `<capability>`, so that `<benefit>`." If it cannot be phrased that way, it is
   a ticket, not a story.
2. **Every story carries a test plan.** Acceptance criteria are not "done"
   until the named backend (pytest) and frontend (vitest) tests exist and pass.
3. **Tickets are only broken out for the next phase.** Backlog stories are
   defined (statement + acceptance criteria + rough test plan) but not yet
   decomposed into tickets — that happens when the story is pulled into the
   active phase, to avoid stale planning.
4. **Guardrails always apply** — methodology traceability, truth-class
   separation, trust semantics, no execution, fail-closed loading. See
   `CLAUDE.md`.
5. An agent delivers a story with the `build-story` skill
   (`.claude/skills/build-story/`).

## Lifecycle

```
Backlog  ──►  Next phase (ticketed)  ──►  In progress  ──►  Done
 story        story + tickets             story underway     all criteria + tests pass
```

## Index

| PRD | Epic | Status |
|---|---|---|
| `epic-3-construction-optimizer-methodology.md` | Epic 3 — Construction & Optimizer Methodology | Active |

PRDs for Epics 1, 2, 4 are written when those epics next take active work;
their current shipped state lives in `docs/product/current-product-state.md`
and their history in `docs/product/epic-roadmap.md`.
