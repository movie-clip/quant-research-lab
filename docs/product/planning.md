# How planning docs work

One page. It defines where a unit of work is recorded, where its status lives,
and what is generated rather than written.

## The three artifacts

| Artifact | Hand-written? | Lifetime | Who writes it |
|---|---|---|---|
| `stories/US-<n>.<m>-<slug>.md` | yes | written once, status flipped once | story author; docs lane at close-out |
| `epics/EP-<n>-<slug>.md` | yes, **optional** | written once at open, closed once | human, when an epic is worth naming |
| `ROADMAP.md` | **no — generated** | recomputed on demand | `scripts/build_roadmap.py` |

A story is the unit of delivery: statement, acceptance criteria, test plan,
tickets. It is complete on its own and is the only product-doc record of its
slice.

An epic is **optional grouping, not a required parent.** Create one only when
two or more stories share a rationale a reader would otherwise have to infer.
A story that stands alone omits the `epic:` field; that is the normal case, not
a gap. Do not open an epic file so that a story has somewhere to point.

## Status lives in the file, never in an index

Every story and epic opens with a frontmatter block:

```markdown
---
id: US-45.1
title: Collapse/expand the Dashboard Risk Summary card
status: done
epic: EP-45          # omit entirely when the story stands alone
opened: 2026-09-11
closed: 2026-09-11
---
```

- `id` must match the filename (`US-45.1-<slug>.md`).
- `status` is one of `backlog` (defined, not ticketed), `active`
  (ticketed, being delivered), `done`, or `dropped` (decided against —
  the file stays so the decision is findable).
- `closed` is required once `status: done`.
- `epic`, if present, must be `EP-<n>` and must have a file under `epics/`.

Changing a story's status means editing that one line, in the file you already
have open. There is no second place to update, so there is no second place to
forget.

## The roadmap is derived

```bash
python scripts/build_roadmap.py           # regenerate docs/product/ROADMAP.md
python scripts/build_roadmap.py --check   # what run_all_tests.py runs
```

`run_all_tests.py` fails on a stale or malformed `ROADMAP.md`, so the index
cannot drift from the files it summarises. Never edit `ROADMAP.md` by hand —
the next regeneration discards the edit.

### Why it is built this way

The previous `docs/product/epic-roadmap.md` was a hand-maintained living
snapshot. It reached 2,090 lines before being deleted at commit `ce9c97d`, and
about nine tenths of it was completed-epic prose. That was not a discipline
failure; it was two design properties:

- It mixed **what is active** (changes every slice), **why a thing exists**
  (written once) and **what shipped** (append-only forever) in one file, so the
  99% that never changes had to be scrolled past to reach the 1% that does.
- It restated facts the story files already carried, so every slice wrote both
  copies and the two drifted whenever one was skipped.

Splitting by lifetime fixes the first; generating the index fixes the second.
Shipped work costs **one row**, and its narrative stays in the story file and
in Git — the same rule `docs/tech-debt-register.md` already states for itself:
exclude completed work and rely on Git history rather than retaining a
completion narrative.

## What does not go here

- **Deferred engineering work** → `docs/tech-debt-register.md`. A tech-debt
  item is not a backlog story and does not get a story file until it is
  scheduled.
- **What is shipped today** → `docs/product/current-product-state.md`. That is
  an inventory of the product as it stands, not a record of slices.
- **Formulas, contracts, architecture** → `docs/finance/`, `docs/contracts/`,
  `docs/architecture/`. A story cites them; it does not restate them.
