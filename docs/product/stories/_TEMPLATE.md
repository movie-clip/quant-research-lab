# US-<n>: <Short title>

**Epic:** <epic number and name>
**PRD:** [`<epic>.md`](../prd/<epic>.md)
**Status:** Backlog | Next phase | In progress | Done
**Last updated:** YYYY-MM-DD

## Story

As a **<role>**, I want **<capability>**, so that **<benefit>**.

## Context

<1–3 sentences: why this matters, what exists today, links to methodology or
contract docs the implementer must read.>

## Acceptance criteria

- [ ] AC1 — <observable, user-facing outcome>
- [ ] AC2 — <...>
- [ ] AC3 — <...>

Each criterion is a fact someone can check, not a task. "Done" = every box
ticked.

## Test plan

Backend (pytest):
- <test name / file> — <what it asserts>

Frontend (vitest):
- <test name / file> — <what it asserts>

Regression / guardrail:
- <e.g. trust-state, fail-closed, reproducibility checks>

## Tickets

Only filled in once the story is in the next active phase. Each ticket is one
focused, reviewable change; work them in order.

- [ ] T-<n>.1 — <change>
- [ ] T-<n>.2 — <change>

## Out of scope

<Explicit non-goals so the story does not creep.>

## Notes / decisions

<Methodology decisions, links to academic precedent, open questions resolved.>
