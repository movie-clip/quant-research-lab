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
5. An agent delivers a story through the `.agentic` network's
   `orchestrate-feature` skill; new stories are authored with the `write-story`
   skill. (The old `build-story` skill is superseded and must not run.)

## Lifecycle

```
Backlog  ──►  Next phase (ticketed)  ──►  In progress  ──►  Done
 story        story + tickets             story underway     all criteria + tests pass
```

## Index

**`docs/product/epic-roadmap.md` is the authoritative epic index** — it carries
the live status of every epic and the slice log. This file does not duplicate
that table; it only records the PRD-authoring conventions below.

- One PRD file per epic lives in this directory (`epic-<n>-<slug>.md`), written
  retrospectively at epic close-out (the convention established by Epic 37/38/39).
- PRDs for Epics 1, 2 and 4 were never written separately; their shipped state
  lives in `docs/product/current-product-state.md` and their history in
  `docs/product/epic-roadmap.md`.
- Epic 3 (Construction & Optimizer Methodology) was **cancelled** — its features
  were removed in the Epic 8 pivot. Epic 5 (Usable Core Flow) is **complete**,
  also superseded by that pivot. No `epic-3-*.md` / `epic-5-*.md` PRD file exists.

Every epic is currently complete; there is no active epic. See
`docs/product/epic-roadmap.md` for which epic is current at any time.
