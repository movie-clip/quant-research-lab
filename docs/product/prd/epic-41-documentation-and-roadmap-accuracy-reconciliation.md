# Epic 41 — Documentation & Roadmap Accuracy Reconciliation

**Status:** Active
**Created:** 2026-08-28
**Charter:** Documentation & Roadmap Accuracy Reconciliation, plus one carried
Dashboard-trust story (US-41.1).
**Seeded by:** the `2026-08-27-next-epic-or-story` run — a between-epics
documentation health review (`02-scout.md` § A–I). Its findings are folded in
below as `F-1..F-15`. Explicit sibling to **Epic 32 — Project Hygiene &
Agent-Facing Doc Accuracy** and **Epic 36 — Findings-First Doc & Gate Hygiene**:
the same class of work (doc-accuracy and gate-hygiene, not new product surface),
third instance, on findings those epics did not touch. The project's convention
for this class is "new epic, every time, never a reopen".

## Problem

Between Epic 32 (closed 2026-08-19) and 2026-08-27, the navigation layer around
the code drifted again. The 2026-08-27 health review found
`docs/architecture/system-architecture.md` roughly 30 epics stale — its entire
route / seam / data-flow inventory still described the pre-Epic-8 ranking /
construction / optimizer / replay product — plus six stale epic-status labels
and a missing Epic 30 heading in `docs/product/stories/README.md`, a ~35-epic
-stale `docs/product/prd/README.md` index, `build-story` invocation instructions
in the repo docs that contradict the `.agentic` pack, a stale
`current-product-state.md` header date, contract-doc `**Backend schema:**`
citations that point at a builder function rather than the class-defining
module, a non-monotonic per-epic section order in `epic-roadmap.md`, and
assorted pointer / label / date / spelling nits.

US-41.2 closed the largest item — the architecture doc — as a standalone
Backlog story with a mechanical guard, before this epic was opened. What
remained was a bundle of smaller reconciliations with no epic home (US-41.3),
plus the housekeeping of recording US-41.2 itself in the roadmap structure
rather than in a "between-epic work" narrative paragraph, and giving the orphan
US-41.1 story file an epic home. The owner opened this epic to house all of it.

US-41.1 (an inline withheld-return chart annotation) is a Dashboard
trust-surfacing feature, not documentation accuracy. It is carried here — with
its number kept and no rename — under the widened charter line above, so a
future reader is not left wondering why a chart feature sits in a doc epic. It
stays **Backlog**; nothing in this epic builds it.

### Findings and disposition

Each row folds one finding from `02-scout.md` § A–I. Dispositions are
transcribed, not re-judged.

| # | Source (scout §) | Finding | Disposition |
|---|---|---|---|
| F-1 | § A | `system-architecture.md` route / seam / data-flow / API-boundary inventory ~30 epics stale — describes `/backtests`, `/construction`, `/strategy-lab`, `/optimizer`, `/ranking` routes and services removed in Epic 8; none of the 15 real route modules documented. | **Closed by US-41.2** — the inventory was rewritten to the 15 registered routers and their real service files, and a mechanical guard `services/quant-engine/app/tests/test_architecture_doc_route_inventory.py` (bidirectional drift check, non-vacuous-scan) now fails on any future drift naming the offending module. The three protected sections (trust rule, market-data provenance, accepted-tradeoff note) stayed byte-identical. |
| F-2 | § B | `stories/README.md` carried 6 stale epic-status labels (Epic 35/34/32/26/24 headed "(active)", Epic 28 "(backlog)") while the roadmap has all six Completed. | **Closed by US-41.3** (AC6) — every epic heading now reads "(complete)"; verified already reconciled by US-41.2 / the 2026-08-27 docs passes and re-confirmed against the repo. |
| F-3 | § B | `stories/README.md` had no `### Epic 30` heading — US-30.1..30.6 listed under the Epic 28 heading though a real Epic 30 roadmap section and PRD file exist. | **Closed by US-41.3** (AC6) — `### Epic 30 — Exposure Improvements (complete)` present; re-confirmed. |
| F-4 | § B | `docs/product/stories/US-41.1-inline-withheld-return-annotation.md` existed on disk but appeared in no index — orphan, placeholder number, no Epic 41 section anywhere. | **Closed by this epic's close-out** — US-41.1 is now indexed under a new `### Epic 41` group in `stories/README.md` (Backlog), and its `**Epic:**` header field points at Epic 41. No file rename; it keeps its number. |
| F-5 | § B, § D, § G | `stories/README.md:504-505` and `prd/README.md:29` instructed agents to invoke the `build-story` skill, which the `.agentic` project profile says is "superseded and must not run". | **Closed by US-41.3** (AC6) — both sites already reconciled to route to `orchestrate-feature` / `write-story`; only a legitimate historical slice-log mention (the US-32.3 row) remains; re-confirmed. |
| F-6 | § C | Epic 40 PRD exists (retrospective) but three sites still said "PRD: none" (`epic-roadmap.md`, `stories/README.md:23`, both US-40.x headers). | **Closed by US-41.3** (AC6) — `stories/README.md` and the roadmap's Epic 40 header both point at the retrospective close-out PRD; re-confirmed. |
| F-7 | § D | `prd/README.md` § Index ~35 epics stale — listed only Epic 5 ("Active") and Epic 3, promised "PRDs for Epics 6 and 7", no pointer to `epic-roadmap.md`. | **Closed by US-41.3** (AC6) — § Index rewritten to defer to `epic-roadmap.md` as the authoritative epic index, no "Active" assertion, "Every epic is currently complete"; re-confirmed. |
| F-8 | § E | `current-product-state.md` header read "Updated: 2026-08-19 (after Epic 34 …)" while the body covered US-35.1 through US-40.2 and a dated audit. | **Partly closed pre-epic** (header date bumped to 2026-08-27 in a 2026-08-27 docs pass) **and closed by US-41.3** (AC3) — the body was read line-by-line against shipped code: one non-methodology correction ("~16 service files" → "~25 service files"), no methodology or trust-semantics claim found stale, no quant referral raised. Header re-dated to 2026-08-28 at this close-out. |
| F-9 | § F | `financial-methodology.md`'s pre-US-34.8 withholding rule — whether the terminal-day withholding passages are now internally consistent. | **Examined-and-correct** — confirmed internally consistent (the US-34.8 supersession is stated coherently across all three passages; no residual live "terminal day is withheld" framing). Confirmed in run 2026-08-26 and re-confirmed by `02-scout.md` § F. Not reopened (explicit non-goal). |
| F-10 | § F | `financial-methodology.md` quotes the terminal reconciliation adjustment as "−$58.11" (L2424) and "−$19.98" (L587); story US-34.3 says "−$53.13" — the −$53.13 is unreconciled with either. | **Still-open** — a methodology-figure reconciliation, routed to the **quant lane** as a separate carried referral (surfaced in run 2026-08-27 `02-scout.md` § F, and carried in US-41.3 `handoff` / `06-docs-us41.3.md` `handoff`). Out of Epic 41 scope by this run's non-goals (editing `financial-methodology.md` was barred). |
| F-11 | § G | `CLAUDE.md` lines 41 and 203 name the Epic-34 PRD as "most-recently shipped" / "the most recent is Epic 34"; the actual most-recent is Epic 40. | **Examined, deliberately not scheduled** — both sites explicitly hedge and defer to `epic-roadmap.md` by design (US-32.3). Surfaced, not fixed; explicit non-goal ("surfacing it, not scheduling it"). |
| F-12 | § H | Contract-doc vs schema field drift was sampled (`dashboard-fields.md`, clean), not exhaustively diffed across all 12 contracts × 20 schemas. | **Addressed outside Epic 41** — the exhaustive 12-contract × 20-schema diff was completed in run 2026-08-27 (`run.md` Closed table: `correlation-fields.md` + `diagnostics-fields.md` corrected for field drift). The one carried residual — the `correlation-fields.md` `DriftWindow` TS-type columns vs `types.ts` — was **closed by US-41.3** (AC1): verified column-for-column against `apps/desktop/src/features/portfolio/types.ts`, confirmed correct, no edit. |
| F-13 | § B, § I | Cosmetic: "(complete)" vs "(completed)" spelling mixed; `epic-roadmap.md` per-epic sections non-monotonic (Epic 25 before Epic 23 before Epic 24). | **Closed by US-41.3** — AC4: the Epic 23 / Epic 24 section blocks were swapped so per-epic headings run strictly descending (40 → 8), and a mechanical guard `services/quant-engine/app/tests/test_roadmap_epic_ordering.py` (strictly-descending assert that names the offending pair + non-vacuous-scan) shipped (T-41.3.4). AC6: spelling normalised to uniform "(complete)"; the roadmap Epic 33 heading normalised to the majority `## Completed Epic: Epic 33 —` form. |
| F-14 | § B | `correlation-fields.md` (L84) and `factor-drift-fields.md` each have a `**Backend schema:**` header line citing an analytics builder function (`analytics/risk.py` — `build_rolling_risk_series`) rather than the module where the cited Pydantic class (`RollingRiskPoint`) is defined. | **Closed by US-41.3** (AC2) — `correlation-fields.md:84` now cites `services/quant-engine/app/schemas/reconciliation.py` — `RollingRiskPoint` (class at `reconciliation.py:122`), keeping the builder function as a parenthetical "series assembled by" reference. `factor-drift-fields.md`'s header reads `**Backend schema:** _none_` and cites no Pydantic class — not applicable, no citation invented. |
| F-15 | § G | `CLAUDE.md`'s "Where to find what" doc map has no row for `docs/contracts/currency-risk-fields.md` (the file exists; only the map row is missing). | **Closed by US-41.3** (AC5) — a dedicated row was added directly after the `docs/contracts/risk-fields.md` row, in the same form, describing the Currency Risk Contribution contract (Epic 26). |

### Examined and correct (scout § I)

State confirmed current at recon time, no action taken:

- `epic-roadmap.md` snapshot ("every epic complete / no epic active / next
  unscoped") — consistent with git state and `current-product-state.md`'s body;
  no repeat of the pre-US-32.3 "Epic 31 active four epics later" failure.
- `epic-roadmap.md` per-epic sections — internally self-consistent on status
  (every closed epic is `## Completed Epic`), unlike `stories/README.md` was.
- `CLAUDE.md` repo-layout route list — accurate, matches the 15 real route
  modules (US-36.3 confirmed this).
- `current-product-state.md` body — accurate to ~Epic 40 (later re-audited
  line-by-line under US-41.3 AC3, one non-methodology correction).
- `financial-methodology.md` withholding / terminal-day passages — mutually
  consistent (see F-9).
- `dashboard-fields.md` sample — in sync with its schema.

## Goal

Every agent-facing status / navigation doc — `stories/README.md`,
`prd/README.md`, `current-product-state.md`, `epic-roadmap.md`, `CLAUDE.md`'s
doc map, the contract-doc `**Backend schema:**` citation headers — reads a state
that matches the roadmap, git and the shipped code; the 2026-08-27 findings live
in this discoverable PRD as `F-1..F-15` instead of only in a run artifact; and
US-41.2's shipped record sits in a proper roadmap epic section, not a
"between-epic work" narrative paragraph.

## Non-goals

- The exhaustive 12-contract × 20-schema field diff — completed in run
  2026-08-27 (`run.md` Closed table). Not re-run here.
- Any behaviour, schema, analytics or trust-classification change. A stale
  methodology / trust claim found during the `current-product-state.md`
  re-audit is a finding routed to quant (F-10), not a doc edit made in this
  epic.
- Reopening `financial-methodology.md`'s withholding rule — confirmed
  internally consistent (F-9).
- `CLAUDE.md`'s Epic-34 "most-recently shipped" pointer — stale in the literal
  number but hedged by design; surfaced (F-11), not scheduled.
- Building US-41.1. It is carried Backlog; nothing here implements it.

## Story list

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-41.1](../stories/US-41.1-inline-withheld-return-annotation.md) | Explain a withheld-return gap where it appears on the Performance & Benchmark chart | Carried Dashboard-trust feature — surface the existing `withheld_return_dates` disclosure inline at the chart break point in `PerformanceBenchmarkCard.tsx`; additive, no new disclosure, no methodology change. Not doc-accuracy work; carried under the widened charter line. | Backlog |
| [US-41.2](../stories/US-41.2-system-architecture-doc-accuracy-and-route-guard.md) | Make the architecture doc an agent is told to trust for backend seams match the repo, and guard it | Rewrote `docs/architecture/system-architecture.md`'s backend-seams / service-layer / data-flow / API-boundary inventory to the 15 registered routers and their real services; added the mechanical guard `test_architecture_doc_route_inventory.py`. Market-data, trust-rule and accepted-tradeoff sections untouched. (F-1.) | Done (2026-08-27) |
| [US-41.3](../stories/US-41.3-status-and-navigation-doc-reconciliation.md) | The agent-facing status and navigation docs match the roadmap, git and the shipped code | The six carried reconciliation items — `correlation-fields.md` DriftWindow TS columns (F-12), the `**Backend schema:**` citations (F-14), a line-by-line `current-product-state.md` body re-audit (F-8), `epic-roadmap.md` section ordering + guard `test_roadmap_epic_ordering.py` (F-13), the `CLAUDE.md` doc-map row (F-15), and residual pointer / label sweep (F-2, F-3, F-5, F-6, F-7). | Done (2026-08-28) |

## Gate verdicts

- **US-41.2** — tech-lead INTEGRATION (`2026-08-27-next-epic-or-story/10-integration.md`)
  PASS; reviewer acceptance (`.../11-review.md`) PASS. All 13 ACs verified
  SATISFIED against the live repo and the diff, no GAP / DRIFTED.
  `python scripts/run_all_tests.py` green (backend 947, frontend 359,
  `tsc --noEmit` clean, dead-code gate clean).
- **US-41.3** — tech-lead INTEGRATION
  (`2026-08-28-epic-41-and-dep-vulns/11-integration.md`) PASS; reviewer
  acceptance (`.../12-review.md`) PASS. AC1–AC7 all SATISFIED.
  `python scripts/run_all_tests.py` green (backend 949, frontend 359 across 40
  files, `tsc --noEmit` clean, dead-code strict gate clean). Guard test
  `test_roadmap_epic_ordering.py` confirmed red-before / green-after.

## Success signals

- The 2026-08-27 health-review findings are discoverable in this PRD as
  `F-1..F-15`, each with a disposition, not only in a run artifact.
- `stories/README.md`, `prd/README.md`, `current-product-state.md`,
  `epic-roadmap.md`, `CLAUDE.md`'s doc map and the contract-doc citation
  headers each read a state consistent with the roadmap, git and the shipped
  types.
- Two mechanical re-drift guards now cover this class — the architecture-doc
  router inventory (`test_architecture_doc_route_inventory.py`, US-41.2) and
  the roadmap per-epic section order (`test_roadmap_epic_ordering.py`,
  US-41.3) — joining `test_route_inventory.py` (US-36.3) and
  `test_docs_paths.py` (US-32.1).
- `dashboardGoldens.ts` and the backend goldens byte-identical across the
  epic; full suite, tsc and dead-code gate green throughout.

## Open items carried out of this epic

- **F-10** — the `financial-methodology.md` terminal reconciliation adjustment
  figure (−$53.13 vs −$58.11 / −$19.98) is unreconciled and routed to the
  quant lane. Not a docs edit; tracked as a standalone quant referral.
- **US-41.1** stays Backlog. It is a Dashboard-trust feature carried here for
  an epic home only; it needs its own build run.
