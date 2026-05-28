---
name: update-docs
description: Use after implementing a story to reconcile docs with the code that just shipped. Triggers when the user says "update the docs for US-X.Y", "close out the story docs", or when build-story auto-delegates the docs close-out. Auto-updates the deterministic stuff (slice log, status flips, contract field tables, current-product-state inventory) and produces a checklist for the judgment stuff (methodology phrasing, citation choice). Always runs AFTER verify-story has passed.
---

# Update Docs

This skill keeps the docs in sync with the code, automatically. It runs at
story close-out (auto-delegated by `build-story`) or whenever the user notices
doc drift.

**Always run `verify-story` first.** This skill assumes the implementation is
correct; it propagates that correctness into the docs. Running it on a broken
implementation just spreads broken claims.

## Scope: auto-update vs flag-for-human

| Action | Auto-update? | Why |
|---|---|---|
| Flip story `Status: Next phase` → `Done` | Auto | Deterministic |
| Tick `[ ]` → `[x]` on ACs and tickets (only those satisfied per verify-story) | Auto | Deterministic |
| Update `Last updated:` field | Auto | Deterministic |
| Add slice log entry to `epic-roadmap.md` | Auto | Deterministic — template-driven |
| Flip epic-roadmap snapshot row status | Auto | Deterministic |
| Flip story status in `stories/README.md` | Auto | Deterministic |
| Add `current-product-state.md` entry for shipped capability | Auto | Template-driven |
| Update contract doc field table for changed schemas | Auto when fields added/removed | Deterministic |
| Add methodology doc section for new formula | Flag — human judgment | Citation choice, phrasing |
| Edit existing methodology section to reflect changes | Flag — human judgment | Wording, edge-case framing |
| Move epic from Active → Completed in roadmap | Auto when all stories Done | Deterministic |
| Create new PRD file | Never | Out of scope (write-story owns) |

When this skill flags something for a human, it must produce a precise
**editable suggestion** — file path, exact location, proposed text — not just
"please update methodology doc."

## Inputs

Required:
- Path to the story file (e.g. `docs/product/stories/US-9.3-multi-benchmark-correlation-matrix.md`)

Optional:
- Slice log entry text (one-liner). If omitted, the skill drafts one from the
  story's tickets + the git diff and prompts the user to confirm before writing.

## Where things live

| Path | What lives there |
|---|---|
| `docs/product/stories/<story-file>.md` | Status, ACs, tickets, last-updated |
| `docs/product/stories/README.md` | Story index with status column |
| `docs/product/epic-roadmap.md` | Epic snapshot table + slice log + epic header |
| `docs/product/current-product-state.md` | Shipped-state inventory by tab/area |
| `docs/finance/financial-methodology.md` | Formula sections |
| `docs/contracts/<area>-fields.md` | Schema field tables (backend ↔ TS ↔ UI) |

## Step 1 — Read the story and the diff

Read the story file. Note: status, ACs (which are ticked), tickets (which are
ticked), test plan, methodology references, contract references.

```bash
git diff main...HEAD --name-only
git log main..HEAD --oneline
```

Categorise changed files:

| Path prefix | Category |
|---|---|
| `services/quant-engine/app/schemas/` | Schema change → contract doc |
| `services/quant-engine/app/analytics/` | Analytics change → methodology doc |
| `services/quant-engine/app/api/routes/` | Route change → API surface in current-product-state |
| `apps/desktop/src/features/portfolio/*.tsx` (non-test) | UI change → current-product-state + contract doc (UI display column) |
| `apps/desktop/src/features/portfolio/types.ts` | TS type → contract doc |
| `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts` | Adapter → no doc impact |

## Step 2 — Story file close-out (auto)

Edit the story file:

1. `Status: Next phase` → `Status: Done`
2. `Last updated:` → today's date (ISO 8601)
3. For each AC listed in the verify-story report as SATISFIED → tick the box
4. For each ticket whose listed work is present in the diff → tick the box

**Never tick an AC that verify-story marked GAP or DRIFTED.** If any AC is
unsatisfied, abort step 2 and report — the story is not actually done.

## Step 3 — Story index (auto)

Edit `docs/product/stories/README.md`:

- Find the row for this story
- Change the status column to `Done`

If the story isn't in the index, add it under the right epic with the row
shape used by sibling stories.

## Step 4 — Epic roadmap (auto)

Edit `docs/product/epic-roadmap.md`:

1. Find the story's row in the epic snapshot table → status → `Done`
2. Append a slice log row in the form:

```
| YYYY-MM-DD | US-X.Y | <one-line: what shipped + test count delta> |
```

Slice log one-liner template (auto-drafted from diff + story; user confirms):

- For a backend+frontend story:
  `<analytics module(s) created>; <schema + service + route + frontend component>; <N1 backend tests green (total), N2 frontend tests green (total); npx tsc --noEmit clean>`
- For a docs-only story:
  `<list of doc files created/updated>; <what changed in each>`
- For a backend-only story:
  `<analytics + service + route>; <N backend tests green (total)>`

Get current test totals from the last verify-story run.

3. **If every story in the epic is now `Done`, flip the epic header** from
`## Active Epic: Epic N — <title>` to `## Completed Epic: Epic N — <title>`.

## Step 5 — Current product state (auto when feature surface changed)

Edit `docs/product/current-product-state.md` if the story added a new
user-visible surface:

- New tab → unlikely (product is fixed at 2 tabs) — flag for human if so
- New card / panel / chart / table within a tab → add a bullet under the
  relevant tab's section
- New backend route → add to the API surface list
- New trust class or trust-state semantic → add to the trust ladder section

The file lives at `docs/product/current-product-state.md`; read it first to
match the existing structure.

## Step 6 — Contract doc reconciliation (auto when schemas changed)

For each changed file in `services/quant-engine/app/schemas/`:

1. Identify the matching `docs/contracts/<area>-fields.md`
2. For each new field in the schema: add a row to the field table with
   Backend type | TS type | UI display | Trust | Nullable | Notes
3. For each removed field: remove the row
4. For each changed field (type, nullability): update the row in place

For consistency, also verify `apps/desktop/src/features/portfolio/types.ts`
mirrors the schema. If it does not, **do not silently edit types.ts** — that
should already have happened in the build-story phase. Flag the mismatch as a
real bug.

## Step 7 — Methodology doc (FLAG — human judgment)

For each new function in `services/quant-engine/app/analytics/`:

Check `docs/finance/financial-methodology.md` for a covering section.

**Section exists, complete (formula + symbols + edges + citation):** OK, no action.

**Section exists, missing pieces:** Auto-add the missing pieces if they are
deterministic (e.g. add the implementation path; add a `Contract rule:` line
if the function returns null on empty input). Flag the section for human
review with a one-line note: "Section §X is missing an academic citation —
suggest <author, year, title> based on Notes in story file."

**Section missing entirely:** Do not author it. Produce a stub like:

```markdown
## <Concept Name>

<!-- TODO(update-docs): section drafted from story US-X.Y; expand before publishing -->

<one-line summary from the story Notes section>

```text
<formula from the story, if cited>
```

Implementation:
- `services/quant-engine/app/analytics/<file>.py`

Contract rule:
- <trust class>; <null behaviour>

Academic precedent:
- TODO: cite per story Notes or quant-research brief
```

And report: "Stub added at §<Concept Name>; needs human review for citation
and edge-case rules."

## Step 8 — Verify and report

Re-run `verify-story` (the docs subset only) to confirm everything is in
sync. Report the diff of doc files touched:

```bash
git diff --stat docs/
```

Output:

```
update-docs report: US-9.3
═══════════════════════════════════════════════

Auto-applied:
  ✓ Story status → Done; 8 ACs ticked; 6 tickets ticked
  ✓ Last updated → 2026-05-28
  ✓ stories/README.md status → Done
  ✓ epic-roadmap.md slice log entry added
  ✓ correlation-fields.md updated (3 new BenchmarkStats fields)
  ✓ current-product-state.md: "Multi-Benchmark Correlation table" added under Exposure tab

Flagged for human review:
  • financial-methodology.md §Multi-Benchmark Correlation — section exists,
    formula matches implementation, citation present (no action needed)
  • epic-roadmap.md — Epic 9 not auto-closed: US-9.5 still open

Files changed:
  docs/product/stories/US-9.3-multi-benchmark-correlation-matrix.md
  docs/product/stories/README.md
  docs/product/epic-roadmap.md
  docs/product/current-product-state.md
  docs/contracts/correlation-fields.md

═══════════════════════════════════════════════
RESULT: PASS
```

## What this skill does NOT do

- Does not write code (read-only on `services/`, `apps/`)
- Does not write tests (delegate to `write-tests`)
- Does not author new PRDs or new stories (delegate to `write-story`)
- Does not author new methodology sections from scratch (stub only; flag for human)
- Does not commit, push, or open PRs

## Definition of Done

- [ ] Story file: status flipped, ACs / tickets ticked per verify-story report
- [ ] stories/README.md updated
- [ ] epic-roadmap.md slice log + snapshot updated (epic header flipped if all Done)
- [ ] current-product-state.md updated if user-visible surface changed
- [ ] Contract doc(s) updated for any schema change
- [ ] Methodology doc: existing sections in sync; new sections stubbed + flagged
- [ ] Structured report with auto-applied vs flagged-for-human breakdown
- [ ] `verify-story` (docs subset) passes after this skill runs
