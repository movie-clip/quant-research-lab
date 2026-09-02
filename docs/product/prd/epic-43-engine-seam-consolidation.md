# Epic 43 — Engine Seam Consolidation

**Status:** Active
**Created:** 2026-09-02
**Seeded by:** `/improve-codebase-architecture` review (2026-09-02), findings
recorded in `docs/tech-debt-register.md` as rows US-43.1–US-43.4.

## Problem

The quant-engine's hot spots — the areas the last ~60 commits keep touching —
carry four **shallow seams**: places where a module's interface leaks, or where
one concept has no module and is re-implemented as private helpers across
several engines. Each makes the financial core harder to navigate and harder to
test through its interface.

- **Synthetic History has no module.** The reconstruction of a daily-state
  series from current holdings × historical prices lives as a *private*
  `_build_synthetic_snapshot_history_states_with_coverage` in
  `services/diagnostics_engine.py`, yet is imported by **five** other engines
  (attribution, correlation, distribution, drawdown, stress). A named truth
  class is reachable only through another engine's underscore-prefixed name.
- **The factor model's internals leak out of `risk.py`.** `analytics/attribution.py`
  imports `_fit_factor_model`, `_orthogonalize_factors_window`,
  `_selected_history_return_series` and four bare constants across the seam;
  `stress_engine.py` reaches in for `STRESS_SCENARIOS`. `analytics/risk.py` is a
  2,300-line file presenting ~30 public `build_*` entry points across six
  unrelated concerns.
- **The trust ladder has no module.** `verified > degraded > withheld >
  unavailable` — guardrail #3 — is implemented as parallel private helpers in
  the two largest engines (`dashboard_history_engine.py`,
  `diagnostics_engine.py`): section-trust rollups, per-section output-admission
  policy, price-history checks, return-basis classification. One helper
  (`_has_any_symbol_price_history`) is a byte-for-byte copy.
- **Two import-bootstrap modules are pass-throughs.**
  `services/import_engine_composer.py` (36 lines) only packs a Pydantic response
  from kwargs it received unchanged; `services/import_engine.py` only sequences
  four calls. Two files, one job.

## Goal

Move each seam to where it belongs, as **behaviour-neutral relocations** — the
Epic 24 discipline:

- **Give each unnamed concept a module.** `services/synthetic_history.py`,
  `analytics/factor_model.py`, `services/trust_gate.py` — named for the concept
  (`CONTEXT.md`), with the leaked privates becoming that module's public
  interface.
- **Collapse the pass-throughs.** Fold `import_engine_composer` into
  `import_engine`; the response assembly becomes a private helper.
- **Change no computed result.** `apps/desktop/src/test/dashboardGoldens.ts` and
  the backend goldens stay **byte-identical** on every story. Any place where
  two implementations have genuinely *diverged* is out of scope here and routed
  to a methodology-reviewed story (see Non-goals).

## Non-goals

- **No behavioural unification.** Where the dashboard and diagnostics trust
  helpers differ (return-basis classification, section-trust derivation), they
  stay two functions. Merging them changes *how* a trust value is computed and
  needs a quant-research pass first (per `tech-debt-register.md`, US-40.1) — a
  separate story, not this epic.
- **No daily-return reconciliation.** Four daily-return implementations diverge
  (`risk.py` applies the US-34.8 reconciliation correction and
  `return_is_publishable`; `attribution.py` omits the former;
  `distribution`/`drawdown` engines omit both and take no basis parameter).
  Consolidating them is a methodology change, recorded as a register note, not
  built here.
- **No full `risk.py` split.** Only the leaked factor-model internals move. The
  remaining five concerns (look-through, volatility regime, risk contribution,
  stress, UCITS mapping) stay put; a full split is a tracked follow-up.
- **No new analytics or product surface.**

## Story list

| Story | Title | Scope | Sequence |
|---|---|---|---|
| US-43.1 | Extract synthetic-history construction into its own module | Move `_build_synthetic_snapshot_history_states[_with_coverage]` from `diagnostics_engine.py` to a new `services/synthetic_history.py`, public names; rewire the 6 consuming engines and the tests. Behaviour-neutral | 1st |
| US-43.2 | Extract the factor-model internals out of `risk.py` | New `analytics/factor_model.py` holds `_fit_factor_model`, `_orthogonalize_factors_window`, `_selected_history_return_series` + `FACTOR_KEY_MAP` / `FACTOR_PROXY_MAP` / `DEFAULT_FACTOR_DEFINITIONS` / `ROLLING_RIDGE_FLOOR` / `FactorDefinition`; the `ReturnBasis` literal moves to `schemas/return_basis.py`. `risk.py` imports them back; rewire attribution / attribution_engine / stress_engine and the ~4 `test_analytics.py` monkeypatch targets. Behaviour-neutral | 2nd |
| US-43.3 | Relocate the trust gate into its own module | New `services/trust_gate.py` holds both `SectionTrust` builders (kept as two engine-qualified functions), `_has_replay_outputs`, the drawdown/investor-economics output-admission gates, and the return-basis classification helpers; the byte-identical `_has_any_symbol_price_history` is merged to one public function. No behavioural change. Behaviour-neutral | 3rd |
| US-43.4 | Collapse `import_engine_composer` into `import_engine` | Fold the 36-line composer into `import_engine.py`; `compose_import_bootstrap_response` → `_compose_import_bootstrap_response`; delete the file; keep the three public entry functions. Behaviour-neutral | 4th |

**Build order:** 43.1 → 43.2 → 43.3 → 43.4. The stories touch disjoint modules
and are independently shippable; the order runs highest-leverage-first
(synthetic-history's 5-consumer leak) and defers the pass-through collapse as
the warm-down.

## Notes

- Every story's real deliverable is the **byte-identical goldens** proof plus
  the full `python scripts/run_all_tests.py` green — the relocation is only
  safe if nothing downstream moved.
- The new module names are recorded in `CONTEXT.md` (created with this epic).
