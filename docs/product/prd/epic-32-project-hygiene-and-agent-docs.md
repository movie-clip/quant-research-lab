# Epic 32 — Project Hygiene & Agent-Facing Doc Accuracy

**Status:** Active (created 2026-08-12)
**Created:** 2026-08-12
**Seeded by:** an end-of-cycle review after Epic 26 closed, plus two findings
deferred from the 2026-06-19 skills review that are still live.

## Problem

Every epic is now Completed, the tech-debt register holds one open row, and the
suite is green — so the *code* is in good shape. The **navigation layer around
the code is not**, and it has drifted far enough to actively mislead.

The findings below were verified against the repository on 2026-08-12, not
assumed. They split into two kinds, and the second kind is the one that costs
real time:

**Stale status surfaces** — documents that describe a project state that ended
several epics ago.

**Wrong instructions** — agent-facing documents that point an implementer at
files and modules that **do not exist**. This class has bitten before: the
`quant-research` skill carries an explicit warning that its own module table
had been wrong *twice*, each time caught only by grepping mid-task. It is wrong
again now. One of these (the `app/main.py` path) cost time inside this very
session before the correct path was found by grep.

### Findings

| # | Severity | Finding |
|---|---|---|
| F-1 | Med | **`epic-roadmap.md`'s own summary line is four epics stale.** Line 3 — the "living execution snapshot", the first thing any reader sees — describes Epic 31 as **active** with "F-1..F-3 open" and Epic 24 as **active**. Both closed. Epics 24, 26, 31 are all Completed and Epic 26 is not mentioned at all. |
| F-2 | Med | **CLAUDE.md names Epic 13 as "the most-recent shipped epic PRD"** in two places (the doc map, and "what's the scope of this epic"). Epic 13 shipped long ago; the most recent is Epic 26. An agent following CLAUDE.md for current scope is sent 13 epics back. |
| F-3 | **High** | **CLAUDE.md's route-registration instruction points at a file that does not exist.** Backend Conventions says "register in `app/main.py`"; the real path is `app/api/main.py`. Verified: `grep app/main.py` → *No such file*. The `write-story` / `write-tests` skills already say it correctly, so only CLAUDE.md is wrong. **Deferred from the 2026-06-19 skills review; still live, and it cost time in the 2026-08-11 session.** The same section's route list also omits `provenance`, `cache` and `currency_risk`. |
| F-4 | **High** | **The `write-story` skill's analytics module table lists three modules that do not exist and omits eight that do.** Listed-but-absent: `analytics/drift.py` (drift lives in `services/drift_engine.py`), `analytics/exposure.py` (sector/look-through lives inside `risk.py`), `analytics/portfolio.py` (the real module is `performance.py`). Absent-but-real: `activity.py`, `currency.py`, `currency_exposure.py`, `currency_risk.py`, `overview.py`, `performance.py`, `portfolio_imports.py`, `reconciliation.py`. An implementer following this table files new code into a module that has to be invented. |
| F-5 | Med | **All three Risk-tab cards sit outside the design-system audit.** `StressScenariosCard.tsx`, `DrawdownAnalyticsCard.tsx` and `VarDistributionCard.tsx` use the Epic-12 primitives *by convention only* — none is in `ALL_CARD_FILES`, so a hex literal, a `px` literal or a hand-rolled Synthetic badge in any of them would **not** fail the build. Deferred from the 2026-06-19 review; verified still true. |
| F-6 | Low | **`current-product-state.md`'s header claims "Updated: 2026-07-04 (after Epic 25)"** despite being updated repeatedly since (Epics 30, 31, 24, 26). |
| F-7 | Low | **`US-8.4` uses a non-standard status format** — a `## Status` section rather than the `**Status:**` header field every other story uses — so a status sweep across `docs/product/stories/` reports it as having no status. It *is* Done (2026-05-25) and the index agrees. |
| F-8 | Low | **`build-story`'s close-out instructs "commit … squash-merge … open PR" unconditionally**, which conflicts with the harness rule to commit and push only when the user asks. Deferred from the 2026-06-19 review. |

### Examined and found correct

Recorded so a future reader knows the review covered them:

- **No stray files.** `git status` clean; no `.bak` / `.orig` / `.tmp` anywhere
  outside `node_modules`.
- **Every epic is Completed** and every story file resolves to Done or
  Cancelled (F-7 is a format issue, not a missing status).
- **Every `app/...py` path referenced by `financial-methodology.md` and the
  contract docs exists** — the doc→code path drift is confined to CLAUDE.md and
  the skill table.
- **The tech-debt register holds exactly one open row** (US-26.3), correctly
  rated and not blocking.
- **`.claude/launch.json`** (added 2026-08-11) is tracked and correct.
- Suite green at 680 backend + 310 frontend; tsc and the dead-code gate clean.

## Goal

- Make every **agent-facing instruction** resolve to a file that exists. A
  wrong path in CLAUDE.md or a skill costs an implementer time on every story
  until someone greps.
- Make every **status surface** describe the project as it is today, so
  "where are we?" is answerable without reading the slice log.
- Close the two findings deferred since 2026-06-19 rather than deferring them a
  third time.
- Extend the **mechanical** design-system gate to the Risk tab, so its cards
  are enforced rather than trusted.

## Non-goals

- **No new analytics, metrics, cards or product surface.** This epic is
  navigation and enforcement only.
- **No behaviour change anywhere.** `dashboardGoldens.ts` must be
  byte-identical at the end of every story in this epic.
- **Not US-26.3.** The request-path currency coercion stays a logged tech-debt
  row; it needs a schema change touching persisted snapshots and is largely
  theoretical (every position in the app originates from an import where
  currency is schema-required).
- **No rewrite of the skills' structure or workflow.** Fix the facts they
  state; leave the process they describe alone.
- **No retroactive reformatting of old story files** beyond F-7's one-line
  status fix.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-32.1 | Fix the agent-facing instructions that point at files that do not exist | F-3 + F-4: CLAUDE.md's `app/main.py` → `app/api/main.py` and its route list; the `write-story` module table's three phantom modules and eight missing real ones. Add a mechanical test so a module table that names a non-existent path fails the suite — the fix for the *class*, since this table has now been wrong three times. |
| US-32.2 | Bring the Risk-tab cards under the design-system audit | F-5: add `StressScenariosCard.tsx`, `DrawdownAnalyticsCard.tsx`, `VarDistributionCard.tsx` to `ALL_CARD_FILES` (and `CARDS_WITH_BADGE` where they carry one), then fix whatever the audit surfaces. Deferred since 2026-06-19. |
| US-32.3 | Refresh the status surfaces | F-1, F-2, F-6, F-7: the roadmap summary line, CLAUDE.md's most-recent-epic pointers, the product-state header, and US-8.4's status format. Plus F-8's one-line wording softening in `build-story`. |

Recommended order: **US-32.1 first** (highest cost per day left unfixed — it
misleads every implementer), then US-32.2 (mechanical gate), then US-32.3
(status text, no code).

## Success signals

- Every file path named in CLAUDE.md and in the skills' module tables resolves
  to a real file — **enforced by a test**, not by review.
- A reader can answer "which epics are open, and what shipped last?" from the
  first paragraph of `epic-roadmap.md` alone, correctly.
- The design-system audit covers every card on all three tabs; adding a hex
  literal to a Risk-tab card fails the build.
- The two findings deferred on 2026-06-19 are closed.
- `dashboardGoldens.ts` byte-identical across the whole epic; full suite,
  tsc and dead-code gate green.
