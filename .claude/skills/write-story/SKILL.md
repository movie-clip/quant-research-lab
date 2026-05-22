---
name: write-story
description: Use when the user has a feature idea and wants a User Story drafted, ticketed, and ready to implement. Triggers when the user says "write a story for X", "create a user story about X", "plan feature X", or describes a new capability they want added. Reads PRD and methodology context, authors the full story file (statement → acceptance criteria → test plan → tickets), saves it, and updates the story index. Output is a Next-phase story file any agent can pick up with build-story.
---

# Write Story

This skill authors one User Story end-to-end: from a feature idea to a complete, ticketed story file that any agent can implement with the `build-story` skill.

## Where things live

| Path | Purpose |
|---|---|
| `docs/product/epic-roadmap.md` | Active epics, phase snapshot, slice log |
| `docs/product/prd/<epic>.md` | PRD — problem, goals, non-goals, story list |
| `docs/product/stories/README.md` | Story index + lifecycle states |
| `docs/product/stories/_TEMPLATE.md` | Story file template |
| `docs/product/stories/US-<n>-<slug>.md` | One file per story |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory |
| `docs/finance/financial-methodology.md` | Source of truth for every formula |
| `docs/contracts/<area>-fields.md` | Backend ↔ TS ↔ UI field contracts |

## Before writing anything

Clarify ambiguous scope with the user before drafting. One well-placed question now prevents a wrong story. Ask if:
- The feature spans more than one epic
- A similar story may already exist in backlog
- The feature involves methodology the user has specific constraints on

## Step 1 — Ground in the right epic

1. Read `docs/product/epic-roadmap.md` — understand active epics and locate where the feature fits.
2. Read the matching PRD (`docs/product/prd/<epic>.md`) — problem, goals, **non-goals**, existing story list.
3. Read `docs/product/stories/README.md` — find the next available story number (`US-<epic>.<n>`).
4. If a similar story already exists, surface it to the user and confirm they want a new one rather than expanding the existing one.

## Step 2 — Understand the methodology

If the feature touches any analytics, factor formula, weighting, replay basis, or trust-state logic:

1. Read `docs/finance/financial-methodology.md` — source of truth for every formula. Never write a criterion that references a metric that isn't defined there; flag it in the story's Notes section instead.
2. Read the relevant `docs/contracts/<area>-fields.md` — backend ↔ TS ↔ UI contract for that feature surface.
3. Read `docs/product/current-product-state.md` — what is already shipped vs intentionally narrow.

## Step 3 — Read existing stories for calibration

Skim 1–2 existing story files in the same epic to match:
- Tone and specificity of the story statement
- Format of acceptance criteria (observable outcomes, not tasks)
- Level of detail in the test plan (named test files, what each asserts)
- Ticket granularity (one focused, reviewable change each)

## Step 4 — Draft the story

Work through each section of `docs/product/stories/_TEMPLATE.md`.

### Story statement

`As a <role>, I want <capability>, so that <benefit>.`

- **Role:** almost always `portfolio researcher` for this product
- **Capability:** a specific, observable action or feature — not "improve X" or "add support for X"
- **Benefit:** why the researcher cares — traceability, reproducibility, decision quality

### Context

1–3 sentences:
- What exists today that this story builds on or replaces
- What specifically changes and why
- Which docs the implementer must read (methodology doc, contract doc)

### Acceptance criteria

Each criterion must be:
- **Observable** — verifiable without reading code
- **User-facing** — describes what the researcher sees or can do
- **Atomic** — one fact per criterion
- **Guardrail-aware** — if missing data is possible, a criterion must address fail-closed or trust-level behaviour explicitly

Cover all relevant cases:
- Happy path (feature works as described)
- Missing / degraded data (trust semantics — fail-closed, not fabricated)
- Replay / reproducibility (if construction or ranking is involved)
- Constraint evaluation (if optimizer is involved)
- Backwards compatibility (existing behaviour unchanged)

### Test plan

Name specific test files and describe what each asserts — not "tests pass".

Backend (pytest):
- `test_<module>.py` — <assertion>

Frontend (vitest):
- `<Component>.test.tsx` — <assertion>

Regression / guardrail:
- Existing tests that must stay green
- Trust-state, fail-closed, reproducibility checks

### Tickets

Break the story into ordered tickets. Each ticket is one focused, reviewable change. Always follow this order:

1. **Schema** — if any Pydantic schema in `services/quant-engine/app/schemas/` changes, this is the first ticket. Mirror change in TS types and the matching `docs/contracts/<area>-fields.md`.
2. **Backend logic** — engine/service changes (one ticket per meaningful seam)
3. **Backend route** — new or modified FastAPI route + route tests
4. **Frontend** — TS types, components, hooks, vitest tests
5. **Docs** — `financial-methodology.md` (formula + academic precedent), contract doc, `epic-roadmap.md` slice log, story status to Done

Number tickets `T-<epic>.<story>.<n>` — e.g. `T-3.2.1`.

Every ticket must include its tests in the same pass — never a separate "add tests" ticket.

### Out of scope

List at least one explicit non-goal. If the user mentioned related ideas this story does not cover, name them here so the implementer does not over-build.

### Notes / decisions

- Any new formula: cite academic precedent here (required — the implementer will add it to `financial-methodology.md`)
- Open questions resolved during authoring
- Implementation constraints or gotchas not obvious from the code

## Step 5 — Save the story file

Write the story to `docs/product/stories/US-<epic>.<n>-<slug>.md`.

- `<slug>`: short kebab-case summary of the capability, max 5 words
- `Status: Next phase` (it is ticketed and ready to implement)
- `Last updated:` today's date

No placeholder text should remain in any section.

## Step 6 — Update the story index

Edit `docs/product/stories/README.md` — add a row to the index table:

```
| [US-X.Y](filename.md) | <title> | <epic> | Next phase |
```

## Guardrails (non-negotiable — from CLAUDE.md)

1. **Methodology traceability** — every AC that references a computed value must trace to a formula in `financial-methodology.md`. If the formula does not yet exist there, note it in the story's Notes section and flag it for the T-docs ticket.
2. **Truth-class separation** — ACs must not mix broker truth, snapshot analytics, synthetic history, persisted artifacts, optimizer previews, or replay in a single criterion.
3. **Trust semantics** — missing or degraded data means fail-closed or explicit trust-level surfacing. Never write an AC that accepts fabrication or silent fallback.
4. **No execution** — no criterion may describe placing trades or moving money.
5. **Desktop stays thin** — tickets must not assign financial computation to frontend components.

## Definition of Done (for this skill)

- [ ] Story file saved at the correct path with no placeholder text
- [ ] Story statement follows the `As a / I want / so that` form
- [ ] Every AC is an observable user-facing outcome (not a task)
- [ ] Test plan names real test files and real assertions
- [ ] Tickets are ordered (schema → backend → route → frontend → docs), each with clear scope
- [ ] Out of scope names at least one non-goal
- [ ] Notes cites academic precedent for any new formula
- [ ] `docs/product/stories/README.md` index updated with the new story
- [ ] No guardrail violated in any AC or ticket
