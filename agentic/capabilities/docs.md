# Capability pack: docs — project `portfolio`

For the `docs-engineer` lane. Runs at close-out, after both gates pass.

Mirrors `portfolio/.claude/skills/update-docs/SKILL.md` — read that skill for
the full templates.

**Never run this lane on unverified work.** This lane propagates correctness
into the docs. Run it on a broken implementation and it propagates broken
claims into the project's sources of truth, which is worse than no docs at all.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Auto-update vs flag-for-human** · **What not to do** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| Where things live | you are looking for which doc owns a fact |
| The second close-out order: applying pack corrections | your order is a close-out pack-corrections order |
| Step 1 — Read the story and the diff | your order is a story close-out |
| Step 2 — Never tick an unsatisfied box | your order is a story close-out |
| You own the story's status field — nobody upstream does | your order is a story close-out |
| Step 3 — Contract docs | your order changes a contract doc |

---

## Where things live

| Path | What lives there |
|---|---|
| `docs/product/planning.md` | how stories/epics/roadmap work - read first |
| `docs/product/stories/<story>.md` | frontmatter (`status:`, `closed:`), ACs, tickets |
| `docs/product/epics/EP-<n>-<slug>.md` | optional epic grouping; most stories have none |
| `docs/product/ROADMAP.md` | GENERATED index - never hand-edited |
| `docs/product/current-product-state.md` | shipped-state inventory by tab/area |
| `docs/finance/financial-methodology.md` | formula sections |
| `docs/contracts/<area>-fields.md` | schema field tables (backend ↔ TS ↔ UI) |
| `docs/tech-debt-register.md` | deferred improvements |

## Auto-update vs flag-for-human

The split is deterministic-vs-judgment, and it is not negotiable.

**Auto:** story frontmatter `status: done` + `closed:` → today (ISO 8601); tick
ACs and tickets that the reviewer marked satisfied; regenerate
`docs/product/ROADMAP.md` with `python scripts/build_roadmap.py`;
`current-product-state.md` entry; contract field table when fields were added
or removed; an epic file's own `status:` when every story in it is done.

**Flag for a human — methodology content you would have to compose.** If an
order names a section of `financial-methodology.md` but leaves you to phrase the
formula, choose the citation, or frame the edge case, **do not write it.** Put
what the section would need into `handoff`, addressed to the quant lane, and
leave the file untouched. That is a flag: the section does not exist until
someone who owns the mathematics writes it. See also *Never invent a formula*
under **What not to do** — this is that rule, applied to a whole section.

**Auto: methodology content the order specifies.** Exact wording, or wording the
order points at — a quant finding's own `expected:` text, a formula block from
the technical plan. Write it, name the source in `changed`, report `DONE`. There
is no conflict to report and no `PARTIAL` to set: you are not exercising the
judgment this rule protects, you are transcribing a decision someone else
already made, and the quant lane reads this file on every dispatch and audits
what is in it.

This split replaced a flat "any new methodology section is flag-for-human". That
version could not do anything: core § "When the order and your capability pack
disagree" says a pack convention never blocks an order, so a rule phrased as
*flag instead of writing* could only ever produce a conflict report after the
fact. Across five dispatches that touched `financial-methodology.md`, five wrote
it and none withheld — and the human accepted the content every time. The
protection was real; where it was placed was not.

**Never auto-create an epic file.** `docs/product/epics/` is optional grouping
and most stories correctly have no epic at all (`planning.md` § The three
artifacts). Opening one so a closed story has a parent is exactly the inflation
the generated roadmap removed the incentive for. If a grouping genuinely
belongs, say so in `handoff` and let the human open it.

## The second close-out order: applying pack corrections

This order scopes you to `agentic/capabilities/`, with
`<run_dir>/pack-corrections.md` as its input. Nothing else is in scope on it.

**How to apply an entry is `protocol/packs.md` § Applying corrections**, which
you read on this order. Work from that file, not from memory of this one.

When you flag, produce an **editable suggestion** — file path, exact location,
proposed text. "Please update the methodology doc" is not a handoff; it is a
note to write the handoff later.

## Step 1 — Read the story and the diff

**You have no `Bash`, so you cannot run `git diff` yourself.** You do not need
to: your order's `inputs` name the upstream lanes' reports, and their `changed:`
sections **are** the diff — each is one line per file, written by the lane that
touched it. Read those, plus the files they name.

That is the relay rule doing its job. A lane report's `changed:` list is a
better source than `git diff` anyway: it says what changed *and why*, and it
cannot include an unrelated edit that happened to be in the working tree.

If your order names no upstream reports and you genuinely cannot tell what
shipped, that is `status: BLOCKED` — not a guess.

| Changed path | Doc impact |
|---|---|
| `app/schemas/` | contract doc |
| `app/analytics/` | methodology doc (flag) |
| `app/api/routes/` | API surface in current-product-state |
| `features/portfolio/*.tsx` (non-test) | current-product-state + contract doc UI column |
| `features/portfolio/types.ts` | contract doc |
| `features/portfolio/portfolioAnalysisAdapter.ts` | none |

**Read the diff, not the story.** Document what shipped. Stories routinely come
out smaller or differently-shaped than written, and a doc describing the plan
rather than the code is the exact drift this lane exists to prevent.

## Step 2 — Never tick an unsatisfied box

If the reviewer marked any AC as `GAP` or `DRIFTED`, **abort and report**. The
story is not done, and ticking its boxes makes it permanently look done. This is
the one place where a docs error is unrecoverable by later inspection.

## You own the story's status field — nobody upstream does

The story author does not flip `status:`, and neither does the producer. That
field records what **shipped**, so it is written here, at close-out, from the
diff — together with `closed:`, which `build_roadmap.py` requires once the
status is `done`.

If you arrive and find the story already marked `done`, that is a finding:
someone upstream wrote an intention into a state record. Report it in `risks`
and reconcile the field against what actually shipped rather than assuming it
is correct.

**There is no separate index to update.** `docs/product/ROADMAP.md` is
generated from these fields by `python scripts/build_roadmap.py`, and
`run_all_tests.py` fails while it is stale. Regenerate it in the same edit and
commit the result; do not hand-edit it.

**The slice narrative still gets written — into the story file, not the index.**
The old `epic-roadmap.md` slice log recorded more than what shipped: premise
corrections caught before implementing, defects the work surfaced, decisions
deliberately not taken and why. That is the most valuable thing a close-out
produces and it does not survive in a one-row generated table, so write it as a
short delivered-block at the top of the story, the way
`US-44.1-risk-tab-annualized-volatility.md` does: run id, lane outcomes, gate
verdicts, suite counts, and what was found. Draft it from the diff and the run
ledger; confirm the counts against the last verification run rather than
recalling them.

The two corruptions the old hand-maintained roadmap produced — an epic marked
active while its only story was not, and two epics active at once because a new
section was inserted above a closed one — are now unreachable by construction:
there is one status field per file and nothing restates it.

## Step 3 — Contract docs

For each schema change named in the backend lane's `contract_notes`, update
`docs/contracts/<area>-fields.md`: the backend field, the TS type, the UI
display. All three columns, or the traceability the doc exists to provide is
broken.

Every `contract_note` from every lane must land in a doc or be explicitly
dismissed with a reason in your report. An unabsorbed note is undocumented
drift.

## What not to do

- **Never invent a formula, a field, or a trust rule.** If the implementation is
  unclear, that is a `risks` entry, not a guess in a source-of-truth doc. A
  plausible-sounding wrong formula in `financial-methodology.md` is worse than
  an acknowledged gap, because everything downstream defers to it.
- **Do not tidy adjacent docs.** Out-of-scope doc changes hide the real diff.
- **Do not report success on a partial reconciliation.** Say which items landed
  and which were flagged.

## Definition of done for this lane

- [ ] Story status, ACs, tickets, `Last updated:` reconciled — nothing ticked that the reviewer did not confirm
- [ ] Story index and epic snapshot rows updated
- [ ] Slice log entry written in the house style, confirmed with the user
- [ ] `current-product-state.md` reflects the new user-visible surface
- [ ] Every `contract_note` from every lane landed or explicitly dismissed with a reason
- [ ] Methodology content you had to compose was flagged to the quant lane, not written;
      content the order specified was written, with its source named in `changed`
- [ ] Epic header flipped if the epic is now complete
