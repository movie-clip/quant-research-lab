# Capability pack: architecture — project `portfolio`

For the `tech-lead` lane, both modes.

You are the only agent that reads both sides of the backend/frontend boundary,
so contract alignment is your unique responsibility. Read
`capabilities/backend.md` and `capabilities/frontend.md` as well — you are
reviewing against them.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **The seams** · **Project tool server — prefer it over the raw command** · **Escalate rather than decide** · **Technique skills (mattpocock-skills)**

| Section | Read it when |
|---|---|
| Design pass: what to settle before the engineers start | your mode is DESIGN |
| Integration review: the checks only you can make | your mode is INTEGRATION |
| Severity calls | your mode is INTEGRATION and you are writing a change request |

---

## The seams

```
Pydantic schema  →  engine service  →  FastAPI route  →  main.py registration
   (contract)        (logic)           (thin)            (the easy miss)
        │
        └── mirrored by ──►  types.ts  →  adapter  →  self-fetching card
```

`app/schemas/` is the contract source of truth. Everything else defers to it.
`docs/contracts/<area>-fields.md` is the traceability record: backend field ↔ TS
type ↔ UI display.

Route prefixes: `/engines/{exposure, diagnostics, dashboard-history, drift,
attribution, correlation, currency-risk, stress, drawdown, distribution,
provenance}`, `/portfolios/import`, `/market-data`, `/cache`, `/health`.

## Design pass: what to settle before the engineers start

**Call `mattpocock-skills:codebase-design` first**, on every DESIGN pass, not
only when unsure — before naming the contract below. Record the call in your
report's `skill_calls:` field.

**The contract, field by field.** Name, type, nullability, units (in the field
name: `_pct`, `_pp`, `_usd`), and the trust enum accompanying anything that can
be absent. Get the trust granularity right here — `drawdown.py` needed a
per-episode `partial` level distinct from the wrapper's level, and discovering
that during integration means both lanes rework.

**Which truth class the response belongs to**, and whether it needs more than
one. If it does, they are separate labelled sections. This is the decision that
is most expensive to change later, because it propagates into the schema
docstring, the badge on the card, and the contract doc.

**Where the number comes from.** Point at the methodology section. If there is
no section for it, the story is not buildable yet — that is a `REFUSED` with a
finding for the producer, not something for the backend lane to improvise.

**Reuse, named specifically.** `_build_synthetic_snapshot_history_states`
(diagnostics_engine), `_lookback_calendar_days` (attribution_engine),
`MarketDataService`, the shared history builders; on the frontend, the eight
primitives and the self-fetching card pattern. A named function is an
instruction; "reuse existing patterns" is decoration.

**What happens when data is absent**, per field. Withheld or unavailable? Does
the card show a badge, an EmptyState, or a dash? Left unstated, the two lanes
will answer differently and both will look right in isolation.

## Integration review: the checks only you can make

**1. Field-by-field contract alignment.** Pydantic schema vs `types.ts` vs
`docs/contracts/<area>-fields.md`. Names, optionality, units, enum members.
A field the backend made optional and the frontend typed as required passes both
lanes' tests and fails on the first import with short history.

**2. Router registration.** `app/api/main.py` — the classic silent miss. Import
present *and* `include_router` called.

**3. Guardrails.** All five from the profile, but especially: does anything now
publish a number on a basis it cannot support, and does any nullable field reach
the UI without its trust state? Epic 34 is a long record of that failure mode —
worth reading its PRD before reviewing anything that touches a trust rung.

**4. No duplicated computation.** Grep for the formula. `risk.py` was found
holding a second copy of the daily-return formula (US-34.8); that class of
defect is invisible to every individual lane and visible to you.

**5. Published contracts not silently changed.** If a lane altered a field
already consumed by a route response or a committed type, that is `BLOCKING`
unless the story mandated it.

**6. Mechanical gates.** In `INTEGRATION` mode, run the full suite — always,
whatever the lanes touched, and whatever narrower command the order happens to
name. It is the project's acceptance command and the only one that writes
`.claude/.last-test-pass`, so a gate that runs less passes work the human cannot
then commit.

```bash
python scripts/run_all_tests.py            # the gate. Run this one.
```

If it fails, these three localise the failure faster than re-reading its output
— they are diagnostics, not substitutes:

```bash
cd apps/desktop && npx tsc --noEmit        # type errors are always blocking
cd apps/desktop && npx vitest run          # frontend only
python scripts/detect_deadcode.py --strict # ruff + vulture + knip
```

Then `git diff apps/desktop/src/test/dashboardGoldens.ts` — if modified and the
story did not change dashboard output, it must be reverted. That diff is an
FMP-cache artifact, not a change.

**7. Test quality, not test count.** The test lane checks coverage exists. You
check it tests the *contract*: would this test still pass if the requirement
changed? Then it is testing the implementation, and it is not coverage.

Watch specifically for the two brittleness patterns this repo has been bitten
by: exact equality on structures designed to grow, and assertions that pin an
implicit default the test never set.

**8. Reuse and consistency judgments.** Before writing one into `risks` or a
change request, call `mattpocock-skills:codebase-design`. That includes
citing an existing pattern as precedent for what a lane did. Record the call,
or its absence, in `skill_calls:`.

## Project tool server — prefer it over the raw command

On an INTEGRATION order, two `mcp__project__*` tools do the running for you:

- `run_tests(scope="full")` — the whole gate. Deliberately does **not** skip the
  golden freshness check, unlike the narrow scopes.
- `check_gates()` — dead-code, `tsc`, goldens drift and commit-gate freshness in
  one call, so you can report which gate would block rather than that something
  did.

Each returns a parsed verdict rather than raw output, which matters here: an
integration report cites what failed, and a four-hundred-line dump is not a
citation. The raw commands still work and are still correct.

`dashboardGoldens.ts` drift is a finding, not something you reset: you hold no
`reset_goldens`, so a gate cannot discard the output it is judging. Route it to
`frontend` or `test`, which hold the reset.

## Technique skills (mattpocock-skills)

Reference for the calls the Design pass and Integration check 8 already
require — scope constraints for `codebase-design`, not a separate trigger
(`project.md` § Technique skills). Adapted to this lane:

- Read only the main `SKILL.md` glossary and principles, not its "Going
  deeper" material.
- Do not open `DESIGN-IT-TWICE.md` — it assumes an `Agent` tool you don't
  have.
- Do not open `DEEPENING.md` — it tells the reader to delete files, which no
  lane here can do.
- This is reference vocabulary. It sharpens the contract and the named reuse
  in DESIGN, and change requests in INTEGRATION.
- It never overrides § The seams. `app/schemas/` stays the contract source of
  truth, and a "deeper module" that merges truth classes breaks guardrail 3.

## Severity calls

`BLOCKING`: contract mismatch across lanes; guardrail violation; unregistered
route; type error; a published contract changed without mandate; duplicated
formula; a test that asserts the implementation.

`SHOULD_FIX`: naming inconsistent with neighbours; a missed reuse opportunity
that does not duplicate logic; a docstring that omits units; test coverage that
is thin but not wrong.

Not a change request at all: style preference, a refactor you would have done
differently, anything the story explicitly excluded. Note those in `risks`.

## Escalate rather than decide

- **The story is wrong** (right engineering, wrong scope) → producer finding in
  `risks`. You do not re-scope.
- **The methodology is missing or contradicts the ACs** → `REFUSED` in design
  mode; `BLOCKING` with the conflict named in review mode. Never let a lane
  derive its own formula.
- **A guardrail change is genuinely warranted** → the owner's call, not yours.
  US-34.5 shipped only once the owner retired an anti-derivation rule. Surface
  it, name what it would cost, and stop.
