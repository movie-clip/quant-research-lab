# Quant Research Lab Technical Roadmap

This file is technical and future-looking only.
Current shipped boundaries belong in `docs/product/current-product-state.md`.

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

### 1. Ranking System Expansion

Remaining work:
- persist ranking runs with stable ids, reproducibility metadata, and artifact loading paths
- generalize ranking inputs beyond the current ETF-focused and replacement-intent flows
- support configurable but versioned component sets, filters, and composite weighting

### 2. Construction Engine Expansion

Remaining work:
- add more persisted construction policies beyond `top_n_equal_weight_v1`
- add richer constraint models, turnover logic, and implementation diagnostics
- standardize policy execution, provenance capture, and replay handoff across persisted and review-oriented construction paths

### 3. Portfolio Improvement Workflow Expansion

Remaining work:
- tighten Workspace integration across ranking, persisted construction, optimizer handoff, replay, and proposal artifacts
- simplify review contracts so lineage, trust, and withholding remain visible without excessive payload noise
- broaden saved proposal review and comparison beyond the current narrow slices

### 4. Overlay and Monitoring Expansion

Remaining work:
- add broader overlay specs beyond `benchmark_trend_overlay_v1`
- persist monitor definitions, observations, and review history
- formalize alert thresholds, hysteresis, and degraded/unavailable semantics across monitoring outputs

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
- formula traceability from UI field to schema field to implementation
- persisted return-basis evidence and replay-output suppression rules where trust is narrower than the computed engine surface
- fail-closed behavior for malformed persisted artifacts or contradictory lineage

## Immediate Priorities

1. persist generalized ranking runs and reproducibility metadata
2. broaden persisted construction policies and constraints
3. improve shared artifact-loading, validation, and provenance rules across construction and optimizer workflows
4. expand monitoring persistence and alert semantics
5. extend optimizer breadth without weakening truth separation or replay attestation rules

## Definition of Done for the Pivot

The pivot is successful when the project can:
- import and reconstruct portfolio truth reliably
- rank a chosen universe reproducibly
- construct candidate allocations from persisted rules and constraints
- compare baseline vs candidate through replay with explicit provenance and trust semantics
- evaluate optimizer outputs through explicit hypothetical handoff boundaries
- monitor ongoing portfolio discipline with first-class persisted workflows
