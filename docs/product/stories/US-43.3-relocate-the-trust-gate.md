# US-43.3: Relocate the trust gate into its own module

**Epic:** Epic 43 — Engine Seam Consolidation
**PRD:** [`epic-43-engine-seam-consolidation.md`](../prd/epic-43-engine-seam-consolidation.md)
**Status:** Done
**Last updated:** 2026-09-03

## Story

As a **developer of this project**, I want the "is this output trustworthy
enough to publish, and at what level" decision — section-trust rollups, the
per-section output-admission policy, the price-history check, return-basis
classification — to live in one module, `services/trust_gate.py`, so that
guardrail #3's trust ladder (`verified > degraded > withheld > unavailable`) has
a single testable home instead of being parallel private helpers in the two
largest engines.

## Context

`services/dashboard_history_engine.py` and `services/diagnostics_engine.py` each
implement the same class of logic as private helpers:

| Concern | dashboard_history_engine | diagnostics_engine |
|---|---|---|
| Section-trust rollup | `_build_dashboard_section_trust` | `_resolve_section_trust` |
| Drawdown output policy | `_allow_dashboard_drawdown_outputs` | `_allow_diagnostics_drawdown_outputs` + `_apply_diagnostics_drawdown_output_policy` |
| Investor-economics status | `_build_dashboard_investor_economics_status` (+ partial-unlock) | `_build_diagnostics_investor_economics_status` |
| Price-history presence | `_has_any_symbol_price_history` | `_has_any_symbol_price_history` **(byte-identical)** |
| Replay-output presence | `_has_replay_outputs` | — |
| Return-basis classification | `_classify_portfolio_return_basis`, `_build_dashboard_return_basis_contract`, `_build_dashboard_return_basis_evidence` | (constructs `ReturnBasisEvidence` inline) |

This is a **relocation, not a unification**. The two `SectionTrust` builders
have different section shapes (`portfolio_path` / `benchmark_path` /
`monthly_returns_path` vs `benchmark_relative_path` / `factor_model_path` /
`risk_contribution_path`) and different inputs; they stay as two engine-qualified
functions inside the new module. The return-basis classification helpers also
differ between the engines and stay separate — merging any of these changes
*how* a trust value is derived and needs a quant-research pass (see Out of
scope). The **only** merge is `_has_any_symbol_price_history`, which is
byte-for-byte identical in both engines and becomes one public function.

Behaviour-neutral: the helpers move verbatim, so every `run_metadata` field and
the goldens stay byte-identical.

Recorded in `docs/tech-debt-register.md` as row US-43.3.

Implementer must read:
- `services/dashboard_history_engine.py` — helpers at ~L124–L400 and ~L720–L724.
- `services/diagnostics_engine.py` — helpers at ~L182–L330 and ~L952.
- Their call sites (both `run_*` paths) — the engines call these to build
  `run_metadata` and gate outputs.
- `services/quant-engine/app/tests/test_dashboard_history*.py`,
  `test_diagnostics*.py` — any that import or monkeypatch these helpers by name.

## Acceptance criteria

- [x] AC1 — A new module `services/trust_gate.py` holds, moved verbatim: both
  section-trust builders (kept as two functions, e.g.
  `build_dashboard_section_trust` / `build_diagnostics_section_trust`), both
  drawdown output-admission gates and the diagnostics apply-policy helper, both
  investor-economics status builders (+ the dashboard partial-unlock helper),
  `has_replay_outputs`, and the dashboard return-basis classification helpers
  (`classify_portfolio_return_basis`, `build_dashboard_return_basis_contract`,
  `build_dashboard_return_basis_evidence`).
- [x] AC2 — `_has_any_symbol_price_history` is defined **once** in
  `trust_gate.py` as `has_any_symbol_price_history` and imported by both
  engines; neither engine defines its own copy. (Body unchanged — the two
  copies are byte-identical today.)
- [x] AC3 — `dashboard_history_engine.py` and `diagnostics_engine.py` import
  every relocated helper from `services.trust_gate` and define none of them
  locally. Names may keep a leading underscore only if they stay
  module-private to `trust_gate.py` and are used nowhere else.
- [x] AC4 — **Behaviour-neutral:** `apps/desktop/src/test/dashboardGoldens.ts`
  is **untouched**, backend goldens byte-identical,
  `python scripts/run_all_tests.py` green. Every `run_metadata.section_trust`,
  output-admission decision, investor-economics status and return-basis contract
  is identical on every route.
- [x] AC5 — No behavioural merge: the two `SectionTrust` builders remain
  distinct functions with their current inputs and outputs; the dashboard and
  diagnostics return-basis paths remain distinct. A reviewer can diff each moved
  function against its pre-move body and see no logic change.
- [x] AC6 — The US-23.8 dead-code gate stays green (`ruff` / `vulture` / `knip`
  clean, `tsc` clean); no orphan left in either engine.

## Test plan

Backend (pytest):
- Retarget any import / monkeypatch of the moved helpers in
  `test_dashboard_history*.py` / `test_diagnostics*.py` to
  `app.services.trust_gate` (patched where used if the engine references them
  via its own namespace).
- **2 new tests** in a new `test_trust_gate.py`:
  1. `has_any_symbol_price_history` — the merged primitive: empty dict → `False`,
     a dict with any non-empty row list → `True` (pins the one merge).
  2. Import-surface pin: `dashboard_history_engine` and `diagnostics_engine`
     each reference `trust_gate.<helper>` for every relocated name and define
     none locally (`hasattr` / `is` identity check), proving AC3.

Regression / guardrail:
- The full `test_dashboard_history*.py` and `test_diagnostics*.py` suites stay
  green unchanged in substance — they already assert on `section_trust`,
  drawdown-output admission, investor-economics status and the return-basis
  contract, so identical values keep them green (the behaviour-neutrality
  proof).
- `python scripts/run_all_tests.py` green; **`dashboardGoldens.ts` untouched**;
  `npx tsc --noEmit` clean; dead-code gate green.

## Tickets

- [x] T-43.3.1 — **Create `services/trust_gate.py` + merge the one identical
  primitive.** Move `has_any_symbol_price_history` (single copy) and
  `has_replay_outputs`; wire both engines. Add `test_trust_gate.py` with the
  primitive test. Suite green; goldens untouched.
- [x] T-43.3.2 — **Move the section-trust builders + output-admission gates.**
  Both `SectionTrust` builders (as two functions), both drawdown gates + the
  apply-policy helper, both investor-economics status builders + the
  partial-unlock helper. Wire both engines; add the AC3 import-surface pin.
  Suite green.
- [x] T-43.3.3 — **Move the dashboard return-basis classification helpers.**
  `classify_portfolio_return_basis`, `build_dashboard_return_basis_contract`,
  `build_dashboard_return_basis_evidence`. Wire `dashboard_history_engine`.
  Suite + dead-code gate green.
- [x] T-43.3.4 — **Docs close-out.** Note `services/trust_gate.py` in
  `docs/architecture/system-architecture.md` (services inventory + the
  trust-rule section, cross-referencing guardrail #3); confirm `CONTEXT.md`;
  mark the US-43.3 register row Resolved; roadmap slice log; story → Done.

## Out of scope

- **Unifying the two `SectionTrust` builders** into one `decide(section,
  evidence)` interface — that changes how at least one section's trust is
  derived and needs a quant-research pass first (per `tech-debt-register.md`,
  US-40.1). Recorded as a register note; a separate story if ever pursued.
- **Unifying the dashboard and diagnostics return-basis classification** — same
  reason.
- **The `portfolio_proof` slice-scope admission helpers**
  (`_admitted_exact_slice_scope`, `_slice_matches_admitted_scope`) — those are
  proof-admission, not output-trust, and pull in `portfolio_proof` coupling;
  left in `dashboard_history_engine.py`.

## Notes / decisions

- **Home = `services/trust_gate.py`.** The helpers consume engine-domain inputs
  (daily states, benchmark rows, `run_metadata` sub-models) and are used only by
  services; no schema or analytics pull.
- **One merge only.** `_has_any_symbol_price_history` is a two-line pure
  function, byte-identical in both engines — merging it is output-neutral by
  inspection. Everything else stays two functions; a wide file of clearly-named
  relocated helpers is the intended shape, not a premature abstraction.
- No new formula; a relocation, not a methodology change.

### Close-out (2026-09-03) — as-built

- **Shipped shape:** new leaf module `services/quant-engine/app/services/trust_gate.py` —
  14 functions moved verbatim (bodies unchanged apart from the leading `_`
  dropping) + the module constant `DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED`.
  One merge only: `has_any_symbol_price_history` (byte-identical in both engines).
  Both engines import every relocated name from `trust_gate`; the former
  `diagnostics_engine → dashboard_history_engine` cross-import is removed (the
  last cross-engine edge). Quant-audit char-diff PASS (anchor = pre-move git blob
  `04cd099`); integration + acceptance gates PASS; backend 984 / frontend 359 green.
- **AC1 extension.** `_build_diagnostics_drawdown_summary` (→ `build_diagnostics_drawdown_summary`)
  MOVED even though AC1's literal list omits it — it is the tail of the drawdown
  output-admission pair AC1 half-moved (it consumes the same `allow_drawdown_outputs`
  flag `_allow_diagnostics_drawdown_outputs` produces and nulls the same two
  `drawdown_summary` fields `_apply_diagnostics_drawdown_output_policy` nulls on
  the snapshot); single call site; body verbatim. Design ruling
  `.agentic/runs/2026-09-03-us43.3-trust-gate-module/02-technical-plan.md` § A,
  human-approved. Also rode along: the `DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED`
  constant, whose sole consumer is the dashboard partial-unlock helper AC1 already
  moves — leaving it in the engine would create a `dashboard_history_engine ↔
  trust_gate` cycle.
- **One sanctioned rename beyond dropping `_`:** `_resolve_section_trust` →
  `build_diagnostics_section_trust` (AC1's own worked example sanctions it).
- **Relative-return output-admission pair stayed.** `_allow_diagnostics_relative_return_outputs`
  / `_apply_diagnostics_relative_return_output_policy` — the structural twin of the
  drawdown pair — was left in `diagnostics_engine.py` because AC1 named neither
  half. A possible follow-up story for symmetry; not this slice.
- **Dead-import cleanup went past the plan's named symbols.** Moving the two
  investor-economics status builders orphaned their `app.schemas.dashboard_history`
  imports in both engines (`InvestorEconomicsStatus`,
  `DashboardHistoryInvestorEconomicsPartialUnlock`,
  `DashboardHistoryInvestorEconomicsScalarPolicy`) as well as the three
  `market_data` names the plan named; all removed, forced by the ruff F401 gate,
  behaviour-neutral.
- **Test-plan "retarget `test_dashboard_history*` / `test_diagnostics*`" was moot** —
  those files do not exist, so there was no retarget. Regression evidence for the
  behaviour-neutrality proof is `test_analytics.py` + `test_routes.py` +
  `test_ledger_replay_audit.py` + `test_exposure_engine.py`, all unmodified and
  green. New `test_trust_gate.py` carries the 2 planned tests (merge primitive +
  AC3 import-surface identity pin).
- **Plan prose miscount:** `02-technical-plan.md` prose says "15 functions" but
  its own § B.2 table and the shipped module both hold 14 functions + 1 constant.
  The delivered symbol set is complete — a plan typo, not a delivery gap.
