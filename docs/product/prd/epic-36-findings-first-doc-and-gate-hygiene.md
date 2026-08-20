# Epic 36 — Findings-First Doc & Gate Hygiene

**Status:** Completed (closed 2026-08-20)
**Created:** 2026-08-20
**Closed:** 2026-08-20
**Seeded by:** `docs/product/review-2026-08-20-findings.md` — a findings-first
health review done between epics (Epic 35 closed 2026-08-19, next epic
unscoped), 8 findings (F-R1–F-R8). Explicit sibling to **Epic 32 — Project
Hygiene & Agent-Facing Doc Accuracy**: the same class of work (doc-accuracy and
gate-hygiene, not new product surface), on findings Epic 32 didn't happen to
touch.

## Problem

The review found the codebase itself healthy (`run_all_tests.py` green — 779
backend + 331 frontend, `tsc --noEmit` clean, dead-code gate clean) but eight
gaps in the layer around it: a security-relevant commit gate that only covers
one tool, no dependency-vulnerability scanning, and four doc-accuracy drifts
(a stale CLI description, an undercounted route inventory, a stale PRD status
header, and an accepted security tradeoff that was never written down).

**The review's own first pass made things worse before this epic fixed them.**
Its original "Disposition" table claimed same-day fixes for F-R1, F-R3–F-R7 and
F-R8 that never actually happened — no code, no doc edit, nothing in the
repo's history matches the claims. Worse, the false F-R1 claim ("commit gate
tool-dependence — fixed 2026-08-20") was also written into `CLAUDE.md` itself
(commit `ec4ad01`), so it wasn't just a review artifact sitting unread — it was
live misinformation in the document every agent session in this project binds
to first. This epic's own delivery process caught that pattern in flight (see
"The meta-finding" below) rather than repeating it a third time.

### Findings and disposition

| # | Severity | Finding | Disposition |
|---|---|---|---|
| F-R1 | Med-high | Commit-freshness gate (`.claude/.last-test-pass` staleness check) is wired only to the Claude Code `PreToolUse` hook, matched on the `Bash` tool — a `git commit` issued through the PowerShell tool bypassed it silently. | **Folded in → US-36.1.** Fixed with a real git-level `pre-commit` hook (`core.hooksPath`), tool-independent by construction. |
| F-R2 | Med | Currency-less request-path positions silently fabricate a currency (`portfolio_snapshot_builder.py:43`). | **Deduplicated.** Confirmed exact duplicate of already-tracked **US-26.3** in `docs/tech-debt-register.md` (logged 2026-08-11). No new story or record — US-26.3 remains the owning entry. |
| F-R3 | Med | No dependency-vulnerability scanning anywhere (no `pip-audit`/`npm audit`/Dependabot). | **Folded in → US-36.2.** A scheduled, network-permitted GitHub Actions workflow now scans both ecosystems weekly, separate from the network-free `run_all_tests.py`/CI gate. |
| F-R4 | Med | Claimed `portfolio_return_trust` missing from `dashboard-fields.md`. | **Dropped — false as written.** `docs/contracts/dashboard-fields.md:289` already contains a full, substantive entry matching the schema's docstring. No story, no register entry. |
| F-R5 | Med | `cache-fields.md` describes the pre-US-35.2 CLI, not the shipped one (stale header + stale prose). | **Folded in → US-36.3** (T-36.3.1). |
| F-R6 | Med | `current-product-state.md`'s route inventory undercounts by 3 modules (12 vs. actual 15 — missing `cache.py`, `currency_risk.py`, `provenance.py`). | **Folded in → US-36.3** (T-36.3.2), plus a new mechanical regression test (`test_route_inventory.py`) so the count cannot silently drift again. |
| F-R7 | Low | `epic-24-codebase-improvement.md`'s status header still read "Active" though the roadmap and story index both have Epic 24 Completed. | **Folded in → US-36.3** (T-36.3.3). |
| F-R8 | Info (accepted tradeoff) | Import route accepts any filesystem path with no auth on the FastAPI server — reasonable given the local-first, single-user, no-execution design and non-wildcard CORS, but never written down as a deliberate decision. | **Folded in → US-36.3** (T-36.3.4) — documentation only, no code change; the tradeoff itself was judged reasonable, not a defect. |

### The meta-finding: a false "fixed" claim, corrected twice

This epic's own delivery process is worth recording explicitly, the same way
Epic 32's PRD records its own process lesson.

`CLAUDE.md` and `<agenticRoot>/projects/portfolio/project.md` both asserted, in
their "Mechanical gates" sections, that F-R1 was already closed by a git-level
hook (`scripts/githooks/pre-commit` via `core.hooksPath`) — "fixed
2026-08-20." Neither file existed anywhere in the repo; the claim was false,
confirmed independently by two lanes (`01-scout.md`, `02-delivery-brief.md`)
via `Glob` and repo-wide `Grep`. The review's own "Correction" section
(`docs/product/review-2026-08-20-findings.md`) already documents catching this
once — but at the moment this epic's own delivery run began, the correction it
described had **also** not actually landed in `CLAUDE.md`/`project.md`, so the
false claim was still live in both files.

Both files were corrected **twice** in this run, deliberately:

1. **Interim correction (order 03, pre-epic, urgent):** before any story was
   even approved, both files were rewritten to say the gap is honestly
   **open** — "That gap is open, tracked under Epic 36 (F-R1)" — because live
   misinformation in the onboarding docs outranked waiting for the epic to be
   scoped and ticketed.
2. **Final correction (T-36.1.3, order 13, after the real fix landed):** once
   the git-level hook actually existed (T-36.1.1), both files were rewritten a
   second time to describe the real mechanism accurately — including the
   `run_all_tests.py` bootstrap that wires `core.hooksPath` on every run, and
   the residual, disclosed caveat that a clone which has never run the suite
   is not yet covered by it. The "(F-R1)" citation was dropped from both, since
   citing a file that is itself being retired as the source of its own fix
   would have been circular.

The findings doc's own "Correction" section carries a **second**, smaller
self-authored error of the identical class: it claims six findings
(F-R1, F-R3–F-R7) were "logged in `docs/tech-debt-register.md`" — none were,
confirmed by grep. That error is left as-is in the findings doc (see
"Superseding the findings doc" below) rather than retroactively fixed, because
it is itself part of the audit trail this epic exists to close the loop on.

**The lesson, in the same terms Epic 32 recorded about itself:** "a document
that admits it cannot be trusted should be checked mechanically." A claimed
fix is not a fix until something independent of the claim can verify it. This
epic's actual fix for F-R1 is a git-level hook precisely because a
`PreToolUse`-matcher patch would have been re-breakable by the same
enumeration gap that broke it the first time — see US-36.1's story file for
the tech lead's full reasoning.

### Superseding the findings doc

`docs/product/review-2026-08-20-findings.md` is marked explicitly superseded
(not deleted) at close-out, pointing at this PRD as the live record — per the
established convention (Epic 32's own precedent of preserving rather than
deleting historical findings/status docs) and per the producer's brief. The
findings doc's own "Correction" section, including its second, self-authored
error described above, is preserved as-is: it is part of the who-claimed-what-
when audit trail, not something to fix retroactively.

## Goal

- Close every real, open gap the review surfaced: the commit gate's
  tool-dependence (F-R1), the absence of dependency-vulnerability scanning
  (F-R3), and the four doc-accuracy drifts (F-R5–F-R8).
- Make the commit-gate fix durable by construction (a git-level hook,
  independent of which tool invokes `git commit`) rather than patchable-again
  the way the false "fixed" claim implied a narrower fix already was.
- Add a mechanical regression check for the route-inventory count (F-R6's
  class of gap), following Epic 32's `test_docs_paths.py` precedent, so the
  count cannot silently drift again the way it did across three separate
  epics (cache/Epic 20+35, currency_risk/Epic 26, provenance/Epic 18).
- Retire the standalone findings doc as a live record once its findings are
  folded in here, while preserving it as an audit trail.

## Non-goals

- **F-R2** — not this epic's scope; stays owned by `US-26.3` in
  `docs/tech-debt-register.md`.
- **F-R4** — not a real gap; dropped, no story or record.
- **Acting on any dependency-vulnerability finding** the new scan surfaces.
  US-36.2 adds visibility only; live `pip-audit`/`npm audit` runs during
  design verification (not part of the network-free gate) already found real
  advisories against several currently-pinned backend packages
  (`starlette`, `pypdf`, `python-multipart`, `pydantic-settings`,
  `python-dotenv`) and one low-severity transitive frontend package
  (`@babel/core`) — deliberately untouched by this epic; acting on them is a
  follow-up once the scheduled workflow's first real run confirms them.
- **No behaviour or analytics change anywhere.** Every ticket in this epic is
  gate/CI/doc infrastructure; `dashboardGoldens.ts` stays byte-identical
  throughout.
- **No new product surface, card, or metric.**

## Story list

| Story | Title | Scope | Status |
|---|---|---|---|
| US-36.1 | A blocked commit stays blocked, regardless of which tool issued it | F-R1: real git-level `pre-commit` hook via `core.hooksPath`, tool-independent by construction; a self-healing `run_all_tests.py` bootstrap; a regression test exercising the real enforcement points. | Done |
| US-36.2 | CI flags a newly-vulnerable pinned dependency instead of staying silent forever | F-R3: `pip-audit`/`npm audit` scan tooling plus a separate, scheduled, network-permitted GitHub Actions workflow — not folded into the network-free `run_all_tests.py`/CI gate. | Done |
| US-36.3 | The docs an agent is told to trust for "what's shipped" actually match the repo | F-R5, F-R6, F-R7, F-R8 bundled (mirrors Epic 32's `US-32.1`/`US-32.3` bundling pattern) — cache CLI doc, route-module inventory (+ mechanical check), Epic 24 PRD status header, API-boundary tradeoff note. Also retires the standalone findings doc. | Done |

Sequencing followed the delivery brief's risk-first order: US-36.1 first
(highest-severity, actively-misleading gap), US-36.3 second (cheap, mechanical,
no open design questions), US-36.2 last (the one story with a real open design
question — whether a vulnerability scan can run inside the deliberately
network-free CI gate at all).

## Gate verdicts

- **Tech-lead INTEGRATION (`14-integration.md`): PASS.** Full
  `python scripts/run_all_tests.py` green (802 backend, 331 frontend, tsc
  clean, dead-code gate strict-clean). No `BLOCKING` findings, no change
  requests filed. 3 `SHOULD_FIX` items carried to close-out (see "Open items"
  in `docs/product/epic-roadmap.md`).
- **Reviewer acceptance (`15-review.md`): PASS.** Every AC across US-36.1
  (6/6), US-36.2 (5/5) and US-36.3 (9/9, AC8 — the findings-doc retirement —
  correctly deferred to this close-out pass) verified by direct inspection of
  the repo, not by trusting lane reports; 34 tests re-run from a fresh
  `pytest` invocation.

## Post-close addendum (2026-08-20)

A post-close review of US-36.1 found that its original AC6 was
**under-specified**: it read "fails if tool-coverage regresses" but was
satisfied by tests that only invoked the hook scripts directly, never through
a real `git commit` — proving the staleness logic couldn't regress while
proving nothing about whether the gate was reachable, which is exactly the
axis F-R1 broke on. AC6 was corrected in place to the narrower, accurate claim
("fails if the staleness logic regresses"), and AC7 (a real-`git commit`
regression test) and AC8 (a tracked-and-executable check on
`scripts/githooks/pre-commit`) were added as the missing reachability half,
closed by new ticket **T-36.1.4**. Both gates re-ran against the corrected AC
set and passed: tech-lead INTEGRATION and reviewer acceptance, both PASS. Full
detail — including why the original two PASS verdicts were each individually
correct against what they checked, and two reviewer non-blocking notes — is
recorded in US-36.1's own "Outcome" section rather than duplicated here.

## Success signals

- A `git commit` issued through any tool — Bash, PowerShell, a human's own
  terminal — is blocked on a stale or missing `.claude/.last-test-pass`
  marker, verified against the real enforcement point, not a
  reimplementation of its logic.
- A weekly scheduled scan reports the vulnerability status of both the
  backend's pinned and the frontend's locked dependency sets, without
  touching the network-free `run_all_tests.py`/CI gate.
- `cache-fields.md`, `current-product-state.md`, the Epic 24 PRD status
  header, and `system-architecture.md`'s API Boundary section all match the
  current repo state — the route-module count is additionally covered by a
  mechanical test.
- `docs/product/review-2026-08-20-findings.md` reads as explicitly
  superseded, pointing at this PRD, not as a current record.
- `dashboardGoldens.ts` byte-identical across the whole epic; full suite, tsc
  and dead-code gate green throughout.
