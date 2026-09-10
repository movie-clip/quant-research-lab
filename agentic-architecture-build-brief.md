# Build brief: an orchestrated agent network (`.agentic`)

> A portable specification of the `.agentic` architecture, written as a build prompt.
> Hand it to an agent and it can reconstruct the same system for any repository.
> Project-specific content (the quant/portfolio domain) is abstracted into
> "you fill this in per project" slots.

---

## 1. What you are building and why

A **multi-agent delivery network** that turns a plain-English request ("add X",
"fix Y", "is Z correct", "what should we work on next") into an ordered set of
isolated specialist subagent runs, with review gates, a durable on-disk ledger,
and cost accounting.

It exists to fix two failures of a single-context "do everything in one skill"
pipeline:

- **Context dilution** — one agent carrying the whole project (backend
  conventions + UI system + test fixtures + doc contracts) spends attention on
  all of it even for a 3-file change.
- **No isolation** — a wrong turn in one slice (say the UI part) pollutes the
  reasoning of another (the backend part) because they share a transcript.

The governing principle: **separate who decides from who does.** A
planning/dispatching orchestrator runs in the main session; every unit of real
work runs in its own subagent context with its own tools and its own project
knowledge. The orchestrator only ever sees short structured summaries.

## 2. The three-layer split (the heart of the design)

| Layer | Lives in | Contains | Must NOT contain | Changes |
|---|---|---|---|---|
| **Protocol** | `PROTOCOL.md` + `protocol/*.md` | message shapes, binding procedure, gate rules, ledger schema | anything about a specific repo; anything about a specific role's craft | rarely |
| **Roles** | `plugins/agentic-core/agents/<name>.md` | what a lane judges, its tool discipline, its output obligations | any path, framework, or convention from a specific repo | ~never (project-agnostic) |
| **Capability packs** | `projects/<project>/capabilities/<lane>.md` | paths, frameworks, fixtures, commands, gotchas, reuse inventories, external anchors | message shapes, role definitions | every time the repo evolves |

Rule of thumb: if you're about to write `pytest` (or any tool/path/framework
name) into an agent file, it belongs in a capability pack instead. If you're
about to paste a message shape into a pack or an agent file, it belongs only in
the protocol — point at it, don't copy it.

**Why the split matters:** `.agentic` lives *one directory above* the repos it
drives. Binding a second repo means adding only a new `projects/<name>/` folder;
the `plugins/` layer is untouched. That is the whole payoff.

## 3. Directory layout

```
.agentic/
├─ ARCHITECTURE.md              ← design rationale + provenance (HUMAN-facing; agents never read it)
├─ PROTOCOL.md                  ← THE core contract. Every agent reads this in full, every dispatch.
├─ protocol/                    ← role-scoped extensions. Each agent reads exactly ONE (or none).
│  ├─ orchestrator.md           ← ledger schema · relay rule · reading discipline
│  ├─ gates.md                  ← verdict semantics · gate independence · change-request shape
│  ├─ packs.md                  ← how the docs lane applies pack_corrections at close-out
│  └─ authoring.md              ← rules for writing agents/packs/protocol (read only when authoring)
├─ runs/<YYYY-MM-DD>-<slug>/    ← one directory per run = a slice's state on disk
│  ├─ run.md                    ← the ledger
│  ├─ NN-<lane>.md              ← each specialist's full report artifact, numbered in dispatch order
│  ├─ NN-head.txt              ← the head each specialist returned (saved by orchestrator)
│  ├─ cr/CR-<n>.md              ← change requests, one file each
│  └─ pack-corrections.md       ← appended as corrections arrive; the docs lane's close-out input
├─ scripts/
│  ├─ check_report.py           ← validates a report artifact + can derive its head (--emit-head)
│  ├─ test_check_report.py      ← pins the validator's own behaviour
│  ├─ run_cost.py               ← re-derives a run's cost tally from its ledger rows
│  └─ test_run_cost.py
├─ .claude-plugin/marketplace.json   ← makes this dir a local Claude Code plugin marketplace
├─ plugins/agentic-core/             ← PROJECT-AGNOSTIC layer
│  ├─ .claude-plugin/plugin.json     ← name + version (orchestrator announces this version)
│  ├─ commands/feature.md            ← the /agentic-core:feature slash command (safety-net wrapper)
│  ├─ skills/
│  │  ├─ orchestrate-feature/SKILL.md  ← the router; runs in the main session
│  │  └─ agentic-protocol/SKILL.md     ← a stub that only points at PROTOCOL.md + the extension table
│  └─ agents/
│     ├─ producer.md          scout.md            story-author.md
│     ├─ tech-lead.md         quant-analyst.md    (domain gate — rename/retheme per project)
│     ├─ backend-engineer.md  frontend-engineer.md
│     ├─ test-engineer.md     docs-engineer.md    reviewer.md
│     └─ protocol-linter.md
├─ projects/<project>/               ← PROJECT-SPECIFIC layer (one folder per bound repo)
│  ├─ project.md                     ← the binding profile (guardrails, stack, layout, lane routing)
│  └─ capabilities/
│     ├─ product.md   architecture.md   backend.md   frontend.md
│     ├─ testing.md   docs.md           story.md     <domain>.md
└─ _repo-patch/.agentic.json          ← copy this one file into each bound repo's root
```

## 4. Binding: how any agent finds its context

The bound repo contains exactly one file at its root:

```json
// <repo>/.agentic.json
{ "agenticRoot": "../.agentic", "project": "<project-name>" }
```

**Every agent's first action, before reading any source file:**

1. Find `.agentic.json` by walking **up** from the current working directory (a
   session may start in a subdirectory — do not assume cwd is the repo root). No
   `.agentic.json` found before a filesystem root → stop and report `BLOCKED`.
   Never guess the layout.
2. Resolve `agenticRoot` **relative to the directory containing `.agentic.json`**,
   not relative to cwd. Record it once as an absolute path; build every later
   path by appending to that string (repeated relative-path arithmetic silently
   produces `C:\projects\investments.agentic\...` — one separator wrong).
3. Read `<agenticRoot>/PROTOCOL.md` in full.
4. Read your one protocol extension from the table (orchestrator →
   `orchestrator.md`; the three gate lanes → `gates.md`; docs lane on a
   close-out order → `packs.md`; everyone else → nothing).
5. Read `<agenticRoot>/projects/<project>/project.md` — **the `## Index` block
   first**, then the sections it marks always-read, then any section your order
   touches.
6. Read `<agenticRoot>/projects/<project>/capabilities/<your-lane>.md` the same
   way.
7. Only then start work.

Nothing else in the network hardcodes a path.

## 5. The roster

Ten specialist roles (plus the orchestrator, which is the main session, not a
subagent). Each agent file is frontmatter (`name`, `description`, `tools`,
`model`, `effort`) followed by: a one-line identity statement, a "Bind first"
block, working rules, and a "Required output format" tail that **points at
`PROTOCOL.md` §3/§4 rather than restating them**.

| Agent | Model / effort | Tools (beyond Read/Glob/Grep) | Job |
|---|---|---|---|
| **producer** | sonnet / high | Write (run-dir only), Bash | **The front door.** Owns the roadmap: does this already exist, does it fit the active epic, is it a new epic, should it be declined. Shapes requests into vertical slices, sequences them, names dependencies. Where "no" lives. |
| **scout** | sonnet / medium | Write (run-dir only) | Read-only recon. "Where does X live, what already exists, what will this touch" — compressed to the ~200 words that matter. Proposes nothing. |
| **story-author** | sonnet / medium | Write (run-dir only) | Drafts a ticketed story (statement → acceptance criteria → test plan → tickets) from the producer's brief. Decides nothing — not epic placement, not the contract. Human approves the draft. |
| **tech-lead** | sonnet / high | Write (run-dir only), Bash, + project test/gate tools | Two modes. **DESIGN**: settles the contract, the reuse map, the lane split before any engineer starts. **INTEGRATION**: the engineering gate — checks contract alignment across lanes, returns `PASS` or `CHANGES_REQUESTED` with per-lane change requests. Never writes production code. |
| **_domain_-analyst** (here `quant-analyst`) | **opus** / medium | Write (run-dir only), Bash, + probe tools | Owns the project's #1 correctness guardrail. **RESEARCH**: establishes formulas/definitions/edge-cases *before* the story is written. **AUDIT**: independently *recomputes* published numbers against an external anchor, checks any trust/validity labels. Opus because nothing downstream catches a wrong formula. Rename/retheme this lane to whatever your project's irreducible-correctness domain is; drop it if the project has none. |
| **backend-engineer** | sonnet / high | Read/Write/Edit/Bash, + project tools | Server-side implementation: schemas → service → route → registration. **Owns the contract source of truth** — any response-shape change starts here and emits `contract_notes`. |
| **frontend-engineer** | sonnet / high | Read/Write/Edit/Bash, + project tools | Client-side implementation: typed API adapters mirroring server schemas exactly, components built on the design-system primitives. Consumes the backend lane's contract notes. |
| **test-engineer** | sonnet / medium | Read/Write/Edit/Bash, + project tools | The only lane that edits test files. Owns fixtures, mocks, golden artifacts, runner commands, assertion-brittleness discipline. |
| **docs-engineer** | sonnet / medium | Read/Write | Reconciles docs with what shipped — contract/field tables, methodology phrasing, shipped-state inventory, slice log. At close-out only, also applies `pack_corrections` back into the capability packs (the one time a lane writes inside `.agentic` outside the run dir). |
| **reviewer** | sonnet / high | Read/Bash, + project test/gate tools (nothing mutating) | The acceptance gate. Walks the story's acceptance criteria one by one, verifies the test plan was actually delivered, spot-checks trust-state rendering. `PASS` / `FAIL`. Never fixes what it finds. |
| **protocol-linter** | **opus** / medium | Read/Write (run-dir only), Bash | The authoring gate. When a work order creates/edits a network file (an agent def, a pack, a protocol section), checks it against `authoring.md` — layer separation, model/effort declared, index correctness, bullet discipline, no pack instructing a tool its lane lacks. `PASS` / `FAIL`, read-only over what it judges. |

**Tool-grant discipline:** every agent holds `Write` for exactly one purpose —
its own report artifact in the run dir. Read-only/gate/planning lanes hold **no
`Edit` tool** (that is the real bound). A subagent's tool list also loads into
its context every dispatch, so grant narrowly: the reviewer gets nothing that
can mutate the tree it verifies.

## 6. Model & effort policy

Two independent frontmatter dials. Pin **both** explicitly on every agent —
never `inherit` (it silently bills every dispatch at the main session's tier and
nothing records it), never `fable`.

**Model — Sonnet is the ceiling; Opus is the exception.** The test, stated not
listed:

> Would a wrong answer from this lane be caught by anything downstream — a test,
> a gate, a validator, or the human approval step? **If yes → Sonnet. If no →
> Opus.**

Second term is frequency: highest-consequence × lowest-frequency earns Opus.
Only two lanes qualify: the domain-analyst (a wrong formula is engineered
perfectly, passes every other gate) and the protocol-linter (a wrongly-passed
agent file bills wrong forever, surfacing only as "the run cost too much"). Both
are also the rarest lanes.

**Effort — `medium` is the baseline; `high` for the five lanes that *decide*
something:** producer, tech-lead, reviewer, backend-engineer, frontend-engineer.
Everything else (drafting, applying, testing, retrieval — all working against
something another lane already fixed) runs `medium`. The two Opus lanes sit at
`medium` effort deliberately: the tier buys their judgment, not the dial. `low`
and `max` are defaults nowhere. Note: Claude Code's implicit effort default is
`xhigh` (second-highest of five), so an agent with no `effort:` line is running
near the top of the range.

**Escalation is evidence-driven.** Frontmatter is a default, not a ceiling. The
orchestrator may raise one dispatch to Opus (or `max`) when the run has produced
evidence the lane is out of its depth: a `BLOCKED` that isn't a missing input,
or a finding reaching its **second** change-request round. Record it in the
ledger as `opus↑` / `sonnet/max↑` with a reason. Never escalate pre-emptively.

## 7. Protocol shapes

These four shapes are defined **once**, in `PROTOCOL.md`, and pointed at from
everywhere else.

### Shape 1 — the work order (what a lane receives)

```
WORK ORDER <run-id>/<nn>
lane:        product | recon | story | design | backend | frontend | test | docs | <domain>-audit | integration | review | protocol-lint
mode:        <for the dual-mode lanes: DESIGN|INTEGRATION, or RESEARCH|AUDIT>
run_dir:     <agenticRoot>/runs/<run-id>
report_to:   <agenticRoot>/runs/<run-id>/<nn>-<lane>.md
story:       <path to story file, or NONE>
tickets:     <T-x.y.z, ... or NONE>

goal:        <one sentence, outcome not method>
scope:
  - <file / dir / glob this order may touch>      # a FENCE, not a hint. Outside it = stop and report.
inputs:
  - <path — a path, NEVER a quotation>            # the receiver opens the file and reads the specialist's own words
definition_of_done:
  - <checkable statement>
non_goals:
  - <thing an eager agent would do that it must not>   # binding; this is where the orchestrator spends its effort
verification:  <exact command(s) to run, or NONE if read-only>
```

### Shape 2 — the report artifact (what a lane writes to `report_to`)

```
REPORT <run-id>/<nn>
status:      DONE | PARTIAL | BLOCKED | REFUSED
verdict:     PASS | FAIL | CHANGES_REQUESTED | NONE    # gate lanes only; everyone else writes NONE
changed:
  - <path> — <what changed, one line>                  # empty section = a BARE "- none"
verification:
  command:   <what you ran>
  result:    PASS | FAIL | NOT_RUN
  detail:    <failure summary, or the counts on pass — e.g. "802 passed, 4 skipped">
contract_notes:
  - <any schema / type / doc that now needs a matching change elsewhere>
pack_corrections:
  - <pack file> — <the false premise, and the exact replacement wording>
handoff:
  - <what the next lane needs: fixture names, prop shapes, route paths>
risks:
  - <anything you were unsure about, or a guardrail you had to interpret>
```

**The three result fields are not the same thing:**
- `status` — did this **order** run to completion? (every lane)
- `verdict` — the **judgment** this lane was asked for (gate lanes only)
- `verification.result` — what the **command** printed (every lane that ran one)

A gate that reviewed and found problems is `status: DONE` + `verdict: FAIL` /
`CHANGES_REQUESTED` — **not** `PARTIAL`. `status: DONE` requires
`verification.result: PASS` unless the order's `verification` was `NONE`.

**Bullet discipline:** one fact per bullet (the orchestrator routes bullets
individually). Targets/ceilings by lane:

| lane | target | ceiling |
|---|---|---|
| gate lanes (integration, review, `<domain>`-audit, protocol-lint) | 200 | **400, enforced** |
| recon, `<domain>` RESEARCH (carry `file:line` citations) | 400 | 600, advisory |
| everything else | 200 | 400, advisory |

A bullet needing a paragraph is several bullets, or it points at a named section
below the block with `see § <section name>` — and adding a section obliges the
artifact to carry a `## Orchestrator brief`.

### Shape 2H — the report head (what a lane *returns* as its final message)

The lane's final message is **not** the report — it's a fixed-size head whose
job is to tell the orchestrator whether to open the artifact and which part:

```
REPORT HEAD <run-id>/<nn>
artifact:    <the absolute report_to path>
status:      DONE | PARTIAL | BLOCKED | REFUSED
verdict:     PASS | FAIL | CHANGES_REQUESTED | NONE
verification: PASS | FAIL | NOT_RUN
detail:      <verification.detail, verbatim, first 200 chars>
changed:     <integer — count of `changed` bullets>
contract_notes: <integer>
pack_corrections: <integer>
handoff:     <integer>
risks:       <integer>
blocked_on:  <one line, only when status is BLOCKED/REFUSED>
headline:    <one sentence, <200 chars, outcome not method>
```

**Derive the head, never type it.** A head is a count of list items plus a
string sliced to an exact length — the two things a model cannot do reliably by
inspection. `scripts/check_report.py <path> --emit-head` produces it from the
artifact; the lane fills in only `headline` (and `blocked_on`). Lanes without
`Bash` (scout, docs-engineer, story-author) can't run it — the orchestrator
derives their head for them as a standing post-dispatch step, keeping only the
lane's `headline`.

**Why head-not-body:** the orchestrator's context is the scarcest resource in a
run and the one thing every dispatch spends. A body returned in full is paid for
twice (disk + coordinator window) and mostly never routed anywhere.

### Shape 3 — the change request (`tech-lead` INTEGRATION only)

Written to `<run_dir>/cr/CR-<n>.md`, one file each; the orchestrator relays each
as a fresh scope-fenced work order to the owning lane.

```
CHANGE REQUEST <n>
lane:     <owning lane>
severity: BLOCKING | SHOULD_FIX          # only BLOCKING holds the slice
round:    <1 | 2>                        # two rounds max on the same finding, then escalate to human
finding:  <what is wrong — file:line, specific>
why:      <the consequence, not the rule — "client renders null as 0", not "violates convention">
expected: <what would satisfy it>
```

The receiving engineer fixes **only** what it names — adjacent improvements are a
new order.

### Planning artifacts carry a `## Orchestrator brief`

`product`, `design`, `story`, and `<domain>` RESEARCH produce documents far
longer than the report block. Each **must** open with a `## Orchestrator brief`
— ≤15 lines, an *index with verdicts* (decisions taken, lane split, the named
sections below and what each contains). The orchestrator reads the brief and
only the sections it names; the rest reaches the lane that needs it as an
`inputs` path. `check_report.py` enforces the heading, the line cap, and that
the brief names every section below it.

## 8. The run ledger (`runs/<id>/run.md`)

A run's state lives **on disk, not in the orchestrator's memory** — the main
session compacts and restarts, and a slice that only exists in a transcript
cannot survive that.

```markdown
# RUN <run-id>
request:      <the user's original words, verbatim>
agentic_root: <the RESOLVED ABSOLUTE path>
story:        <path, or NONE>
status:       PLANNING | DISPATCHING | GATING | BLOCKED | CLOSED   # bare enum only
blocked_on:   <one line, only when status is BLOCKED>
next:         <the single next action a fresh session would take, rewritten every update>
route:        recon | express | audit | review | story | full
gates:        <each of <domain>-audit, integration, review — its verdict, or "skipped" + why>

## Artifacts
| # | lane | mode | agent | model | artifact | status | verdict |
...one row per dispatch. `model` = the model it ACTUALLY ran on. Write the row
   WHEN THE HEAD RETURNS, before reading the artifact or summarising anything.

## Open
| kind | from | ref | one-line (<120 chars) | state |    # contract_note / should_fix / partial; state OPEN|ABSORBED|CARRIED

## Closed
| kind | from | absorbed by | one-line |                  # rows move here when absorbed, dropping `state`

## Rounds
| finding | lane | round | of |                          # change-request round counter lives here, not in memory

## Cost
| metric | value |                                        # filled at close-out; mid-flight the unfilled cells are "—", not 0
  dispatches / rounds / by model (e.g. "sonnet 15 · opus 1") / escalations
```

`scripts/run_cost.py <run_dir>` re-derives dispatches/rounds/model-spread from
the rows and fails if the tally disagrees, a dispatch recorded no model, or the
`gates:` line omits a gate / claims one that never ran / states a verdict
disagreeing with its row.

## 9. The orchestrator (`orchestrate-feature` skill)

Runs in the main session. **Plans, dispatches, relays. Does not edit source
files. Does not issue a specialist's verdict in its own voice.**

**The failure mode this skill actually has is not a bad plan — it is a no-op:**
the orchestrator reads the request, it seems tractable, it does the work itself
in the main session and produces a good answer, with no ledger, no isolation, no
gate, no record. It looks like success; it is the architecture silently not
running. Three non-optional self-checks guard it:

1. Before your first `Edit`/`Write` to any file in the bound repo — **stop.**
   That edit belongs to a lane. The only files the orchestrator writes are
   `run.md` and `pack-corrections.md` in the run dir.
2. Before stating a conclusion, ask whose it is. "This is one epic, not three."
   "These are duplicates." "This doesn't need a story." Those are the
   **producer's** verdicts. Contract → tech-lead. Acceptance → reviewer. If
   you're about to say one, dispatch instead.
3. Report `dispatched: <n>` at close-out, always. Zero on anything but pure
   recon → disclose it explicitly, don't present it as a network result.

### Step 0 — Bind, announce, open the run

First line of output, always:
```
agentic-core v<version> · project <name> · route <recon|express|audit|review|story|full>
```
Version comes from `plugins/agentic-core/.claude-plugin/plugin.json`. If running
from an installed plugin cache rather than the working directory, say which —
they can differ by several versions and a stale copy produces plausible answers
to a question nobody asked. Then bind (§4), check `runs/` for an unfinished
`run.md` matching this request and resume from its Artifacts table if found,
else create the ledger with the request verbatim.

### Step 1 — Choose the route before spending it

| Route | When | Dispatches | Human stops |
|---|---|---|---|
| **Recon** | "where does X live", "how does Y work" | 1 (scout) | 0 |
| **Express** | one lane, no contract crossed, no domain math, no new user-visible scope, every file nameable up front | 1–2 | 1 (the suite) |
| **Audit** | "is this number/output right" | 1 (`<domain>`-analyst AUDIT) | 0–1 |
| **Review** | health review / findings fold-in | 2–4 | 1 |
| **Story pickup** | an approved ticketed story exists | 5–9 | 2 |
| **Full** | new user-visible scope | 8–12 | 4 |

State the route and its cost to the user in one line before dispatching. The
**express lane self-voids**: if the returned head has a non-zero
`contract_notes` count, or `status` isn't `DONE`, or the lane reports it had to
touch a second lane — mark `express: no` and escalate to the full flow. When in
doubt between express and producer, choose producer.

### Steps 2–10 — the full flow

2. **`<domain>` RESEARCH** (if the work introduces/changes a formula, weighting,
   definition, or validity classification) — dispatch *before* story authoring,
   so acceptance criteria are groundable. May run in parallel with `scout` (the
   only free concurrency in the flow).
3. **`story-author`** drafts the ticketed story → **hard stop, hand to human.**
   Acceptance criteria are the contract everything downstream is measured
   against. Every open decision the producer escalated must be resolved by the
   human first. Epic placement is always the human's call.
4. **`tech-lead` DESIGN** → technical plan (contract, reuse map, lane split,
   decisions engineers must not each make). Present the lane plan to the human.
5. **Present the plan and wait.** Show the lane list, one line of intent each,
   the agent count. A user correcting the plan costs one sentence; correcting
   six agents' output costs the session.
6. **Dispatch, one order at a time.** Default order: contracts before consumers,
   implementation before tests, everything before docs. After each returned
   head:
   - **Validate the artifact against its head, before reading either:**
     `check_report.py <artifact> --lane <lane> --head <saved-head.txt>`.
     Non-zero → send back with the script's output; do not route
     `contract_notes` out of a failed report. The `--head` half is not optional
     — it's the only defence against a head that undercounts and silently drops
     work.
   - Read `status` and `detail` honestly. `PARTIAL`/`BLOCKED` are information.
   - Open only the sections the counts point at
     (`sed -n '/^contract_notes:/,/^[a-z_]*:/p' <artifact>`). All-zero counts +
     a `detail` matching the order → record and move on, no read.
   - **Update `run.md`** (the Artifacts row incl. `model`, a typed `Open` row
     for anything unabsorbed) *before* dispatching the next order.
   - Route `contract_notes` forward as explicit `inputs` paths on downstream
     orders; keep each `OPEN` until a downstream order absorbs it. Append
     `pack_corrections` to `pack-corrections.md`. Route `handoff` forward.
   - `REFUSED` → surface it, never re-dispatch with softer wording.
7. **`<domain>` AUDIT** (if any lane touched the domain) — runs *first*, before
   the engineering gate. Read `verification.detail` for **which external anchor
   it checked against**; "recomputed from the methodology doc the implementation
   was built from" is a consistency check, not independent verification.
   `CRITICAL`/`MATERIAL` findings → change requests to the owning lane.
8. **`tech-lead` INTEGRATION** — the engineering gate. On `CHANGES_REQUESTED`:
   for each `BLOCKING` request, dispatch a fresh scope-fenced order to the
   owning lane (increment the round counter in `run.md` *before* dispatching),
   then re-run integration. Two rounds max per finding, then escalate to the
   human. `SHOULD_FIX` → `Open`, doesn't hold the slice.
9. **`reviewer`** — the acceptance gate, only after integration passes. On
   `FAIL`, re-dispatch to the owning lane with the failure artifact's path;
   never fix it yourself.
10. **Close out.** Dispatch the `docs` lane against (a) the contract notes vs
    the repo's docs, (b) `pack-corrections.md` vs `capabilities/` — the only
    order in which a lane writes inside `.agentic` outside the run dir. Then
    walk the ledger checklist: `gates:` accounts for all three; every `Open` row
    is `ABSORBED`/`CLOSED`/deliberately `CARRIED`; the docs order actually ran;
    `Cost` is filled and `run_cost.py` exits 0; `next:` says `none — CLOSED`.
    Report to the human: the banner with `dispatched: <n>`, what changed by
    lane, every gate verdict + which gates were skipped and why, anything still
    open, any producer finding raised, the exact command to run before
    committing.

**The orchestrator never commits.** The repo's mechanical gates (test runner,
pre-commit hook, CI) own that boundary.

### The relay rule (the one that degrades under pressure)

The orchestrator carries the producer's brief, the tech lead's plan, and every
change request between lanes, because subagents can't spawn subagents (fan-out
is one level deep). Carry them **as `inputs` paths, never as quoted/summarised
text** — under context pressure, summarising is exactly what a model does, and
then the specialist works from the orchestrator's paraphrase instead of the
specialist judgment that produced it. Every agent writes its own artifact; an
`inputs` line names a path (optionally with a `§ section` suffix). "Verbatim"
becomes a property of the filesystem. The only exception: `goal` and `non_goals`
are the orchestrator's own words.

## 10. The gates

Four gates, each checking something the others structurally cannot see:

| Gate | Judges | Fails on |
|---|---|---|
| `<domain>`-analyst AUDIT | the **mathematics/domain correctness** | a wrong formula, a mislabelled validity class, a number that doesn't reproduce |
| `tech-lead` INTEGRATION | the **engineering** | contracts misaligned across lanes, the design not followed |
| `reviewer` | **acceptance** | the story's criteria not satisfied |
| `protocol-linter` | the **network's own files** | an agent/pack/protocol section breaking `authoring.md` |

**Order matters and none subsumes another.** A wrong formula can be engineered
flawlessly, tested thoroughly, and satisfy every acceptance criterion — the
second and third gates both pass it, because neither is looking at the
arithmetic. So the domain gate runs first where analytics changed.

**A gate that reads only the source the work was built from is not a gate** — it
catches slips, not wrong premises, and that failure is invisible (every gate
passes, loudly and correctly, and the defect ships). Where a capability pack
names an **external anchor** (a reference implementation, a textbook definition,
hand-computed known values, a second data source), the gate must use it and name
it in `verification.detail`. The specification-shaped version: three gates
measuring against one spec cannot catch an error *inside* that spec — when
checking an acceptance criterion, name the observation that would prove it
**false** and confirm the work would actually produce it; if you can't name one,
the criterion is the defect.

Gates are a *pre-*check. The repo's mechanical gates (test runner, pre-commit
hook, CI) remain the actual authority — no agent bypasses or weakens a hook.

## 11. The validator (`scripts/check_report.py`)

The report contract is not prose — it's mechanically checked. The orchestrator
validates every artifact before routing from it; lanes with `Bash` check their
own first.

It verifies: enums are real values; every section is present; an empty section
says a bare `- none`; `DONE` is not paired with `NOT_RUN` on an order that named
a command; a non-gate lane has not issued a verdict; bullets are within length
(blocking on gate lanes, advisory elsewhere); a planning artifact's
`## Orchestrator brief` exists, is within the line cap, and names every section
below it; and (with `--head`) that the head's counts and `detail` match the
artifact. `--emit-head` derives the head from the artifact.

It **does not check whether the content is true** — no script can. It checks
that the report is *routable*. Truth is what the gates and human reading are
for. The validator has its own test suite (`test_check_report.py`) — it exists
because a review pass found six bugs in it (code fences parsed as document
structure; `detail` checked as a prefix so an agent could stop just before "4
skipped"; `US-36.10` satisfying a `US-36.1` section by substring).

## 12. What is deliberately NOT automated

- **Story authoring** — a vertical slice with no ticketed story stops the
  orchestrator. That human gate is the only cheap place to catch bad acceptance
  criteria before code.
- **Commits** — the repo's pre-commit hook and CI are the real authority. The
  network never touches that boundary. No agent commits.
- **The final test run** — the reviewer is a cheap pre-check for what a green
  suite can't see (a missing criterion, a lagging contract doc). It is not a
  substitute for the canonical suite.

## 13. Optional: a project tool server

A bound repo may expose a small tool server to the network over MCP, registered
in the repo's `.mcp.json` under the generic key **`project`** (→
`mcp__project__<tool>` prefix — generic because agent `tools:` lines live in the
agnostic layer and cannot name a repo). A second project implements the same
contract under the same key or implements none of it.

Typical tools: `run_tests` (parsed failures + bounded tail instead of 400 noisy
lines), `probe_engine` (one route's JSON computed offline), `build_snapshot` (a
valid request payload — the most-tripped fixture gotcha), `check_gates`
(per-gate verdicts before a commit is attempted), `reset_goldens` (discard
generated-file drift).

Two rules: **no tool may be the only way to do something** (each wraps a command
still runnable under `Bash`; the pack names the raw command too — the server
buys a bounded parsed return value and one removed class of error, not a
capability). **Grant per lane, narrowly** (an unused schema is a standing
context cost; the reviewer gets nothing that mutates).

## 14. Adapting this to a new project — the checklist

1. Create `.agentic/` one level above the repo. Copy `PROTOCOL.md`,
   `protocol/*.md`, `scripts/*`, `plugins/agentic-core/` **verbatim** — these
   are project-agnostic.
2. In `plugins/agentic-core/agents/`, retheme the one domain-correctness lane
   (`quant-analyst` here) to your project's irreducible-correctness domain, or
   delete it (and its gate) if the project has none. Leave the other nine agent
   files alone — if you find yourself writing a path or framework into one, it
   belongs in a capability pack.
3. Create `projects/<name>/project.md` — the binding profile. It carries: the
   numbered **hard guardrails** (an order requiring one to be broken gets
   `REFUSED`), the **stack** table, the **layout** tree, **sources of truth**
   (which doc answers which question), the **delivery model**, the **lane
   routing** table (lane → agent → pack → what it owns), the **express-lane
   eligibility** rules for this repo, which **repo skills** agents may invoke,
   the **commands** (especially the canonical test entrypoint), the **mechanical
   gates** that must never be bypassed, and the **PR convention**. Open it with
   a `## Index` block.
4. Create `projects/<name>/capabilities/<lane>.md` for each lane — paths,
   frameworks, fixtures, commands, **gotchas the reader cannot anticipate**,
   **reuse inventories** (named modules, so an engineer doesn't re-derive them),
   and **external anchors** for the gate lanes. Open each with a `## Index`
   block: "always read" for hazards/guardrails/conventions; conditional ("read
   it when your order adds an endpoint") only when the agent can evaluate the
   condition *before* reading the section. When unsure, make it always-read.
5. Drop `_repo-patch/.agentic.json` into the repo root with
   `{ "agenticRoot": "../.agentic", "project": "<name>" }`. Commit it.
6. Register the marketplace (`/plugin marketplace add <path to .agentic>`) and
   install (`/plugin install agentic-core@agentic`). **Use the local-path
   source, not a git URL** — a git-sourced marketplace reloads a clone under
   `~/.claude/plugins/`, so edits to your working directory do nothing until
   committed, pushed, and re-installed. Verify which copy is installed
   (`cat ~/.claude/plugins/installed_plugins.json` — read `version`,
   `installPath`, and the marketplace `source`).
7. Fallback if the marketplace route misbehaves: a directory junction
   (`mklink /J <repo>\.claude\agents <.agentic>\plugins\agentic-core\agents`,
   same for `skills`) works with no plugin machinery — you lose namespacing and
   versioning, keep everything else.

## 15. Authoring rules (for whoever writes/edits network files)

- **One rule, one home.** `PROTOCOL.md` and each `protocol/*.md` are disjoint —
  no rule appears in two of them. Place a new rule by *who needs it*: every lane
  → core; only the dispatcher → `orchestrator.md`; only a gate → `gates.md`;
  only the docs lane at close-out → `packs.md`; only an author → `authoring.md`.
  A rule that seems to belong in two places is usually two rules at the wrong
  abstraction level.
- **Agent files never restate the shapes.** Point at `PROTOCOL.md` §3/§4. A
  pasted copy drifts.
- **Every command in a pack must be runnable by the lane that pack belongs to.**
  Open the agent file's `tools:` line before writing a command into its pack —
  `scout`, `story-author`, `docs-engineer` have no `Bash`; a pack telling one of
  them to run `git diff` is a false premise that gets silently worked around,
  not reported.
- **Write for the reader you have.** Everything under `PROTOCOL.md`, `protocol/`,
  `projects/`, `agents/` is read only by models, once per dispatch, many
  dispatches per run. Keep the *why* that changes behaviour (a rule with a
  stated consequence is followed more reliably and lets an agent handle a case
  the rule didn't anticipate); cut the history of how the rule was discovered —
  that goes in `ARCHITECTURE.md`, whose reader is a human deciding whether to
  trust the design. Prefer a table to a paragraph wherever the content is a
  mapping.
- **Provenance lives in `ARCHITECTURE.md` only.** That file is the human-facing
  design-rationale-plus-changelog; agents never read it. The four human-facing
  runtime artifacts (the delivery brief's recommendation, the story's acceptance
  criteria, the gate verdicts, the close-out report) are written for the person
  who approves them — everything else is written for a model.
