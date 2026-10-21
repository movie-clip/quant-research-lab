# Project profile: `portfolio`

Repo: `C:\projects\investments\portfolio` (quant-research-lab)
Bound via `portfolio/.agentic.json`.

**`CLAUDE.md` is already in your context.** Claude Code loads the repo's
`CLAUDE.md` into every dispatched lane at startup, so the product surface, the
stack, the directory layout, the canonical-doc map and the command list reach
you without a read. Treat it as read, and go to it for anything about the code
this file does not carry. (If it is genuinely not in your context, read it —
that is the one case where it is worth a tool call.)

This file carries what `CLAUDE.md` does not: the lane map, and the friction the
repo docs do not record. It also carries the **numbering** — `CLAUDE.md` states
the same five guardrails unnumbered, and the numbered list below is the one a
`REFUSED` cites. Phase bindings live in `phases.md`, which the orchestrator
reads at intake and no specialist lane needs.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Hard guardrails — no plan or lane may violate these** · **Mechanical gates — never bypass**

| Section | Read it when |
|---|---|
| Delivery model | you are the producer, or shaping a slice into stories |
| Lane routing | you are choosing which lane owns a piece of work |
| Repo skills agents may invoke | you are about to reach for anything in `portfolio/.claude/skills/`, whether or not your order named it — one of them is superseded and must not run |
| Technique skills (mattpocock-skills) | you hold the `Skill` tool and are about to call a `mattpocock-skills:*` skill, or your pack's trigger for one just fired |
| PR convention | your order asks you to open or describe a PR |

Elsewhere: **`phases.md`** — which lane fills each phase and the clause that
fires it (orchestrator, at intake). **`CLAUDE.md`** — product, stack, layout,
canonical docs, commands, truth classes (already in your context).

---

## Hard guardrails — no plan or lane may violate these

1. **Financial accuracy first.** If the math or methodology is wrong, nothing
   else matters. Any change to analytics, a factor formula or trust-state logic
   requires reading `docs/finance/financial-methodology.md` first, and updating
   its tests in the same pass.
2. **Methodology traceability.** Every UI metric maps to one engine formula and
   one code path. Untraceable → do not ship.
3. **Truth-class separation.** Broker truth, snapshot analytics, synthetic
   history and persisted imports are distinct classes. Never mixed in one
   response.
4. **Trust semantics over fabrication.** `verified > degraded > withheld >
   unavailable`. Surface the level; never fill a plausible value; never collapse
   `withheld` into `unavailable`.
5. **No execution.** The system never places trades or moves money.

An order that requires breaking one of these gets `status: REFUSED` naming the
guardrail. **This is the system's only numbered copy** — `CLAUDE.md` restates
the same five unnumbered, so a session working the repo outside the network
still sees them and a cited number still resolves to exactly one rule.

## Delivery model

**PRD → User Story → Ticket.** A story is a vertical slice delivering
user-visible value, carrying acceptance criteria, a test plan, and
`T-<epic>.<story>.<n>` tickets. Vertical slice with no ticketed story → the
orchestrator dispatches `story-author` for a draft, then stops for the human to
approve it. The human approves; the network never self-approves a story.

## Lane routing

| Lane | Agent | Pack | Owns |
|---|---|---|---|
| product | `producer` | `product.md` | roadmap placement, epic/story shaping, sequencing |
| quant | `quantitative-researcher` (RESEARCH) | `quant.md` | research brief: formulas, grounding, trust-class analysis |
| story | `story-author` | `story.md` | drafts the ticketed story |
| recon | `scout` | — | read-only exploration |
| design | `tech-lead` (DESIGN) | `architecture.md` | the contract, reuse, lane split |
| backend | `backend-engineer` | `backend.md` | `services/quant-engine/app/**` (non-test) |
| frontend | `frontend-engineer` | `frontend.md` | `apps/desktop/src/**` (non-test) |
| test | `test-engineer` | `testing.md` | `app/tests/**`, `src/**/*.test.{ts,tsx}`, `src/test/**` |
| docs | `docs-engineer` | `docs.md` | `docs/**`, and — at close-out only — `agentic/capabilities/**` when applying `pack-corrections.md` |
| quant-audit | `quantitative-researcher` (AUDIT) | `quant.md` | **financial gate**: independently recomputes, checks trust honesty |
| integration | `tech-lead` (INTEGRATION) | `architecture.md` | engineering gate: PASS / CHANGES_REQUESTED |
| review | `reviewer` | — | acceptance gate: PASS / FAIL |
| protocol-lint | `protocol-linter` | — | on request only: audits this project's profile and packs, at onboarding or when an order asks. Not a delivery phase |

Eleven agents fill these thirteen lanes — `quantitative-researcher` and
`tech-lead` each fill two, and `plugins/agentic-core/agents/` is the
authority on the roster. This table says what each lane **owns**;
`phases.md` says when it fires.

**Four gates, each checking something the others cannot see.** Three judge
the delivery, and `phases.md` § Phases carries their triggers:
`quantitative-researcher` gates the mathematics, `tech-lead` gates engineering
coherence, `reviewer` gates acceptance against the story. `protocol-lint` judges the network's own files, not this repo, so it is
not a gate here.

## Repo skills agents may invoke

These live in `portfolio/.claude/skills/` and stay there. Agents read them as
reference; they are not replaced by this network.

| Skill | Who reaches for it |
|---|---|
| `write-tests` | `test-engineer` (its content is mirrored into `capabilities/testing.md`) |
| `ui-polish` | `frontend-engineer` — mandatory for any card work; a design-system audit test enforces it |
| `fmp-data` | any lane touching market data, symbol resolution or the cache |
| `quant-research` | `quantitative-researcher` in RESEARCH mode (its brief template is mirrored into `capabilities/quant.md`) |
| `write-story` | `story-author` — for its drafting conventions only; its workflow (roadmap edits, epic placement, `build-story` handoff) is superseded by this network |
| `verify-story` | `reviewer` (its checklist becomes the gate) |
| `update-docs` | `docs-engineer` |
| `build-story` | **nobody. Superseded — do not invoke.** See below. |

### `build-story` is superseded and must not run

`build-story` implements the old linear pipeline: it works tickets in order in
one context, self-invokes `write-tests` / `verify-story` / `update-docs`, and
**commits**. Every one of those is now owned by a lane or by the human.

The repo skill's own description (`.claude/skills/build-story/SKILL.md`
frontmatter) now opens "SUPERSEDED - do not use for implementation" and
explicitly routes "build US-X.Y" / "pick up ticket T-..." / "implement the
next story" to `orchestrate-feature`, so the trigger collision is closed at
the skill itself. The residual prose that once told agents to run `build-story`
lived in `docs/product/stories/README.md` and `docs/product/prd/README.md`,
both deleted, so the collision is now closed both at the skill and across
the repo docs.

**If `build-story` loads for a request that belongs to this network, stop and
route to `orchestrate-feature` instead.** A slice built through it has no run
ledger, no gate verdicts, no contract notes, and ends with an agent commit.

## Technique skills (mattpocock-skills)

`portfolio/.claude/settings.json` enables `mattpocock-skills` alongside
`agentic-core` and `frontend-design`. Each lane's pack names its calls and
their triggers:

| Skill | Lane | Pack section |
|---|---|---|
| `mattpocock-skills:diagnosing-bugs` | backend | `backend.md` § Diagnosing a stuck bug |
| `mattpocock-skills:diagnosing-bugs` | frontend | `frontend.md` § Diagnosing a stuck bug |
| `mattpocock-skills:diagnosing-bugs`, `mattpocock-skills:tdd` | test | `testing.md` § Technique skills (mattpocock-skills) |
| `mattpocock-skills:codebase-design` | tech-lead (DESIGN, INTEGRATION) | `architecture.md` § Technique skills (mattpocock-skills) |

- Do not call any `mattpocock-skills:*` skill outside this table. Its trigger
  and lane adaptations have not been written for portfolio.
- These are technique, not house style. The repo skills above still own the
  conventions: `write-tests` for fixtures and assertions, `ui-polish` for cards.
- When a technique skill's advice conflicts with a repo skill or a pack, the
  repo skill or pack wins.
- A technique skill never licenses a formula change. A wrong number is a
  finding for `quantitative-researcher`, and guardrail 1 still applies.
- The skills that need a human interview, an issue tracker or the `Agent`
  tool (`grilling`, `prototype`, `research`, `code-review`, `wizard`) do not
  fit a dispatched lane.

## Mechanical gates — never bypass

- **CI** runs `run_all_tests.py` on every PR and push to `main`. Network-free.
- **Commit gate hook** — enforced at two layers, both checking the same
  thing (`.claude/.last-test-pass` exists and is fresher than every changed
  non-`.md` file, written only by a fully green suite run). The **git-level**
  `scripts/githooks/pre-commit` (wired via `git config core.hooksPath
  scripts/githooks`, execing `scripts/hooks/git_pre_commit.py`) is the actual
  enforcement boundary — it fires on every `git commit` regardless of which
  tool or terminal invoked git, since it runs inside git itself rather than
  inside a tool's interception layer. `core.hooksPath` is local git config,
  not committed; `scripts/run_all_tests.py` idempotently sets it early in
  every run, so a dev/agent session that has run the suite at least once has
  it wired — a clone that has never run the suite yet does not. The
  **Claude Code** `scripts/hooks/pre_commit_gate.py` (PreToolUse, matched on
  `Bash` only) remains as a faster-feedback duplicate inside agent sessions,
  not the boundary itself. **A blocked commit means re-run the suite — never
  work around either hook.**
- **Schema hook** (`schema_edit_reminder.py`, PostToolUse) fires after edits
  under `app/schemas/`, reminding that TS types and
  `docs/contracts/<area>-fields.md` must change in the same pass.
- **Dead-code gate** is enforced inside `run_all_tests.py` (ruff + vulture +
  knip, zero findings, plus `tsc --noEmit`). New dead code fails the suite.
- **`docs/product/ROADMAP.md` is generated**, by `scripts/build_roadmap.py` from
  story frontmatter, and `run_all_tests.py` fails when it is stale. Change a
  story's frontmatter and regenerate; an edit made directly to `ROADMAP.md` is
  overwritten by the next run and fails the suite in between.
- **No agent commits.** The human runs the suite and commits.

## PR convention

`.github/PULL_REQUEST_TEMPLATE.md` structures PRs around the story: story ID, AC
checklist, contracts/methodology checklist, verify verdict. GitHub only
auto-fills it in the web UI — with `gh pr create`, pass it explicitly via
`--body-file`.
