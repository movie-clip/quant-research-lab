---
name: verify-story
description: Use after implementing a story to verify it is actually done — every acceptance criterion satisfied, every test in the test plan exists and passes, methodology + contract docs consistent with code, no regressions. Triggers when the user says "verify US-X.Y", "is the story done", "check the implementation", or when build-story auto-delegates the verification step before committing. **Blocks the commit when verification fails** — agents must not commit a story until verify-story reports PASS.
---

# Verify Story

This skill is the QA gate between implementation and commit. It does not write
code or docs — it reads, checks, and reports.

**Contract:** if `verify-story` returns FAIL, the calling agent must not commit.
Build-story auto-invokes this skill before close-out; manual callers should
treat its output the same way.

## What it verifies

A story is verifiable along five axes. The skill walks each one in order and
short-circuits on the first hard failure (no point checking docs if tests are red).

| # | Axis | Pass criterion |
|---|---|---|
| 1 | Acceptance criteria | Every AC in the story file is observably satisfied by the implementation |
| 2 | Test coverage | Every test in the story's test plan exists, with the named file + count |
| 3 | Test suite | `python scripts/run_all_tests.py` is green; `npx tsc --noEmit` clean |
| 4 | Contract & methodology drift | If schemas changed, contract doc updated; if formulas changed, methodology updated |
| 5 | Repo hygiene | `dashboardGoldens.ts` reverted if not a dashboard story; no stray files; status flipped |

## Inputs

Required:
- Path to the story file (e.g. `docs/product/stories/US-9.3-multi-benchmark-correlation-matrix.md`)

Optional:
- A specific ticket to verify (e.g. `T-9.3.4`) — when called per-ticket
- "skip-tests" flag — only when caller has already run tests in this session and shows the green result

If the user invokes you without a story path, ask for one or infer from
`git log` (the most recent `US-X.Y:` commit) and confirm.

## Step 0 — Read the story

Read the story file end to end. Extract:

- The full AC list
- The full test plan with named files + counts
- The ticket list
- Status field (warn if already "Done" — verifying a "Done" story is fine, but
  surface it so the user knows nothing should change)

Read the linked PRD section if methodology context is needed.

## Step 1 — Verify acceptance criteria

For each AC in the story file:

1. Locate the implementation that satisfies it (Grep the codebase for the
   relevant symbol / component / route)
2. Read enough of the implementation to confirm the AC's observable behaviour
3. Categorise the AC as one of:
   - **SATISFIED** — implementation matches the AC text
   - **GAP** — implementation missing or partial
   - **DRIFTED** — implementation exists but differs from AC (e.g. AC says
     "sorted by |ρ| descending", implementation preserves request order)

A SATISFIED categorisation requires you to point at the file:line that
implements it. "I think it's done" is not SATISFIED.

**Trust-class spot checks** (always perform regardless of AC text):
- For any new field marked `synthetic` in the schema, verify the UI renders a
  visible "Synthetic" badge
- For any nullable field, verify the UI renders `"—"` (not `0`, `""`, `"N/A"`)
- For any new MarketDataService caller, verify there's an autouse mock in
  `conftest.py` OR explicit `mocker.patch` in tests

## Step 2 — Verify test coverage

For each entry in the story's test plan:

1. Check the named test file exists
2. Count tests in the file (`grep -c "def test_" file.py` for pytest;
   `grep -c "  it(" file.tsx` for vitest)
3. Compare to the count promised in the test plan

| Outcome | Report |
|---|---|
| File exists, count matches | OK |
| File exists, count differs | DRIFTED — list expected vs actual |
| File missing | GAP — name the missing file |

If the test plan was vague (no exact counts — happens for old stories), apply
a minimum-coverage rule:
- Pure analytics module → ≥ 5 tests covering happy path + 4 edge cases
- Route → ≥ 3 tests (shape, empty, unavailable)
- Component → ≥ 4 tests (renders, null state, empty state, interaction)

If coverage is below minimum, report GAP and suggest specific test cases.

## Step 3 — Run the test suite

```bash
python scripts/run_all_tests.py
```

If green, proceed. If red:

- Identify which tests failed
- Categorise:
  - **Story-introduced regression** — failure is in a test you just wrote
  - **Existing-test regression** — failure is in a pre-existing test (much worse)
  - **Stale goldens** — `dashboardGoldens.ts` drift not caused by this story
- Report each with file:test_name and suggested fix

Then:

```bash
cd apps/desktop && npx tsc --noEmit
```

Type errors are always blocking. Report each with file:line.

## Step 4 — Contract & methodology drift

**Schema changes (Pydantic):**

```bash
git diff main...HEAD services/quant-engine/app/schemas/
```

For every changed file in `app/schemas/<name>.py`, verify:

1. `docs/contracts/<name>-fields.md` exists and was updated in the same range
2. `apps/desktop/src/features/portfolio/types.ts` has matching TS types
3. Field-by-field consistency: name, type, nullability

For every new field in a schema:

- Is it documented in the contract doc?
- Does the TS type mirror it?
- If nullable, is the trust class identified?

Report DRIFTED for any inconsistency. (build-story relies on update-docs to
auto-fix these — if you're called before update-docs runs, that's expected.
Report it so the next step can pick it up.)

**Methodology changes (analytics):**

```bash
git diff main...HEAD services/quant-engine/app/analytics/
```

For every new function in `app/analytics/<name>.py`, verify:

1. `docs/finance/financial-methodology.md` has a section covering it
2. The section includes: formula block, symbol definitions, edge-case rules,
   academic citation
3. The implementation matches the formula (skim — full math validation is the
   maintainer's job)

Missing section → GAP. Section exists but no citation → GAP. Section exists
but formula differs from implementation → DRIFTED with diff.

## Step 5 — Repo hygiene

```bash
git status
git diff --name-only main...HEAD
```

Checks:

| Check | Pass criterion |
|---|---|
| Story file status | `Status: Done` (only checked at story-level verify; per-ticket verify skips this) |
| Story file ACs | Every `- [ ]` flipped to `- [x]` |
| Story file tickets | Every `- [ ]` flipped to `- [x]` |
| `dashboardGoldens.ts` | Not modified unless story actually changes dashboard output |
| `epic-roadmap.md` slice log | New entry for this story |
| `README.md` (stories) | Status column updated |
| Stray files | No untracked debug logs, scratch files, `.bak` files |

For "story actually changes dashboard output" — heuristic: did any file under
`services/quant-engine/app/services/dashboard*` or `app/analytics/performance.py`
change? If no → goldens must be reverted. If yes → goldens diff must match
intent.

## Reporting

Emit a structured report. Pass/fail must be unambiguous.

```
verify-story report: US-9.3
═══════════════════════════════════════════════

Acceptance criteria (8 total)
  ✓ AC1: route exists at POST /engines/correlation/multi (correlation.py:11)
  ✓ AC2: BenchmarkStats has all required fields (schemas/correlation.py:16-22)
  ✓ AC3: <20 trading days → trust='unavailable' (correlation_engine.py:185)
  ✗ AC4: GAP — "sorted by |ρ| descending" — backend does sort but frontend
        re-renders in request order in BenchmarkCorrelationTable.tsx
  ✓ AC5: null → "—" (BenchmarkCorrelationTable.tsx formatValue helper)
  …

Test coverage
  ✓ test_correlation_engine.py — 22 tests (plan: 22)
  ✓ BenchmarkCorrelationTable.test.tsx — 5 tests (plan: 5)

Test suite
  ✓ python scripts/run_all_tests.py — 261 backend + 107 frontend green
  ✓ npx tsc --noEmit clean

Contract & methodology drift
  ✓ docs/contracts/correlation-fields.md updated
  ✓ docs/finance/financial-methodology.md has §Multi-Benchmark Correlation
  ✓ types.ts mirrors schemas/correlation.py

Repo hygiene
  ✓ Status: Done
  ✓ All ACs ticked
  ✓ All tickets ticked
  ✓ dashboardGoldens.ts reverted
  ✓ epic-roadmap.md slice log entry present

═══════════════════════════════════════════════
RESULT: FAIL — 1 GAP (AC4)
Suggested fix: BenchmarkCorrelationTable.tsx already maps over
result.benchmarks; if backend sorts, frontend ordering is correct. Verify
backend actually sorts (correlation_engine.py:201-206) — looks OK.
Re-check AC4 by inspecting the test that asserts sort order.
```

The result must be exactly one of:

- **PASS** — every axis green; safe to commit
- **FAIL** — at least one GAP / DRIFT / red test; commit blocked
- **PASS-WITH-WARNINGS** — soft issues (e.g. test count off by one but coverage
  reasonable); caller decides whether to commit

When PASS, also surface a one-liner the caller can include in the commit body:
"Verified by verify-story: AC ×N, tests ×M, regression suite green."

## What this skill does NOT do

- Does not write code (only reads + reports)
- Does not write tests (delegate to `write-tests`)
- Does not update docs (delegate to `update-docs`)
- Does not commit, push, or open PRs
- Does not judge whether the story's *premise* was right (that's `write-story`'s job)

## Definition of Done (for this skill)

- [ ] Read the story file and PRD context
- [ ] Categorised every AC as SATISFIED / GAP / DRIFTED with file:line evidence
- [ ] Compared test counts to plan
- [ ] Ran the test suite (or confirmed caller did)
- [ ] Checked schema/contract/methodology drift
- [ ] Checked repo hygiene
- [ ] Emitted a structured report with unambiguous PASS / FAIL / PASS-WITH-WARNINGS
