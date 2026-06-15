# Epic 23 — Dead-Code Cleanup & Codebase Review

**Status:** Active
**Created:** 2026-06-12

## Problem

The codebase has grown across 22 epics. Real friction this session
(the never-consumed admission-disposition plumbing, possibly-empty
`features/market-data` / `features/settings` dirs, a re-discovered timing-flaky
test) shows two accumulating costs:

1. **Dead / unused code.** Schemas, functions, components, types, helpers, CSS
   tokens, and whole modules that are defined, persisted, or imported but have
   **no live producer or consumer**. It inflates the surface area an agent must
   read, makes "what's actually used?" ambiguous, and lets bugs hide.
2. **No detection floor.** There is **no dead-code tooling** (no
   ruff/vulture for Python, no knip/ts-prune/eslint for TypeScript) and
   `tsconfig` lacks `noUnusedLocals`/`noUnusedParameters`. Detection today is
   manual and ad-hoc — so things get missed, which is exactly the failure mode
   to avoid for a "review everything" pass.

Separately, the review **surfaces** (does not fix) a second class of issue:
**hardcoded values and questionable techniques** — magic numbers, inlined
thresholds, fragile coupling, missing abstractions — that should be improved,
but as a deliberate, reviewed change, not mixed into deletion diffs.

## Goal

A **safe, comprehensive, per-area** sweep that:

- **Removes confirmed-dead code** across the whole project, one reviewable area
  per story, with the full deterministic test suite green after each.
- Stands up a **detection floor** (tooling + tsconfig flags) so dead code is
  caught going forward, not re-accumulated.
- **Catalogs** every hardcode / anti-pattern / improvement candidate found
  during the sweep into a single **tech-debt register**
  (`docs/tech-debt-register.md`), categorized with `file:line`, severity, and
  rough effort — feeding a **follow-up improvement epic** (Epic 24).

The split is deliberate: this epic's diffs are **deletions + tooling + docs
only**. Behaviour-changing refactors and hardcode fixes are **out of scope** —
they are catalogued here and executed later, so the cleanup stays low-risk.

## Non-goals

- **No behaviour change.** Removing dead code must not change any computed
  number, route response, rendered output, or persisted format. The suite
  staying green is the proof.
- **No fixing of the catalogued smells.** Hardcodes and anti-patterns are
  *recorded*, not changed, in this epic (that's Epic 24). The only exception is
  a hardcode that is itself dead (delete it).
- **No touching financial formulas, trust-state logic, or the methodology** as
  "cleanup." Any change near `analytics/`, the trust ladder, or admission
  semantics that is more than a pure unused-symbol deletion is out of scope and
  goes to the register, not the diff. (Financial-accuracy guardrail.)
- **No new runtime dependencies.** Detection tooling is dev-only.
- **No mass reformatting / style churn.** Whitespace/lint-style reflows are not
  part of this epic.

## The safety protocol (applies to every removal)

A symbol/file is **"confirmed dead"** only when ALL hold:

1. No static reference anywhere (grep + the area's detection tool agree).
2. No **dynamic / reflective** use — `getattr`, string-keyed dispatch, route
   auto-registration, pytest collection, JSON `schema_version` round-trips,
   IndexedDB/localStorage **persistence or migration** sanitizers (the
   disposition plumbing is the cautionary example — it *looks* dead but
   sanitizes persisted state).
3. Not part of a **public contract** still referenced by docs/types on the
   other side of the seam (reconcile in US-23.5 first if so).
4. The full `python scripts/run_all_tests.py` is green after removal, and
   `npx tsc --noEmit` is clean.

When in doubt, it goes to the register as "suspected dead — needs decision",
not the deletion diff.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-23.1 | Detection tooling + tech-debt register + removal protocol | Add dev-only dead-code tooling (Python: vulture + ruff unused-rules; TS: knip or ts-prune; enable `tsconfig` `noUnusedLocals`/`noUnusedParameters`); wire a `detect-deadcode` script; create `docs/tech-debt-register.md` with the category schema + the removal protocol. The keystone every later story uses. |
| US-23.2 | Backend dead-code sweep — analytics, schemas, domain, instruments | Pure-logic core: remove confirmed-dead functions/classes/schemas (e.g. orphaned admission-disposition schema once its FE consumer is gone), unused imports, dead branches; catalog hardcodes/magic-numbers/smells in these modules. No formula change. |
| US-23.3 | Backend dead-code sweep — services, routes, clients, core, importers | The wiring tier: dead service helpers, unregistered/unreachable routes, unused client methods, dead core utilities, importer cruft; catalog smells (inlined thresholds, fragile parsing, duplication). |
| US-23.4 | Frontend dead-code sweep — app & features | Unused exports/components/types/helpers (the admission-disposition persistence plumbing), empty/legacy feature dirs (`features/market-data`, `features/settings`), dead CSS tokens/classes; catalog FE smells (inline literals not yet tokenised, prop-drilling, duplicated formatters). |
| US-23.5 | Contract & schema↔type↔docs drift reconciliation | Cross-seam audit: backend Pydantic schemas vs desktop TS types vs `docs/contracts/*` — fields defined-but-unused, type/nullability drift, contract rows for removed things. Resolve drift so US-23.2/23.3/23.4 deletions don't break a documented contract. |
| US-23.6 | Tests, fixtures & golden-pipeline hygiene | Dead test helpers, skipped/duplicate tests, fixtures not migrated to the US-21.2 shared module, obsolete golden-adjacent code; ensure the network guard + frozen-goldens determinism still hold. Catalog test-smells. |
| US-23.7 | Scripts, tooling & docs reconciliation | `scripts/` dead code; reconcile `current-product-state.md` / architecture / roadmap with the now-leaner code; consolidate the tech-debt register; draft the Epic 24 (improvement) story seeds from it. |
| US-23.8 | Enforce the dead-code floor in the canonical test gate | **The tail.** Once the baseline is clean, wire `knip` + `ruff` + `vulture` (zero-findings vs a reasoned allowlist) into `run_all_tests.py` so newly-introduced unused/dead code fails the suite — so the project never needs another manual cleanup epic. Closes Epic 23. |

Recommended build order: 23.1 → (23.5 first to settle contracts) → 23.2 → 23.3
→ 23.4 → 23.6 → 23.7 → **23.8**. (23.5 early so cross-seam contracts are known
before deletions; 23.7 reconciles docs + hands off the register; **23.8 last**
because the enforcement gate can only be green once the baseline is clean.)

**Tool choice for enforcement (researched, US-23.8):** the standing gate is
`knip` (unused exports/files/deps — the dead-export class) + `tsc`
`noUnusedLocals` (in-file) for the frontend, and `ruff` + `vulture` for the
backend. **ESLint is deliberately not adopted** — its `no-unused-vars` is
in-file only and redundant with `tsc`; it would not catch the unused *exports/
files* that actually accumulate, so it adds maintenance without closing the gap.

## Success signals

- The detection tooling runs clean (or with an explicit, reviewed allowlist) for
  each area after its story; `noUnusedLocals` is on and tsc is clean.
- A measurable reduction in dead surface (counts of removed symbols/files/lines
  recorded per story in the slice log), with the **full suite green and zero
  behaviour change** after each.
- `docs/tech-debt-register.md` exists and is populated across all areas, each
  entry with `file:line`, category, severity, and effort — ready to seed Epic 24.
- A fresh agent reading the codebase sees only live code; "is this used?" is
  answerable by the tooling, not by tribal knowledge.
- **The dead-code gate is enforced (US-23.8):** after the baseline is clean,
  `run_all_tests.py` fails on any new unused/dead code — so dead code cannot
  re-accumulate and no future cleanup epic is needed. (This supersedes the
  earlier "no gating, not now" stance, which applied only while the baseline was
  dirty.)
