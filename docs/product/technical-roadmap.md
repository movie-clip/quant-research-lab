# Quant Research Lab Technical Roadmap

This file is technical and future-looking only.
Current shipped boundaries belong in `docs/product/current-product-state.md`.
Living epic execution status belongs in `docs/product/epic-roadmap.md`.

## Goal

Continue evolving the repo into a local-first quant research lab for imported portfolio truth, systematic ranking, deterministic construction, hypothetical optimizer workflows, and financially auditable replay.

## Product Principles

1. Deterministic engines own portfolio math and research outputs.
2. Every material result must carry methodology, provenance, and truth separation.
3. Persisted artifacts must be reproducible from versioned inputs and explicit references.
4. The frontend stays thin on finance logic.
5. Optimization remains constrained and explainable.

## Target Architecture

### Backend engine families

- truth and data engines
- portfolio intelligence engines
- ranking engines
- construction and constraint engines
- replay and improvement engines
- optimizer preview and handoff engines
- overlay and monitoring engines

### Canonical artifact expectations

Persisted research and decision artifacts should converge on the same shape:
- stable artifact identity
- immutable payload semantics
- explicit upstream references
- methodology and policy ids
- trust and return-basis attestation where financially required
- validation and fail-closed loading behavior

## Remaining Technical Work

### 1. Generalized Ranking System Expansion

Remaining work:
- generalize ranking inputs beyond the currently shipped ETF ranking and intent-bound ETF replacement artifact/discovery slice
- support configurable but versioned component sets, filters, and composite weighting
- converge future non-ETF ranking families on shared artifact, fail-closed validation/open handoff, loading, and discovery rules beyond the current shipped ETF ranking and intent-bound replacement boundary

### 2. Construction Engine Expansion

Remaining work:
- broaden persisted construction policy coverage beyond the current narrow catalog and canonical launch profile, including configurable `top_n` support
- add richer constraint models, turnover logic, and implementation diagnostics
- standardize policy execution, provenance capture, and replay handoff across persisted and review-oriented construction paths

### 3. Portfolio Improvement Workflow Expansion

Remaining work:
- tighten Workspace integration across ranking, persisted construction, optimizer handoff, replay, and proposal artifacts
- simplify review contracts so lineage, trust, and withholding remain visible without excessive payload noise
- keep persisted construction reopen lineage fail-closed now that canonical launch context is explicit across ranking artifact identity/schema, ranking lineage, current portfolio identity/timestamp, policy identity/definition, and fixed `top_n`
- broaden saved proposal review beyond the shipped canonical PM-first family inbox, active-thesis cross-family PM review queue, proposal-family PM review, and same-family sibling comparison slices while preserving backend-rooted persisted-artifact discovery contracts

### 4. Overlay and Monitoring Expansion

Remaining work:
- add broader overlay specs and monitor families beyond the shipped `benchmark_trend_overlay_v1` and evidence-only `data_quality_monitor_v1` monitor-definition artifact paths
- extend persisted monitor observations, latest-observation-alert-inbox review intake, recovered-alert-review discovery, active-alert-episode-inbox discovery, definition-scoped alert-episode history retrieval, definition-scoped alert-review timeline retrieval, and evaluation-history inspection beyond the shipped narrow monitor-definition create/get/list/catalog/recent/latest-observation-alert-inbox/alert-history-queue/recovered-alert-review-queue/active-alert-episode-inbox/evaluate/observation contract family, which already includes additive read-only persisted retrieval for benchmark-trend and data-quality definitions at `GET /backtests/monitor-definitions/alert-history-queue`, `GET /backtests/monitor-definitions/recovered-alert-review-queue`, `GET /backtests/monitor-definitions/active-alert-episode-inbox`, `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history`, `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline`, and additive read-only evaluation-history routes
- add broader monitoring workflows and overlay coverage beyond the current narrow review-only `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` boundaries while preserving the shipped alert lifecycle, persisted alert-episode lifecycle semantics, degraded/unavailable handling, hysteresis transitions, and definition-scoped review semantics

### 5. Optimizer Expansion

Remaining work:
- expand objective coverage beyond the current benchmark-distance-oriented path
- add broader constraint and diagnostic coverage while preserving explicit handoff lineage
- improve comparison between optimizer outputs and rule-based construction baselines
- keep all optimizer outputs hypothetical unless and until a separate execution boundary exists

### 6. Research and Data Expansion

Remaining work:
- broaden dataset coverage, universe definitions, and reusable templates
- strengthen cross-sectional research infrastructure and validation tooling
- expand PIT alpha inputs beyond the current narrow `alpha_quality_v1` coverage contract

## Financial Accuracy Requirements

These remain permanent technical requirements:
- adjusted-close or stronger total-return-aware inputs for return-based analytics where required
- explicit trust, degradation, withholding, and unavailability semantics on financially meaningful contracts
- finite-only numeric evidence on admission/review contracts; non-finite imported inputs must degrade or become unavailable rather than serialize `NaN`/`Infinity`
- formula traceability from UI field to schema field to implementation
- persisted return-basis evidence and replay-output suppression rules where trust is narrower than the computed engine surface
- fail-closed behavior for malformed persisted artifacts or contradictory lineage

## Foundation Status

The backend engine families (ranking, construction, construction-constraint, replay, optimizer, monitoring) are functionally complete for the MVP golden path. The immediate technical work is **workflow integration and UX clarity**, not engine breadth.

## Immediate Priorities

1. Fix the end-to-end golden path: tab order, Workspace candidate UX, "Review in Construction" broken workflow, replay comparison output (Epic 5)
2. Dashboard portfolio-weakness signals: concentration, factor tilt, benchmark-relative performance (Epic 6)
3. Decision persistence: saved proposal rationale, drift monitoring against saved plan (Epic 7)

## Deferred (explicitly not priority until Epic 5–7 are done)

- Additional construction policies (inverse-vol, risk-parity)
- Full index ingestion (Russell 1000 complete, Russell 2000, MSCI EAFE)
- Optimizer objective expansion
- Cross-sectional research expansion
- Additional monitor families

## Definition of Done for the Pivot

The pivot is successful when the project can:
- import and reconstruct portfolio truth reliably
- rank a chosen universe reproducibly
- construct candidate allocations from persisted rules and constraints
- compare baseline vs candidate through replay with explicit provenance and trust semantics
- evaluate optimizer outputs through explicit hypothetical handoff boundaries
- monitor ongoing portfolio discipline with first-class persisted workflows that extend the shipped monitor-definition artifact boundary
