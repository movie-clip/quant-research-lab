# Quant Research Lab Roadmap

This file is future-looking only.
Shipped-state detail belongs in `docs/product/current-product-state.md`.
Living epic execution status belongs in `docs/product/epic-roadmap.md`.

## Product Thesis

The product should keep evolving into a deterministic portfolio research and decision workbench for:
- portfolio intelligence and risk review
- systematic ranking
- rule-based construction
- hypothetical replay and improvement review
- optimizer-assisted refinement under clear guardrails
- overlays and ongoing monitoring

The product should stay focused on transparent, auditable investing workflows rather than black-box prediction.

## Core Product Principles

1. Financial outputs must stay methodologically explicit.
2. Every displayed metric must trace to one engine output and one code path.
3. Truth classes, trust states, degradation, and withholding must remain explicit.
4. Ranking and construction rules remain primary; optimization is a constrained refinement layer.
5. The UI should present decision-grade outputs, not debug dumps.

## Remaining Milestones

### 1. Generalized Ranking Platform Expansion

Goal:
- extend the shipped ETF ranking artifact flow into a broader first-class ranking platform capability

Remaining work:
- broaden beyond the current ETF-heavy slices and seeded replacement flows
- support richer universes, eligibility filters, and reusable score configurations
- standardize generalized ranking workflows without treating the shipped ETF artifact/discovery path as still pending

### 2. Construction Expansion

Goal:
- extend the shipped persisted construction engine beyond its current narrow policy set

Remaining work:
- add more weighting policies beyond `top_n_equal_weight_v1`
- add richer hard and soft constraint families
- deepen ranking-to-construction handoff and implementation diagnostics

### 3. Portfolio Improvement Expansion

Goal:
- make baseline-vs-candidate review the clearest end-to-end product workflow

Remaining work:
- broaden proposal review and comparison flows beyond the shipped proposal-family PM review and same-family sibling comparison slices
- extend the shipped PM-first saved-proposal family inbox and active-thesis cross-family PM review queue into broader cross-family review and ranking workflows without weakening persisted-artifact authority
- improve PM-first summarization across replay, diagnostics deltas, and proposal artifacts
- connect persisted construction and optimizer workflows more directly into Workspace review

### 4. Overlay and Monitoring Expansion

Goal:
- extend the shipped `benchmark_trend_overlay_v1` overlay and persisted monitor-definition slice into broader ongoing discipline tools

Remaining work:
- add broader alert workflows, observation discovery surfaces, and review history on top of the shipped narrow monitor-definition observation boundary
- broaden monitoring beyond the shipped active alert-episode inbox, definition-scoped persisted alert-episode history index, definition-scoped alert-review timeline, and latest persisted alert-episode lifecycle for one persisted `monitor_definition_id`
- extend the shipped hysteresis and degraded-monitor contract into broader monitoring surfaces and future monitor families
- support broader overlay and monitor families, including benchmark-relative, factor-drift, and concentration-drift coverage

### 5. Optimizer Expansion

Goal:
- keep optimization bounded, explainable, and subordinate to rule-based construction

Remaining work:
- add additional optimizer objectives and constraint families
- compare optimizer candidates against persisted rule-based baselines more directly
- expand optimizer workflows without blurring hypothetical outputs into applied portfolio truth

### 6. Research Expansion

Goal:
- broaden the platform into a more complete personal quant research lab

Remaining work:
- expand reusable research templates and datasets
- broaden universe coverage and cross-sectional research depth
- support stronger validation and walk-forward style research where realistic

## Immediate Priorities

1. generalize ranking beyond the shipped ETF artifact and discovery flow
2. add more construction policies and richer constraints on top of the shipped persisted engine
3. improve Workspace integration for persisted construction and optimizer handoff review
4. expand overlays and monitoring after core workflow clarity stays intact
5. grow optimizer breadth without weakening truth separation

## Documentation Rule

Any financially meaningful change must update:
- `docs/finance/financial-methodology.md`
- relevant field inventory docs
- tests that lock down formulas, trust semantics, degradation, or withholding behavior

Any product-shape change should keep this file future-looking and keep shipped-state detail in `docs/product/current-product-state.md`.
