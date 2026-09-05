# US-43.4: Collapse `import_engine_composer` into `import_engine`

**Epic:** Epic 43 — Engine Seam Consolidation
**PRD:** [`epic-43-engine-seam-consolidation.md`](../prd/epic-43-engine-seam-consolidation.md)
**Status:** Done
**Last updated:** 2026-09-05

## Story

As a **developer of this project**, I want the import-bootstrap flow to be one
module instead of two, so that following "how a broker statement becomes an
`ImportedBootstrapResponse`" does not bounce through a 36-line file whose only
job is to fill a Pydantic object from kwargs it received unchanged.

## Context

`services/import_engine_composer.py` (36 lines) exposes one function,
`compose_import_bootstrap_response(...)`, which constructs an
`ImportedBootstrapResponse` from arguments passed straight through by
`services/import_engine.py`'s `build_import_bootstrap_from_snapshot`. The
**deletion test**: folding the composer into `import_engine` concentrates no
complexity — it removes one hop. `import_engine.py` is the only importer of the
composer anywhere in `app/`; no test imports it directly.

Behaviour-neutral: the assembled response is identical; the goldens stay
byte-identical.

Recorded in `docs/tech-debt-register.md` as row US-43.4.

Implementer must read:
- `services/import_engine.py` (all 52 lines — the three public entry functions
  `build_import_bootstrap`, `build_import_bootstrap_from_portfolio_snapshot_request`,
  `build_import_bootstrap_from_snapshot`).
- `services/import_engine_composer.py` (all 36 lines).
- `grep -rn "import_engine_composer\|compose_import_bootstrap_response" app/` —
  confirm `import_engine.py` is the sole consumer before deleting.

## Acceptance criteria

- [x] AC1 — `compose_import_bootstrap_response`'s body is moved into
  `services/import_engine.py` as a module-private helper
  `_compose_import_bootstrap_response(...)`; `services/import_engine_composer.py`
  is deleted.
- [x] AC2 — The three public entry functions in `import_engine.py` keep their
  names, signatures and behaviour. Callers of `import_engine` (the `imports`
  route, `import_engine` itself) are unchanged.
- [x] AC3 — **Behaviour-neutral:** `apps/desktop/src/test/dashboardGoldens.ts`
  is **untouched**, backend goldens byte-identical, and
  `python scripts/run_all_tests.py` is green. The `ImportedBootstrapResponse`
  returned on every import path is field-identical to before.
- [x] AC4 — No dangling reference to `import_engine_composer` anywhere in `app/`
  or `app/tests/`; the US-23.8 dead-code gate stays green (`ruff` / `vulture` /
  `knip` clean, `tsc` clean).

## Test plan

Backend (pytest):
- No new unit test for the private helper — it is exercised end to end by the
  existing import-bootstrap coverage.
- **1 assertion** added to the nearest existing import-bootstrap test
  (`test_import_*` / `test_importer.py` / the bootstrap route test): the module
  `app.services.import_engine_composer` no longer imports
  (`pytest.raises(ModuleNotFoundError)`), pinning AC1/AC4.

Regression / guardrail:
- The existing import-bootstrap and `imports` route suites stay green unchanged
  — they assert on the full `ImportedBootstrapResponse` shape, so an identical
  response keeps them green (the behaviour-neutrality proof).
- `python scripts/run_all_tests.py` green; **`dashboardGoldens.ts` untouched**;
  `npx tsc --noEmit` clean; dead-code gate green.

## Tickets

- [x] T-43.4.1 — **Fold + delete.** Move the compose body into
  `import_engine.py` as `_compose_import_bootstrap_response`; update the call in
  `build_import_bootstrap_from_snapshot`; delete
  `services/import_engine_composer.py`; add the AC1 pin assertion. Suite green;
  goldens untouched; dead-code gate green.
- [x] T-43.4.2 — **Docs close-out.** Confirm `docs/architecture/system-architecture.md`
  and `CONTEXT.md` ("import bootstrap") name only `services/import_engine.py`;
  mark the US-43.4 register row Resolved; roadmap slice log; story → Done.

## Out of scope

- **Absorbing `portfolio_snapshot_builder.py` or `history_context_builder.py`**
  into `import_engine` — those have their own callers and are not pass-throughs;
  not touched.
- **Any change to the `ImportedBootstrapResponse` schema or the import flow's
  behaviour.**

## Notes / decisions

- **Warm-down story.** Smallest and lowest-risk of the epic; sequenced last so
  the higher-leverage relocations land first.
- Stale `import_analysis` / `import_analysis_composer` `.pyc` artifacts in
  `__pycache__` are from a prior rename and are not in scope — do not
  resurrect those names.
- No new formula; a pass-through collapse, not a methodology change.

### Close-out (2026-09-05) — as-built

- **Shipped shape:** `compose_import_bootstrap_response`'s body folded verbatim
  into `services/quant-engine/app/services/import_engine.py` as module-private
  `_compose_import_bootstrap_response(...)` — including the delegated
  `build_import_admission_summary(snapshot)` call. Three new imports added
  (`ExposureAvailability, ExposureCurrentStateConcentration`;
  `PortfolioHistoryContext`; `build_import_admission_summary`); the existing
  `app.schemas.reconciliation` import extended onto one line rather than
  duplicated. The sole call site, inside `build_import_bootstrap_from_snapshot`,
  changed from `return compose_import_bootstrap_response(` to
  `return _compose_import_bootstrap_response(` — every keyword argument below
  it unchanged. All three public entry functions kept their exact prior names
  and signatures.
- **The `git rm` step.** No lane holds a delete tool, so
  `services/quant-engine/app/services/import_engine_composer.py` could not be
  removed by the backend lane — a human ran
  `git rm services/quant-engine/app/services/import_engine_composer.py`
  between the backend and test dispatches (confirmed absent from disk and
  `git status --porcelain` shows `D` for the file, per the integration gate).
- **Pin test location.** `test_import_engine_composer_module_is_gone` added to
  `services/quant-engine/app/tests/test_analytics.py` immediately after
  `test_build_import_bootstrap_from_snapshot_falls_back_to_ledger_and_position_dates_when_statement_period_missing`;
  asserts `pytest.raises(ModuleNotFoundError)` on
  `import app.services.import_engine_composer`, pinning AC1/AC4.
- Quant-audit skipped by human-approved ruling (pure Pydantic-construction
  relocation, no `analytics/`, formula, weighting, return-basis, or
  trust-classification code touched — `.agentic/runs/2026-09-04-us43.4-collapse-import-composer/02-technical-plan.md`
  § Quant-audit ruling); integration gate PASS, independently re-confirming all
  four ACs (verbatim fold, call-site-only behavioural change, goldens
  byte-identical + full suite green, no dangling reference to the deleted
  module/function anywhere under `app/`). Backend 985 passed (was 984 at
  US-43.3 close; +1 new pin test); dead-code gate (ruff/vulture/knip) clean;
  `tsc --noEmit` clean; `dashboardGoldens.ts` diff empty.
- `ImportedBootstrapResponse` schema untouched — no TS/contract-shape change
  owed. One dangling code pointer corrected in `docs/contracts/exposure-fields.md`
  (the field-forwarding call chain now names `_compose_import_bootstrap_response(...)`
  inside `import_engine.py`, not the deleted `import_engine_composer.py`).
- Epic 43 — Engine Seam Consolidation is now **Completed**: all four stories
  (US-43.1–US-43.4) Done.
