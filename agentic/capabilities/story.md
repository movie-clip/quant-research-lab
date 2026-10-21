# Capability pack: story — project `portfolio`

For the `story-author` lane.

Companion source: `portfolio/.claude/skills/write-story/SKILL.md` — read it for
the drafting craft (how ACs are phrased here, how the test plan reads).

**But do not follow its process.** That skill was written before this network
existed, when it *was* the pipeline. It instructs its user to decide epic
placement, update the roadmap and the story index, and hand off to
`build-story`. In this network those belong to the human, the docs lane, and the
orchestrator. Take the writing conventions; leave the workflow.

This is a live example of the two-sources-of-truth problem: the repo skill and
this pack overlap, and the skill will not be updated when the network changes.
When they conflict, this pack wins.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Files** · **Status values** · **Guardrails as they show up in acceptance criteria** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| Read the nearest sibling story first | always, before drafting — it is one file |
| Sizing | you are deciding whether this is one story or several |
| Common failure modes here | before you report — read it as a checklist |

---

## Files

| Path | Your relationship to it |
|---|---|
| `docs/product/planning.md` | the frontmatter contract your file must satisfy |
| `docs/product/stories/US-<n>.<m>-<slug>.md` | **the one file you create** |
| `docs/product/ROADMAP.md` | read for numbering and precedent. **Generated — do not edit.** |
| `docs/product/epics/EP-<n>-<slug>.md` | read the epic's goals and non-goals, *when one exists* |
| `docs/finance/financial-methodology.md` | read when the story touches a formula |
| `docs/contracts/<area>-fields.md` | read to see what the contract *is* today |

Numbering: `US-<n>.<m>-<slug>.md`, tickets `T-<n>.<m>.<k>`. Open the file with
the frontmatter block `planning.md` specifies — `id` must match the filename,
and omit `epic:` unless an `EP-<n>` file already exists. An unparseable block
fails `run_all_tests.py`, so it is not a formality. `status:` is § Status
values.

## Read the nearest sibling story first

Before drafting, read one or two recent stories from the same area. US-45.1 is
the current-shape model — frontmatter, ACs, test plan, tickets. US-15.1 and
US-15.2 are the richer models for a full-stack analytics slice: how ACs are
phrased, how the reconciliation invariant is stated as a checkable criterion,
how the "Notes / decisions" section records what was considered and rejected.

**Every `US-` and `Epic` named in this pack below `US-44.1` is
git-history-only.** The story and PRD corpus was deleted at commit `ce9c97d`;
the two files under `docs/product/stories/` are the only ones on disk. The
citations are kept because the precedents are real and still worth reading —
but read them out of Git, not off the filesystem, and do not report a missing
file as a pack correction:

```bash
git ls-tree -r --name-only ce9c97d^ docs/product/stories/ | grep US-15.1
git show "ce9c97d^:docs/product/stories/US-15.1-drawdown-decomposition-engine.md"
```

Match their register. A story that reads differently from its neighbours makes
the whole product-docs set harder to trust.

## Status values

`backlog` → `active` → `done`, plus `dropped` for work decided against. Those
four words are the enum `scripts/build_roadmap.py` enforces, lower-case, in the
frontmatter `status:` field — a fifth word fails `run_all_tests.py`.

You write `backlog`, or `active` if the work order says the human has pulled it
into delivery. **Never `done`** — that is the docs lane's to write at close-out,
from the diff, together with the `closed:` date it requires. A story that
arrives already marked `done` is a finding, and the docs lane reports it as one.

The older `Next phase` / `In progress` / `Active` labels are gone: they were
free text, and `Active` in particular was an epic-level word that a story could
silently contradict. There is no separate epic status to contradict now.

## Guardrails as they show up in acceptance criteria

The five guardrails hold whether or not you write them down. Do not restate them
as ACs. Do write an AC when this story creates a *specific new way* to violate
one — that is the case worth checking:

- A new field that can be missing → an AC stating what the user sees when it is
  (a dash, a badge, a named disclosure — never zero, never a placeholder).
- A new aggregate over values that can be missing → an AC stating that the
  missing share is disclosed rather than apportioned across the others.
- A new number derived from synthetic history → an AC stating the trust level it
  claims, so the reviewer can check it does not overstate its basis.
- A change to a withheld field → this needs the owner's decision, not an AC.
  Report `BLOCKED`.

## Sizing

If the draft runs past roughly a dozen acceptance criteria, or the tickets span
schema *and* a new UI interaction model, say so in `risks` and propose the split
— typically the backend contract as one story and the UI surface as another.

Do not split it yourself: whether to split is a producer decision, and you would
be creating a second story nobody scoped. Flag and let the human choose.

The producer's `invest:` line often names Estimable as the weak criterion. If it
did, that is a signal the story wants a design decision before ticketing, not a
longer AC list.

## Common failure modes here

**Answering the producer's open decision.** The single most damaging one. If the
brief says "your call", the story says "open, blocks ticketing".

**Specifying the schema.** Tempting because the research brief often gives you
enough to do it. That inventory is a *constraint for the tech lead*, cited as
such — not a set of field definitions to promote into ACs.

**Writing roadmap entries.** The skill tells you to. Don't.

**Ticket 5 tells someone to commit.** The repo's older stories sometimes end
with a close-out ticket that self-invokes `verify-story` and commits. Do not
reproduce that pattern — the gates are dispatched by the orchestrator, and the
human commits.

**Predicting test counts.** "+8 backend, +7 frontend" reads precise and invites
the test lane to hit a number instead of covering the behaviour.

## Definition of done for this lane

- [ ] Producer brief read in full; quant research brief read where one exists
- [ ] Nearest sibling stories read for register and structure
- [ ] Every producer open decision reproduced in `## Open decisions`, unresolved
- [ ] ACs state observable behaviour; none specifies a field name, type or function signature
- [ ] Absent and degraded cases have their own ACs
- [ ] Research-brief constraints carried forward and cited, not restated as schema
- [ ] Test plan names files and behaviours; no function names, no counts
- [ ] Tickets ordered, lane-sized, tracing to ACs; **none instructs a commit or a self-gate**
- [ ] `status:` is `backlog` or `active` - never `done`
- [ ] `ROADMAP.md`, `current-product-state.md` and any epic file untouched
- [ ] Report says plainly that this is a draft for human review
