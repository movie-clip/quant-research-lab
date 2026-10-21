# Capability pack: product — project `portfolio`

For the `producer` lane. How this project's roadmap, epics and stories actually
work.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Where the plan lives** · **Guardrails you must respect when briefing** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| Story lifecycle | you are placing work against existing stories |
| The house pattern: findings-first epics | the request is a review, an audit or a findings fold-in |
| Epics get created mid-flight | nothing on the roadmap fits the request |
| What is a story here, and what is not | you are deciding whether this is one story or several |
| Where findings live | the request cites a findings document |
| Epic inflation | you are about to propose a new epic |
| Sequencing conventions | your brief orders more than one story |

---

## Where the plan lives

Read `docs/product/planning.md` first. It is the one hand-written page that
states this model, and it is short.

| Doc | Role |
|---|---|
| `docs/product/stories/US-<n>.<m>-<slug>.md` | one file per story — statement, ACs, test plan, tickets. The sole product-doc record of its slice. |
| `docs/product/epics/EP-<n>-<slug>.md` | **optional** grouping, one per epic — problem, goals, non-goals, findings |
| `docs/product/ROADMAP.md` | **generated** index of every story by status. Never hand-edited. |
| `docs/product/current-product-state.md` | canonical shipped-state inventory |
| `docs/tech-debt-register.md` | deferred improvements, not stories |

The earlier `epic-roadmap.md` / `prd/**` / `stories/README.md` corpus was
deleted and is not coming back in that shape: the roadmap was
hand-maintained, reached 2,090 lines, and about nine tenths of it was
completed-epic prose. `ROADMAP.md` replaces it by being
*derived* from story frontmatter rather than written, so it cannot go stale and
shipped work costs one row. Do not propose recreating the old corpus.

### An epic is optional, and that is the default

A story omits `epic:` unless two or more stories share a rationale a reader
would otherwise have to infer. **Do not propose an epic so that a story has a
parent.** Epic inflation used to be invisible because a roadmap row made a new
epic feel free; it is not free — each one is a file someone must open, close
and keep true.

Where you do propose one, say in your brief's `## Placement` which existing
story or epic it is a sibling of. A grouping with no stated precedent is
usually inflation, and naming the sibling is the cheapest check against that.

### Finding precedent

```bash
cat docs/product/ROADMAP.md          # every story, by status, one row each
ls docs/product/epics/               # groupings that exist, if any
```

`ROADMAP.md` is the index the old `grep '^## .*Epic '` used to substitute for.
Read it, shortlist one or two siblings by title, then open those story files —
not the whole directory.

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

## Story lifecycle

Four states, and they are the enum `scripts/build_roadmap.py` enforces — not
labels. A fifth word fails the suite.

| `status:` | Meaning |
|---|---|
| `backlog` | Defined: statement + ACs + rough test plan. Not ticketed. |
| `active` | Ticketed and being delivered. |
| `done` | Every AC met, full test plan passing, docs updated. Requires `closed:`. |
| `dropped` | Decided against. Stays as a file so the decision is findable. |

Naming: `US-<n>.<m>-<slug>.md`. Tickets: `T-<n>.<m>.<k>`. The `<n>` is a series
number, not a required epic: `US-45.1` does not imply an `EP-45` exists.

Only a **ticketed** story can be dispatched. A `backlog` story needs a ticketing
pass first.

## The house pattern: findings-first epics

This is the most important convention in the project, and it is unusual enough
that you must apply it deliberately rather than defaulting to a normal feature
epic.

**When an epic addresses something suspected wrong with shipped behaviour, its
first story is an audit.** `US-<n>.1` is audit-only: it investigates, records
findings as `F-1`, `F-2`, … in the epic file where one exists and in the audit
story itself where it does not, and ships no behaviour change. Each
subsequent story closes one or more findings and names them in its scope line.

Epics 33 and 34 both work this way. It exists because scoping a fix before the
cause is named produces stories that get rewritten mid-flight — and in a system
whose whole premise is that every number is traceable, "we think it's wrong"
is not a scope.

Two things follow that matter for your briefs:

**The audit records what is correct too.** Each audit story carries an
"examined-and-correct" list. That is what makes the finding list trustworthy
rather than just a list of the first three things someone noticed.

**Findings may be closed as "will not fix", with the reason recorded.** Epic 34
left F-1a, part of F-10, and F-12 open deliberately — structurally unreachable,
or bounded and immaterial. When a request touches one of these, surface the
recorded reason and ask whether it has changed. Do not quietly reopen a decision
someone already made with more context than you have.

## Epics get created mid-flight

Epic 35 was created from a hazard hit during US-34.9's work. This is normal and
healthy here: implementation surfaces real problems, and the honest response is
a new epic rather than scope-creeping the current story.

So when an implementation lane reports a finding outside its scope, that is a
producer input, not noise. Brief it: a new standalone story, a story joined to
an existing epic, a new epic where two or more stories will share the rationale,
or a debt-register entry.

Note also that epic creation **corrects the framing**, it does not just copy the
complaint. Epic 35's own description records that the original framing was
partly wrong and states the corrected version. A brief that simply restates the
reporter's words has skipped the producer's actual work.

## What is a story here, and what is not

**A story is a vertical slice of user value.** Read a few existing story
statements before writing a brief — they are phrased as what the researcher can
now see or trust, not as what the code now does.

Not stories:

- **Refactors and cleanups** → `docs/tech-debt-register.md`.
- **Pure technical enablement** with no user-visible change. If it is genuinely
  needed, it is a ticket inside a story that delivers something.
- **A bug with no diagnosis** → route to investigation. In this project that
  usually means an audit story, not a fix story.

## Guardrails you must respect when briefing

The product's five guardrails are in the project profile. Two shape scope
decisions specifically:

- **No execution.** The system never places trades or moves money. A request in
  that direction is declined, not deferred.
- **Trust semantics over fabrication.** A request to "just show a number" where
  the system currently withholds is a request to weaken a guardrail. It may
  still be legitimate — US-34.2 published a replay-derived TWR under a *new,
  explicitly labelled* trust rung rather than pretending it was verified. But
  the brief must name it as a trust-model change, because that is what it is,
  and it needs the owner's decision.

## Where findings live

Findings from an audit or health review belong as `F-1`, `F-2`, … **in the epic
file when the work is grouped into one, and in the audit story itself when it is
not** — that is the findings-first pattern above, and it is what makes them
discoverable to later stories and to your own "already covered" check.

Do not accept a standalone findings file with its own numbering scheme as the
record. If one exists (a review was run outside this structure), your job is to
fold its findings into whichever of the two homes applies, deduplicating against
what is already recorded in the tech-debt register and in prior open findings.

A finding that duplicates a known-open item is not a new finding — say so, and
point at the existing record.

## Epic inflation

A one-story epic needs a reason beyond "this request needs somewhere to live",
and under the current model it usually has none: `epic:` is optional, so a story
with no grouping is already well-formed. Epic 16 justified itself as a *quick
win* — small, self-contained, no open design questions. If the story you are
proposing is small-to-medium with an unresolved design decision, that precedent
does not apply, and `status: backlog` with no epic is the more honest verdict.

When you do propose a new epic, say who decides. Epic placement is the owner's
call, and a brief that presents a new epic as settled removes them from it.

## Sequencing conventions

- **Recommended order is stated explicitly** in your brief, and in the epic
  file where one exists. `ROADMAP.md` is generated and carries no ordering, so
  if you do not state the order nothing else will.
- **Risk-first.** Put the story that could invalidate the others first.
  US-34.2 was first in its epic and immediately surfaced three hidden defects
  that reshaped the rest.
- **A story that surfaces a finding may spawn its own successor.** Expect this
  and say so in the brief rather than presenting a plan as fixed.

## Definition of done for this lane

- [ ] `ROADMAP.md`, the nearest sibling stories, any open epic file and the
      shipped-state inventory all actually read
- [ ] Checked whether the request is already shipped, already storied, or deliberately open
- [ ] Verdict stated plainly, including "already covered", "defer to Backlog" or "decline" when true
- [ ] Value claim checked against real project data where the repo contains it, not asserted
- [ ] Mathematical uncertainty routed to quant research, not deferred to the tech lead
- [ ] Proposed stories are vertical slices with a one-sentence user-visible outcome
- [ ] Audit-first applied where the cause is not yet named
- [ ] Dependencies named with the reason for each edge
- [ ] Any prior recorded decision the brief would reverse is surfaced, not overridden
- [ ] Open decisions for the human listed explicitly
- [ ] No story files written, no implementation specified
- [ ] **Every claim about the code cited from a `recon` artifact named in your
      `inputs`, or marked as unverified in `risks`** — you read the *plan*:
      roadmap, stories, epics, the shipped-state inventory. Reading source files
      to establish what the code does is the `recon` lane's dispatch, and when
      you do it anyway the network runs it again and the two answers can
      disagree. If the fact you need is not in an input, say which fact and let
      the orchestrator dispatch for it.
