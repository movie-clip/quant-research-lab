# Epic Roadmap

This file is the living execution roadmap for the four active product epics.

- Shipped-state truth belongs in `docs/product/current-product-state.md`.
- Future-looking product direction belongs in `docs/product/roadmap.md`.
- Future-looking technical sequencing belongs in `docs/product/technical-roadmap.md`.

After every shipped slice or epic checkpoint, update this file first, then update shipped-state docs and contracts if the slice changed product truth.

## Roadmap Snapshot

| Epic | Objective | Current status | Current slice | Next slice | Last updated |
| --- | --- | --- | --- | --- | --- |
| 1. Imported-portfolio truth and reconciliation guard | Keep imported portfolio truth, trust semantics, and reconciliation explicit before downstream methodology layers | Foundation strong; productization still missing a first-class reconciliation admission/review surface | No active slice | Reconciliation admission summary and exception review | 2026-05-06 |
| 2. Ranking and selection methodology guard | Generalize ranking into a broader methodology platform with explicit selection guardrails and artifact-backed reuse | Active epic | No active slice | Broaden supported ranking families only after explicit selection-readiness semantics stay clear | 2026-05-06 |
| 3. Construction and optimizer methodology guard | Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts | Phase closed / guardrail-complete for current phase; breadth still narrow | No active slice | Future breadth work: add configurable `top_n`, richer constraints, broader policy coverage, optional inverse-rank promotion if desired, broader ranking-family construction eligibility, and cleanup of narrow lineage assumptions | 2026-05-08 |
| 4. Monitoring and overlay review guard | Extend narrow review-scoped monitoring into broader persisted discipline workflows | Narrow shipped breadth; review mechanics stronger than monitor-family breadth | No active slice | Surface active alert-episode inbox more directly in Workspace | 2026-05-06 |

## Cross-Epic Guardrails

- Truth classes, degradation, withholding, and unavailability remain explicit.
- Persisted artifacts and typed handoffs remain authoritative.
- Desktop stays thin on finance logic.
- Optimization remains hypothetical and subordinate to rule-based construction.
- Fail-closed loading and lineage validation must not be weakened.

## Program Snapshot

- Current stage: prototype flow stabilized, regression green, desktop build green.
- Active epic: `2. Ranking and selection methodology guard`.
- Current sequence: `Epic 2 -> Epic 3 -> Epic 4`, while `Epic 1` remains the foundational guardrail.
- Epic 3 is phase closed / guardrail-complete for this phase; remaining construction and optimizer work is breadth expansion rather than guardrail closeout.
- Biggest current gap: ranking is still too ETF-centric relative to the target methodology platform.

## Epic 1. Imported-Portfolio Truth and Reconciliation Guard

### Objective

Keep imported portfolio truth, trust semantics, and reconciliation explicit before downstream ranking, construction, optimizer, or monitoring workflows are allowed to overclaim certainty.

### Shipped baseline

- Broker import, workspace snapshots, immutable saved nodes, and working drafts are shipped.
- Dashboard, Exposure, diagnostics, and replay now carry explicit trust/degradation/withholding semantics.
- Imported-history and combined-statement regression coverage was recently hardened.

### Target state

- Imported portfolio truth is admitted through an explicit reconciliation guard before downstream workflows depend on it.
- Residual cash, symbol mismatches, NAV breaks, and unsupported evidence states are reviewable as first-class reconciliation outcomes.

### Open gaps

- No first-class reconciliation admission surface yet.
- No dedicated exception-management workflow for residual breaks or import mismatches.

### Planned slices

- Reconciliation admission summary and review surface.
- Exception review for residual cash, symbol, and NAV mismatch cases.

### Dependencies

- Feeds all other epics.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/finance/financial-methodology.md`
- `docs/contracts/exposure-fields.md`
- import, analytics, and route tests under `services/quant-engine/app/tests`

### Exit criteria

- Imported truth admission is explicit, reviewable, and blocks downstream overclaiming when reconciliation is not good enough.

## Epic 2. Ranking and Selection Methodology Guard

### Objective

Generalize ranking into a broader methodology platform with explicit selection guardrails, reusable artifact-backed discovery, and canonical downstream handoffs.

### Shipped baseline

- Persisted ETF ranking artifacts are shipped.
- Persisted intent-bound replacement ranking artifacts are shipped.
- Generalized ranking artifact catalog and recent discovery are shipped backend capabilities.
- Desktop can reopen recent ETF ranking runs and carry selected ranking artifacts into review.

### Target state

- Ranking discovery, open, and downstream handoff work through the generalized artifact platform rather than ETF-only seams.
- Selection methodology becomes more explicit than a simple ordered list.

### Open gaps

- Desktop still leans on ETF-native recent discovery instead of the generalized ranking-artifact path.
- Generalized ranking remains narrow in visible desktop workflow.
- Selection guardrails and broader ranking families are not yet productized.

### Planned slices

- `Shipped`: desktop recent discovery now uses generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=etf_ranking`, while ETF-native metadata remains temporary for peer-group filter options.
- `Shipped`: Workspace Candidate Idea now browses and opens persisted replacement ranking artifacts read-only through generalized recent plus generalized preflight/open, with fail-closed validation and ephemeral in-memory state only.
- `Shipped`: persisted ETF ranking artifacts can now hand off into persisted construction review through canonical construction preflight plus construction run, exposed from both ETF Ranking and Workspace Candidate Idea while remaining ETF-only in this slice.
- `Shipped`: persisted intent-bound ETF replacement ranking artifacts can now also hand off into persisted construction review through the same canonical construction preflight plus construction run seam, while remaining replacement-family-only in this slice.
- `Shipped`: construction preflight for the two supported ranking families now returns typed eligibility/readiness semantics, so desktop can distinguish supported-but-ineligible artifacts from malformed or unsupported artifact states before `Review In Construction`.
- Next: broaden supported ranking families only after explicit selection-readiness semantics stay clear.

### Dependencies

- Depends on imported truth guardrails.
- Unlocks richer construction and optimizer methodology work.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/roadmap.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/etf-ranking-fields.md`
- ranking artifact and strategy-lab tests under `services/quant-engine/app/tests`

### Exit criteria

- Generalized ranking artifact discovery/open is the visible default desktop path for shipped ranking families.

## Epic 3. Construction and Optimizer Methodology Guard

### Objective

Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts and explicit review-basis provenance.

### Shipped baseline

- Persisted construction engine, policy catalog, preview, and replay are shipped.
- Construction provenance, hard-constraint truth, weighting trace, and turnover diagnostics are shipped.
- Optimizer preview, handoff, replay, and methodology provenance are shipped.
- Desktop restore and review-basis handling were recently hardened.
- Desktop `Review In Construction` now consumes authoritative backend policy discovery for the shipped ranking-to-construction bridge.

### Target state

- Desktop uses authoritative backend construction policy discovery and stronger ranking-to-construction handoff.
- Optimizer review compares against stronger rule-based baselines under the same explicit provenance rules.

### Phase closeout status

- Closed for this phase / guardrail-complete.
- The shipped narrow boundary preserves artifact-backed ranking-to-construction handoff, backend-authoritative policy discovery, fixed launch-profile semantics, fail-closed lineage validation, explicit review basis, and hypothetical-only optimizer/construction truth separation.

### Future breadth gaps

- Canonical ranking-to-construction handoff is shipped for the narrow `ranking_artifact_review_handoff_v1` launch profile; broader eligibility and parameterization remain open.
- Policy and constraint breadth remain narrow.
- Ranking-entry portfolio lineage and policy parameterization are still intentionally narrow in the current desktop bridge.

### Planned slices

- `Shipped`: desktop ranking-to-construction review now uses authoritative backend `/construction/policies` discovery for policy selection and exposes required `max_position_weight` plus optional `min_position_weight` inputs while keeping the bridge parameter-light.
- `Shipped`: the broader Epic 3 launch boundary is now explicit and stabilized as `preflight -> typed handoff -> /construction/run -> persisted construction artifact review` for exactly two supported ranking families: `etf_ranking` and `intent_bound_etf_replacement_ranking`, with desktop fail-closed policy discovery and fixed `top_n = 2` launch semantics.
- `Shipped`: the existing Workspace artifact-backed ranking-to-construction launch browsers now also expose optional `max_turnover_weight` and optional `max_trade_intent_count`, with shared local validation, omission-on-blank request serialization, and no widening of policy authority, ranking-family support, or inline launch paths.
- `Shipped`: canonical launch context is now preserved and fail-closed across the full shipped ranking-to-construction review boundary, including ranking artifact id/schema/ranking lineage, current portfolio identity/timestamp, selected policy id/definition, and fixed `top_n` lineage through persisted construction artifact reopen.
- `Shipped`: backend policy discovery now stamps one canonical `ranking_artifact_review_handoff_v1` launch profile with explicit default/opt-in/excluded status, desktop consumes that metadata instead of hardcoded launch allowlists/defaults, and review surfaces read back the shipped `top_n = 2` plus required/optional hard-constraint boundary next to construction launch controls.
- Future breadth work: add configurable `top_n`, richer constraints, broader policy coverage, optional inverse-rank promotion if desired, broader ranking-family construction eligibility, and cleanup of narrow lineage assumptions.

### Dependencies

- Depends on Epic 2 generalization.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/backtest-fields.md`
- construction and optimizer tests under `services/quant-engine/app/tests`

### Exit criteria

- Supported construction and optimizer review workflows consume explicit upstream artifact/handoff boundaries and preserve review basis throughout.
- Broader ranking-family eligibility, policy breadth, configurable `top_n`, and richer constraints remain future work.

## Epic 4. Monitoring and Overlay Review Guard

### Objective

Extend narrow review-scoped monitoring into broader persisted discipline workflows without weakening current alert lifecycle or fail-closed review authority.

### Shipped baseline

- `benchmark_trend_overlay_v1` monitor-definition workflow is shipped.
- Latest-observation, recovered-review, active alert-episode, and timeline/history review surfaces are shipped.
- Workspace restore from persisted monitor review state was recently strengthened.

### Target state

- Monitoring grows into a broader discipline layer with more visible inbox/history workflows and more than one narrow monitor family.

### Open gaps

- Monitor-family breadth is still narrow.
- Monitoring is still more review-scoped than ongoing discipline-system level.

### Planned slices

- Surface active alert-episode inbox more directly in Workspace.
- Add definition-scoped alert-episode history drill-in using existing routes.

### Dependencies

- Benefits from stronger upstream ranking, construction, and replay methodology boundaries.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/roadmap.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/backtest-fields.md`
- monitoring and route tests under `services/quant-engine/app/tests`

### Exit criteria

- Monitoring is no longer only a narrow replay-adjacent review seam and has broader persisted review coverage without overclaiming continuity.

## Slice Update Log

### 2026-05-08 - Epic 3 phase closeout

- Epic: `3. Construction and optimizer methodology guard`
- Status: docs-only phase closeout.
- Marked Epic 3 phase closed / guardrail-complete for the current phase while preserving construction and optimizer breadth expansion as future work.
- No code, test, contract, current-state, or technical-roadmap changes beyond this roadmap closeout.

### 2026-05-07 - Epic 3 ranking bridge stabilization follow-up

- Status: shipped slice stabilization
- Aligned docs, backend discovery, and desktop wording to the broader shipped ranking-to-construction bridge: backend-authoritative policy selection from `/construction/policies`, typed preflight/handoff launch semantics, and persisted construction artifact review.
- Tightened the launch boundary so desktop-compatible policy discovery now carries explicit `launch_top_n = 2`, desktop consumers fail closed on mismatched catalog rows, and backend handoff-backed construction rejects `policy.top_n != 2` for the shipped launch path.
- Kept the bridge intentionally parameter-light and review-only: `top_n = 2`, desktop surfaces only required `max_position_weight` plus optional `min_position_weight`, other optional constraints stay hidden, and supported ranking families remain limited to ETF and intent-bound replacement artifacts.

### 2026-05-08 - Epic 3 slice 3 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: expose optional `max_turnover_weight` and optional `max_trade_intent_count` on the shipped artifact-backed ranking-to-construction desktop bridge.
- Status: shipped.
- Scope delivered:
  - Workspace persisted ETF ranking and persisted replacement ranking construction browsers now expose optional `Max Turnover Weight` and `Max Trade Intent Count` beside the existing max/min position-weight inputs.
  - desktop uses one shared validation path across both browsers so blank optional fields omit from the request, `max_turnover_weight` accepts decimal values in `[0, 1]` including `0`, and `max_trade_intent_count` accepts whole numbers `>= 0` including `0`.
  - ranking-artifact construction handoff now serializes those two optional hard constraints only when the user supplies non-null values, while preserving the same backend-authoritative policy selection and fixed `top_n = 2` launch boundary.
- Guard impact:
  - broadens the visible hard-constraint surface only within the agreed artifact-backed desktop bridge and keeps construction review hypothetical, persisted-artifact-backed, and limited to the same two supported ranking families.
  - does not widen backend capability, policy families, ranking families, or inline ranked-universe launch paths.
- Contracts changed:
  - no backend contract changes.
  - desktop handoff now optionally serializes `hard_constraints.max_turnover_weight` and `hard_constraints.max_trade_intent_count` only when explicitly supplied.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n` and the currently exposed hard-constraint set.

### 2026-05-08 - Epic 3 slice 4 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: make `top_n_linear_rank_weight_v1` an explicit launch-compatible opt-in on the shipped artifact-backed ranking-to-construction desktop bridge while keeping equal-weight the only auto-selected default.
- Status: shipped.
- Scope delivered:
  - desktop ranking-to-construction policy pickers now surface only `top_n_equal_weight_v1` and `top_n_linear_rank_weight_v1` for the existing artifact-backed launch browsers and ETF Ranking recent-run handoff entry point.
  - equal-weight remains the only auto-selected default when backend discovery returns it; if not, desktop stays fail-closed until the user explicitly chooses the linear-rank alternative.
  - the narrow launch boundary remains unchanged: review-only/hypothetical artifact-backed semantics, same two supported ranking families, backend-owned policy discovery, fixed `top_n = 2`, and post-run lineage checks for `policy_id`, `policy_definition_id`, and normalized `top_n`.
- Guard impact:
  - narrows desktop launch-scope exposure without widening backend construction capability, persistence, replay, or catalog rows.
  - does not expose `top_n_inverse_rank_weight_v1` on desktop launch surfaces in this slice.
- Contracts changed:
  - no backend contract changes.
  - desktop launch compatibility now filters discovered policies down to the shipped opt-in set before rendering or accepting selection.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`

### 2026-05-08 - Epic 3 slice 5 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: make the narrow ranking-artifact construction launch path canonical through explicit launch-profile metadata plus matching desktop readback.
- Status: shipped.
- Scope delivered:
  - backend `/construction/policies` rows now stamp one canonical `ranking_artifact_review_handoff_v1` launch profile with explicit `default` / `opt_in` / `excluded` policy status and explicit fixed `launch_top_n = 2`.
  - the canonical launch profile includes only `top_n_equal_weight_v1` as the single default and `top_n_linear_rank_weight_v1` as explicit opt-in; `top_n_inverse_rank_weight_v1` remains in the broader catalog but is explicitly excluded from the desktop launch profile.
  - desktop policy parsing now consumes launch-profile metadata fail-closed instead of relying on hardcoded launch-compatible policy ids or hardcoded default-policy selection.
  - ETF Ranking and Workspace persisted ranking browsers now show compact readback text for selected launch policy, default vs opt-in status, fixed `top_n = 2`, required `max_position_weight`, and optional `min_position_weight`, `max_turnover_weight`, and `max_trade_intent_count`.
- Guard impact:
  - makes the currently shipped ranking-to-construction launch boundary explicit without widening policy breadth, ranking-family breadth, request shape, or hard-constraint semantics.
  - blocks launch if catalog metadata is contradictory, incomplete, or no longer matches the canonical equal-weight-plus-linear-rank launch boundary.
- Contracts changed:
  - additive backend discovery metadata only: `/construction/policies` rows now include `launch_profile`.
  - desktop launch compatibility/default behavior is now derived from that backend metadata rather than hardcoded allowlists/defaults.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_routes.py`
  - `services/quant-engine/app/tests/test_construction_run_service.py`
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`

### 2026-05-07 - Epic 3 slice 2 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: add optional `min_position_weight` to the shipped ranking-to-construction bridge while keeping policy authority and scope narrow.
- Status: shipped.
- Scope delivered:
  - desktop `Review In Construction` entry points for ETF ranking and persisted replacement ranking now expose optional `Min Position Weight` beside the existing max field.
  - blank `min_position_weight` is treated as not requested and omitted from the construction request shape.
  - desktop uses one shared validation path for required `max_position_weight` and optional `min_position_weight`, including the local `min <= max` guard.
  - ETF Ranking workspace session state now persists the min field alongside the existing max field; the two persisted browsers keep min in local component state only.
- Guard impact:
  - broadens the visible bridge only one notch while preserving backend-authoritative policy selection, fixed `top_n = 2`, review-only construction semantics, and the two-family ranking allowlist.
  - keeps deeper feasibility with the backend and continues to leave turnover and trade-intent constraints out of scope.
- Contracts changed:
  - no backend contract changes.
  - desktop handoff now optionally serializes `hard_constraints.min_position_weight` only when the user explicitly supplies it.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n`, position-weight constraints, and hidden optional-constraint bridge.

### 2026-05-06 - Baseline epic alignment established

- Status: shipped roadmap update
- Added this living epic roadmap to track the four active epics and future slice sequencing.
- Set current priority order to `Epic 2 -> Epic 3 -> Epic 4`, with `Epic 1` treated as the foundational guardrail.
- Recorded the current shipped baseline from product-state, roadmap, and technical-roadmap docs.
- Next slice: move desktop ranking recent discovery onto generalized ranking-artifact recent flow.

### 2026-05-06 - Epic 2 slice 1 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: move desktop recent discovery onto generalized ranking-artifact recent flow for ETF ranking.
- Status: shipped.
- Scope delivered:
  - `EtfRankingPanel` recent-run listing now fetches generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=etf_ranking`.
  - Desktop keeps ETF-native `/strategy-lab/etf-ranking/artifacts/recent/metadata` only for peer-group filter options in this transitional slice.
  - Recent-run open remains on the existing generalized preflight/open handoff path.
- Guard impact:
  - strengthens the generalized ranking artifact discovery seam in visible desktop workflow without changing ranking methodology or widening supported artifact kinds.
- Contracts changed:
  - no backend contract changes.
  - desktop discovery consumer moved to the generalized recent contract for ETF rows.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: add read-only browsing/opening of persisted replacement ranking artifacts through the same generalized flow.

### 2026-05-06 - Epic 2 slice 2 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: add read-only browsing/opening of persisted replacement ranking artifacts through generalized ranking discovery/open.
- Status: shipped.
- Scope delivered:
  - Workspace `Candidate Idea` now includes a persisted replacement review browser backed by generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=intent_bound_etf_replacement_ranking`.
  - Desktop opens persisted replacement artifacts only through generalized preflight plus typed open handoff reuse.
  - Persisted replacement review renders read-only authoritative artifact context in Workspace without creating intent, mutating workflow state, widening storage, or launching replay.
  - Desktop validates discovery rows, preflight, open payload, and consumer handoff fail-closed before rendering persisted review state.
- Guard impact:
  - strengthens the generalized ranking artifact seam in visible Workspace review while keeping persisted replacement reopen explicitly context-only and non-promotable.
  - keeps `consumer_handoff` validation-only in this slice; no downstream actionability was added.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes generalized replacement recent/preflight/open contracts in Workspace Candidate Idea.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
- Next slice: generalized ranking-to-construction handoff review path.

### 2026-05-06 - Epic 2 slice 3 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: ETF ranking artifact to persisted construction review handoff through the canonical construction preflight/run path.
- Status: shipped.
- Scope delivered:
  - persisted ETF ranking artifacts now expose `Review In Construction` from `ETF Ranking`.
  - Workspace `Candidate Idea` now also exposes an ETF-only persisted ranking construction browser/action surface alongside the existing read-only replacement review surface.
  - both entry points route through canonical `/construction/ranking-artifacts/preflight/{artifact_id}` plus `/construction/run` and then reopen the returned persisted construction artifact through the existing artifact review flow.
  - desktop validates construction preflight contract identity and construction-run ranking lineage fail-closed before opening persisted construction review.
- Guard impact:
  - makes ranking-to-construction methodology visible through canonical persisted handoff review rather than ETF-local-only ranking inspection.
  - keeps this slice explicitly ETF-ranking-only for construction handoff; persisted replacement reviews remain read-only/context-only and do not imply construction eligibility.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes the shipped ETF construction ranking-artifact preflight/handoff boundary from both ETF Ranking and Workspace Candidate Idea.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden construction handoff beyond ETF ranking artifacts.

### 2026-05-06 - Epic 2 slice 4 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: broaden persisted construction handoff from ETF ranking artifacts to intent-bound ETF replacement ranking artifacts.
- Status: shipped.
- Scope delivered:
  - backend construction preflight and construction run now support exactly two ranking-artifact handoff kinds: `etf_ranking` and `intent_bound_etf_replacement_ranking`.
  - persisted replacement ranking artifacts now expose `Review In Construction` from Workspace Candidate Idea while keeping their ranking review explicitly read-only until that action is invoked.
  - replacement construction handoff reuses the same persisted construction artifact review path already used by ETF ranking handoff.
  - desktop and backend both validate replacement construction preflight identity, selected-candidate lineage, and persisted construction ranking lineage fail-closed.
- Guard impact:
  - broadens ranking-to-construction review one artifact family further without pretending all ranking artifacts are construction-eligible.
  - keeps the construction seam on an explicit two-kind allowlist rather than silently generalizing to arbitrary ranking artifacts.
  - preserves replacement review as context-only unless the user explicitly launches the separate construction review handoff.
- Contracts changed:
  - backend construction preflight/handoff contracts now support the additive `intent_bound_etf_replacement_ranking` construction handoff kind alongside the shipped ETF handoff kind.
  - desktop now consumes the widened two-kind construction handoff seam through the shared ranking-artifact construction helper.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_construction_run_service.py`
  - `services/quant-engine/app/tests/test_routes.py`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden construction handoff beyond ETF and intent-bound replacement artifacts.

### 2026-05-06 - Epic 2 slice 5 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: add explicit construction eligibility/readiness review for the two supported ranking families before construction launch.
- Status: shipped.
- Scope delivered:
  - backend construction preflight for `etf_ranking` and `intent_bound_etf_replacement_ranking` now returns additive typed `eligibility` plus optional `handoff` instead of treating all non-launchable cases as the same class.
  - desktop ETF and replacement construction browsers now surface construction-readiness state, disable `Review In Construction` when preflight says ineligible, and show canonical backend reason text.
  - unsupported families such as `cross_sectional_research_run` remain explicitly non-constructible; desktop shows only a static unsupported note and backend rejects construction preflight for that family fail-closed.
  - construction run still revalidates persisted artifact truth and lineage; preflight eligibility is a typed gate, not execution approval.
- Guard impact:
  - strengthens the selection-to-construction boundary by making construction-readiness explicit for the two supported ranking families rather than implicit in CTA behavior.

### 2026-05-07 - Epic 3 slice 1 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: stabilize the ranking-to-construction bridge around backend-authoritative policy selection plus one editable `max_position_weight` input.
- Status: shipped.
- Scope delivered:
  - desktop `Review In Construction` entry points for ETF ranking and persisted replacement ranking now load compatible construction policies from backend discovery instead of silently hardcoding `top_n_equal_weight_v1`.
  - desktop validates policy catalog rows fail-closed, auto-selects `top_n_equal_weight_v1` only when it is actually returned, and otherwise requires explicit user selection before construction launch.
  - desktop ranking-to-construction entry points now expose one shared editable `max_position_weight` input while still omitting other optional constraint knobs.
  - ranking-artifact construction handoff now requires caller-supplied selected policy and validates persisted construction run lineage for both ranking artifact provenance and requested policy provenance.
- Guard impact:
  - strengthens backend methodology authority in the visible ranking-to-construction workflow without widening supported ranking families, optimizer scope, or construction configuration breadth.
  - keeps the bridge explicitly review-only and parameter-light: fixed `top_n`, one editable `max_position_weight`, hidden optional constraints, and narrow portfolio lineage assumptions remain unchanged in this slice.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes `GET /construction/policies` as the authoritative source for construction policy identity on the ranking-to-construction bridge.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n`, single editable `max_position_weight`, and hidden optional-constraint bridge.

## Operational Update Rule

After every shipped slice or epic checkpoint:

1. update this file with status, delivered scope, and next slice
2. update `docs/product/current-product-state.md` if shipped behavior changed
3. update contracts or finance docs if methodology, trust semantics, or artifact boundaries changed
