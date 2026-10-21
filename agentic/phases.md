<!-- Profile extension: ORCHESTRATOR only, read at intake.
     Split out of project.md — every build lane was reading it for nothing.
     `check_report.py` reads the `verify` rows here; see `## Phases` below. -->

# Project phases: `portfolio`

The phase→lane binding for this project. Read this at intake, alongside
`project.md`. No specialist lane needs it.

## Contents

- **Phases** — the binding table: which lane fills each phase, in what order,
  and the clause that decides whether it fires. Copied into the run ledger.
- **Four orderings that are not negotiable** — dependencies between phases that
  a plan may not reorder.
- **When the brief is the specification** — why the `story` trigger is narrower
  than `framing`'s, and what still fires it.
- **What the gates run** — the command each `verify` row owes.
- **The short run** — what a run looks like when `framing`, `specification` and
  `design` all fail their triggers.

## Phases

`protocol/orchestrator.md` § 2 defines the phases and § 3 the loop that walks
them. This table is the binding: which lane fills each phase **here**, in what
order, and the clause that decides whether it fires at all. The orchestrator
copies it into the run ledger at intake and records a verdict beside every row.

| Phase | # | Lane | Fires when | Human stop |
|---|---|---|---|---|
| ground-truth | 1 | recon | the area is unfamiliar, or the run would otherwise build on an unverified claim — a bug report, a findings doc, a "this number looks wrong" | — |
| framing | 1 | product | the request changes what the product does: a new capability, new scope, or a re-prioritisation | **yes** — the brief is relayed and the verdict is the human's |
| specification | 1 | quant (RESEARCH) | the work introduces or changes a metric, formula, weighting, return basis or trust classification | — |
| specification | 2 | story | framing produced scope that no approved, ticketed story covers, **and** the slice needs ticketing — more than one build lane, a contract crossing, or mathematics | **yes** — the one hard stop |
| design | 1 | design | the change crosses a contract boundary, or more than one build lane touches it | — |
| build | 1..n | backend, frontend, test | anything that edits the repo. One order per lane: contracts before consumers, implementation before tests | — |
| verify | 1 | quant-audit | any lane touched `analytics/`, a formula, a weighting, a return basis or a trust label | — |
| verify | 2 | integration | any build lane was dispatched | — |
| verify | 3 | review | the run carries a story whose acceptance criteria someone must accept | — |
| close | 1 | docs | always — contract notes against `docs/`, and `pack-corrections.md` against `capabilities/` **when a lane emitted one** | — |

### Four orderings that are not negotiable

**`ground-truth` before `framing`.** When both fire, recon's artifact is an
`inputs` on the producer's order. Run the other way round, the producer
establishes the facts itself and recon re-derives them — two dispatches over the
same territory, and nothing reconciles them. A producer's "already covered"
then rests on claims it opened itself, and a later scout can contradict it with
no mechanism that notices.

**`quant` RESEARCH before `story`.** The research brief is what makes acceptance
criteria groundable. Written the other way round, the story states an outcome
nobody has established is computable, and the contradiction surfaces during
implementation — when three lanes have already built toward it.

**`quant-audit` before `integration`.** A wrong formula can be engineered
flawlessly and satisfy every acceptance criterion, so the other two gates would
both pass it. If the mathematics is wrong, the rest of the review is measuring
the wrong thing. Read its `verification.detail` for **which anchor it checked
against**: an audit that recomputed from the same methodology doc the
implementation was built from is a consistency check, not an independent one.

**`review` last.** It judges the story, not the code, and only once engineering
coherence has passed — so a `FAIL` there is about acceptance rather than
something `integration` would have caught anyway.

### When the brief is the specification

The `story` row's trigger is narrower than `framing`'s on purpose. A slice that
is one build lane, crosses no contract and touches no mathematics does not need
a ticketed story: the delivery brief already states the outcome, the slice
boundary and what is out of scope, and the human approved it at the framing
stop. Record the row as `not triggered (single-lane slice; the delivery brief in
<nn> is the specification)`, and `review` does not fire either — its own clause
asks for a story to accept, and there is none.

The failure it prevents: a story of 28 lines and two tickets, carrying no
contract notes, restating a brief the human had already approved. It was not
wrong. It was a dispatch and a human stop spent re-stating a decision already
made, and the `review` gate that followed judged acceptance criteria written
from that restatement.

**What still fires it, however small the change looks:** anything under
`schemas/`, anything under `analytics/`, anything that adds or removes a field
in `docs/contracts/<area>-fields.md`, and anything two build lanes touch. Those
are the cases where "what does done mean" is a question the brief did not
answer.

### What the gates run

**`integration` runs `python scripts/run_all_tests.py`.** Not the subset the
run happened to touch — the whole suite, every time, whatever the lanes changed.
Write that command into the gate's order, and nothing narrower.

Two reasons, and the second is the one that bites. It is this project's declared
acceptance command, so a gate running something smaller is gating against a
weaker standard than the repo itself applies. And it is the only command that
writes `.claude/.last-test-pass`, which the commit hook checks against every
changed file — so a run whose gate ran `vitest` + `tsc` + `detect_deadcode.py`
ends with three green results, a `PASS` verdict, and work the human cannot
commit until they run the suite themselves.

A build lane's own `verification` is properly narrower: it is checking its own
change, not the run. The gate is where the project's standard applies.

**`quant-audit` runs whatever recomputes the number independently** — named in
its order, and its `verification.detail` says which anchor it checked against.
**`review`** verifies the story's test plan actually ran; the suite is the
evidence, not the claim.

### The short run — what used to be the express route

There is no express route and none is needed: a run where `framing`,
`specification` and `design` all fail their triggers **is** the short run. What
matters is that each false clause is written into the ledger with its reason.

**What makes them false here.** A failing or flaky test (`test` lane). A doc
reconciliation a gate or a contract note already identified (`docs` lane). A
rename or a dead-code removal that `detect_deadcode.py` flags. A defect in
shipped behaviour whose fix sits inside one lane and changes no schema.

**What makes them true, no matter how small it looks.** Anything under
`services/quant-engine/app/schemas/` — that is the contract source of truth, and
the schema hook exists because changes there never stay in one lane, so `design`
fires. Anything under `analytics/` — the quant rows in `specification` and
`verify` both fire, always; mathematics never takes the short route, and that is
guardrail one made operational. Anything that adds or removes a field visible in
`docs/contracts/<area>-fields.md`. Anything a user would describe as a new
capability — `framing` fires and the verdict is the producer's.

**A false clause is re-read every turn, which is what replaces the old
self-voiding rule.** When a build lane returns a contract note, `design`'s
clause has stopped being false: that is a re-plan (`orchestrator.md` § 3), with
a `## Replans` row and a bumped `plan:`, not a route quietly discovering it was
the wrong one.

The short run ends the same way as the long one: `python scripts/run_all_tests.py`,
green, then the human commits. Skipping phases never skips verification.

