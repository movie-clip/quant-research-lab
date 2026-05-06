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
| 2. Ranking and selection methodology guard | Generalize ranking into a broader methodology platform with explicit selection guardrails and artifact-backed reuse | Active epic | Read-only browsing/opening of persisted replacement ranking artifacts | Generalized ranking-to-construction handoff review path | 2026-05-06 |
| 3. Construction and optimizer methodology guard | Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts | Guardrails strong; breadth still narrow | No active slice | Drive desktop policy selection from backend construction policy catalog | 2026-05-06 |
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
- `Active`: add read-only browsing/opening of persisted replacement ranking artifacts through the same generalized flow.
- Next: generalized ranking-to-construction handoff review path.

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

### Target state

- Desktop uses authoritative backend construction policy discovery and stronger ranking-to-construction handoff.
- Optimizer review compares against stronger rule-based baselines under the same explicit provenance rules.

### Open gaps

- Desktop policy selection is still not fully driven by backend catalog authority.
- Ranking-to-construction handoff is not yet the clearest canonical workflow.
- Policy and constraint breadth remain narrow.

### Planned slices

- Drive desktop construction policy selection from `/construction/policies`.
- Add ranking-artifact to construction handoff through shipped backend routes.

### Dependencies

- Depends on Epic 2 generalization.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/backtest-fields.md`
- construction and optimizer tests under `services/quant-engine/app/tests`

### Exit criteria

- Construction and optimizer workflows consume stronger generalized upstream ranking artifacts and preserve explicit review basis throughout.

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

## Operational Update Rule

After every shipped slice or epic checkpoint:

1. update this file with status, delivered scope, and next slice
2. update `docs/product/current-product-state.md` if shipped behavior changed
3. update contracts or finance docs if methodology, trust semantics, or artifact boundaries changed
