---
name: write-story
description: Use when the user has a feature idea and wants a User Story drafted, ticketed, and ready to implement. Triggers when the user says "write a story for X", "create a user story about X", "plan feature X", or describes a new capability they want added. Reads PRD + methodology context, authors the full story file (statement → ACs → test plan → tickets), saves it, updates the index. Output is a Next-phase story file any agent can pick up with build-story.
---

# Write Story

This skill authors **one** User Story end-to-end: from a feature idea to a
complete, ticketed story file that any agent can implement with the
`build-story` skill.

**This skill does not write code.** It produces a contract (the story file).
The handoff to implementation is via `build-story`.

## The cycle this skill plugs into

```
quant-research → write-story → build-story → write-tests → verify-story → update-docs
   (research)    (this skill)    (implement)    (cover)        (QA)         (sync docs)
```

If the feature involves a new financial formula or non-trivial methodology,
the user should run `quant-research` first — it produces a Research Brief
this skill consumes.

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

## Before drafting

Clarify ambiguous scope with the user before writing. One well-placed question
now prevents a wrong story. Ask if:

- The feature spans more than one epic
- A similar story may already exist in backlog
- The feature involves methodology the user has specific constraints on
- The feature implies a backend formula not yet in `financial-methodology.md`
  (if so, suggest running `quant-research` first)

## Step 1 — Ground in the right epic

1. Read `docs/product/epic-roadmap.md` — locate where the feature fits.
2. Read the matching PRD (`docs/product/prd/<epic>.md`) — problem, goals,
   **non-goals**, existing story list.
3. Read `docs/product/stories/README.md` — find the next story number
   (`US-<epic>.<n>`).
4. If a similar story exists, surface it to the user and confirm they want a
   new one rather than expanding the existing one.

## Step 2 — Understand the methodology and module layout

If the feature touches analytics, factor formulas, weighting, replay basis, or
trust-state logic:

1. Read `docs/finance/financial-methodology.md` — source of truth. Never write
   a criterion that references a metric not defined there; flag it in Notes
   instead, and add a docs ticket to fill the gap.
2. Read the relevant `docs/contracts/<area>-fields.md` — backend ↔ TS ↔ UI
   contract.
3. Read `docs/product/current-product-state.md` — what already ships.

**Where new analytics belong (so tickets file them correctly):**

| Module path | What goes here |
|---|---|
| `services/quant-engine/app/analytics/correlation.py` | Pearson, beta, R² scalars |
| `services/quant-engine/app/analytics/attribution.py` | Factor return attribution |
| `services/quant-engine/app/analytics/risk.py` | Rolling factor model, volatility, rolling risk series |
| `services/quant-engine/app/analytics/drawdown.py` | Underwater curve, drawdown episodes, per-position contributors (Risk tab) |
| `services/quant-engine/app/analytics/distribution.py` | Return histogram, percentiles, VaR/CVaR, distribution shape (Risk tab) |
| `services/quant-engine/app/analytics/drift.py` | Portfolio vs benchmark drift |
| `services/quant-engine/app/analytics/exposure.py` | Sector / look-through composition |
| `services/quant-engine/app/analytics/portfolio.py` | TWR, money-weighted return |
| `services/quant-engine/app/services/<name>_engine.py` | Service that wires market data → pure analytics |
| `services/quant-engine/app/api/routes/<name>.py` | FastAPI route (registered in `app/api/main.py`) |
| `services/quant-engine/app/schemas/<name>.py` | Pydantic request/response models |
| `apps/desktop/src/features/portfolio/<Name>Card.tsx` or `<Name>Chart.tsx` | UI component |
| `apps/desktop/src/features/portfolio/types.ts` | Mirrored TS types |
| `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts` | `runFooEngine(snapshot, ...)` adapter |

A new analytic that doesn't fit any existing module gets its own file —
don't shoehorn into `risk.py`.

## Step 3 — Read 1–2 existing stories for calibration

Skim same-epic story files to match:

- Tone and specificity of the story statement
- Format of ACs (observable outcomes, not tasks)
- Test plan detail (named files + exact assertions)
- Ticket granularity (one focused, reviewable change each)

## Step 4 — Draft the story

Work through each section of `docs/product/stories/_TEMPLATE.md`.

### Story statement

`As a <role>, I want <capability>, so that <benefit>.`

- **Role:** almost always `portfolio researcher`
- **Capability:** specific, observable — not "improve X" or "add support for X"
- **Benefit:** why the researcher cares — traceability, reproducibility, decision quality

### Context

1–3 sentences:

- What exists today this story builds on or replaces
- What changes and why
- Which docs the implementer must read (methodology section name, contract doc)

### Acceptance criteria

Each criterion must be:

- **Observable** — verifiable without reading source
- **User-facing** — describes what the researcher sees or can do
- **Atomic** — one fact per criterion
- **Guardrail-aware** — if missing data is possible, a criterion must spell out
  the fail-closed or trust-level behaviour

Cover all relevant cases:

- Happy path
- Missing / degraded data (fail-closed, not fabricated)
- Replay / reproducibility (if construction or ranking is involved)
- Backwards compatibility (existing behaviour unchanged)

**Synthetic-history calibration check.** If any AC describes a metric computed
by applying *current holdings* to *historical prices* (anything in the drift,
correlation, attribution, or rolling-risk family), that AC must explicitly
require a `Synthetic` trust badge on the UI surface and a `'synthetic'` /
`'unavailable'` trust field in the schema. Never write an AC that lets such a
metric appear as `verified`.

### Test plan

Name specific test files **and exact test counts**. Vague test plans
("add tests for correlation") produce vague coverage. Use this shape:

Backend (pytest):
- `test_<module>_engine.py` — **N tests**: <test 1 one-liner>; <test 2 one-liner>; …

Frontend (vitest):
- `<Component>.test.tsx` — **N tests**: <test 1 one-liner>; <test 2 one-liner>; …

Regression / guardrail:
- Existing tests that must stay green (name them)
- Trust-state, fail-closed, reproducibility checks

**Test-fixture gotcha to flag in the test plan.** If route tests will POST to
an endpoint that consumes `ImportedPortfolioSnapshot`, mention the
`_minimal_snapshot()` helper in `test_attribution.py` — the schema requires
`statement` (with `importer`, `imported_at`, `source_path`, `detected_format`),
`instruments: []`, `positions` (with `as_of_date`, `cost_basis`,
`unrealized_pnl`, etc.), `cash_balances: []`, `ledger_entries: []`. A vague
test plan that just says "POST minimal payload" yields hours of 422
debugging.

### Tickets

Break the story into ordered tickets. Each ticket is one focused, reviewable
change. Always follow this order:

1. **Schema** — if any Pydantic schema in `app/schemas/` changes, this is
   first. Mirror TS types + contract doc in the same ticket.
2. **Backend analytics** — pure functions in `app/analytics/<name>.py`
3. **Backend service** — `app/services/<name>_engine.py` wiring market data
   to analytics
4. **Backend route** — `app/api/routes/<name>.py` + registration in
   `app/api/main.py` + route tests
5. **Frontend types + adapter** — `types.ts` + `portfolioAnalysisAdapter.ts`
6. **Frontend component** — `<Name>Card.tsx` / `<Name>Chart.tsx` / `<Name>Table.tsx`
   + vitest. Default to the **self-fetching component pattern**: component
   takes a `snapshot` prop, manages its own `useEffect`-driven fetch, holds
   `'idle' | 'loading' | 'error' | 'done'` state. Avoids App.tsx wiring
   overhead and `PortfolioSnapshot` vs `ImportedSnapshot` type clashes.
7. **Wire-in** — render the component in `ExposurePanel` / `DashboardPanel`.
   Usually a tiny ticket — often combinable with the component ticket.
8. **Docs close-out** — `financial-methodology.md` (formula + academic
   citation), contract doc, `epic-roadmap.md` slice log, `current-product-state.md`,
   story status to Done. This ticket is auto-executable via the `update-docs`
   skill at story close.

Number tickets `T-<epic>.<story>.<n>` — e.g. `T-9.3.1`.

**Every ticket must include its tests in the same pass** — never a separate
"add tests" ticket. Tests are not optional, and the `write-tests` skill
expects to be invoked on each ticket's slice.

### Out of scope

List at least one explicit non-goal. If the user mentioned related ideas
this story does not cover, name them here so the implementer does not
over-build.

### Notes / decisions

- Any new formula: cite academic precedent here (required — the implementer
  will paste this into `financial-methodology.md`)
- Open questions resolved during authoring
- Implementation gotchas not obvious from the code
- If `quant-research` produced a Research Brief, link it here

## Step 5 — Save the story file

Write to `docs/product/stories/US-<epic>.<n>-<slug>.md`.

- `<slug>`: short kebab-case, max 5 words
- `Status: Next phase` (it is ticketed and ready to implement)
- `Last updated:` today's date (ISO 8601)

No placeholder text in any section.

## Step 6 — Update the story index

Edit `docs/product/stories/README.md` — add a row to the index table:

```
| [US-X.Y](filename.md) | <title> | <one-line scope> | Next phase |
```

## Guardrails (non-negotiable — from CLAUDE.md)

1. **Methodology traceability** — every AC referencing a computed value must
   trace to a formula in `financial-methodology.md`. If the formula does not
   yet exist there, note it in Notes and flag it for the docs ticket.
2. **Truth-class separation** — ACs must not mix broker truth, snapshot
   analytics, synthetic history, persisted artifacts, or replay in one
   criterion.
3. **Trust semantics** — missing or degraded data means fail-closed or
   explicit trust-level surfacing. Never an AC that accepts fabrication or
   silent fallback.
4. **No execution** — no criterion may describe placing trades or moving money.
5. **Desktop stays thin** — tickets must not assign financial computation to
   frontend components. The frontend may rebase/format/color, never compute
   correlations, returns, betas, etc.

## Definition of Done (for this skill)

- [ ] Story file saved at the correct path with no placeholder text
- [ ] Story statement follows `As a / I want / so that` form
- [ ] Every AC is an observable user-facing outcome (not a task)
- [ ] Synthetic-history trust calibration is explicit where applicable
- [ ] Test plan names real test files **with exact test counts** and per-test assertions
- [ ] Tickets are ordered (schema → analytics → service → route → types/adapter → component → wire-in → docs)
- [ ] Out of scope names at least one non-goal
- [ ] Notes cites academic precedent for any new formula
- [ ] `docs/product/stories/README.md` index updated
- [ ] No guardrail violated in any AC or ticket
