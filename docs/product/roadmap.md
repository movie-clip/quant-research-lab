# Quant Research Lab Roadmap

This file is future-looking only.
Shipped-state detail belongs in `docs/product/current-product-state.md`.
Living epic execution status belongs in `docs/product/epic-roadmap.md`.

## Product Thesis

A local-first portfolio research workbench for a systematic personal investor.
The product should help answer three questions, in order:

1. **What do I have and how is it doing?** — portfolio clarity
2. **What should I change, and would it actually be better?** — improvement proposal
3. **Am I still on plan?** — decision tracking

Every output must be transparent, auditable, and explainable. The product is
not a black-box signal generator — it is a research workbench where the
researcher stays in control and every displayed number is traceable.

## Foundation (Complete)

The first four epics established the technical foundation. They are complete.

| Epic | What it established |
|---|---|
| 1. Imported-portfolio truth | Broker import, trust semantics, admission evidence, reconciliation guardrails |
| 2. Ranking platform | Generalized ranking artifacts, ETF + generic ranking, persisted discovery |
| 3. Construction engine | Deterministic construction, constraints, configurable top-N, ranking handoff |
| 4. Monitoring infrastructure | Persisted monitor definitions, alert workflows, benchmark-trend + data-quality families |

Future work builds usable workflows on top of this foundation — **not more
infrastructure breadth**.

## MVP Epics

### Epic 5: Usable Core Flow

**Goal:** A portfolio researcher can go from "I imported my portfolio" to "here
is a proposed better allocation with a clear improvement case" without confusion
or broken steps.

The primary golden path is:

```
Dashboard  →  Workspace  →  Pick ranking artifact  →  Review In Construction
  →  Replay  →  Clear before/after comparison  →  Save proposal
```

**Success signals:**
- App tab order matches the workflow — Dashboard, then Workspace, then research tools
- Workspace candidate section is self-explanatory — a researcher who has never used the product can understand what they are selecting
- "Review in Construction" works end-to-end from the Workspace candidate browser
- Replay output shows a clear before/after summary (returns, drawdown, turnover cost) — not a methodology dump

### Epic 6: Portfolio Clarity

**Goal:** The Dashboard tells the researcher where their portfolio is weak —
not just what they hold.

**Success signals:**
- Concentration risk is visible at a glance: single-name cap, sector weight, largest positions
- Factor tilts are summarized: is the portfolio biased toward momentum / value / quality?
- Performance vs benchmark is clearly stated with trust level (not buried in a methodology section)
- The researcher can see an opportunity before opening Workspace

### Epic 7: Decision Capture & Tracking

**Goal:** The researcher can record investment decisions and track whether the
portfolio is still following the plan.

**Success signals:**
- A saved proposal records the rationale alongside the quant evidence
- Monitoring surfaces when the portfolio drifts materially from the saved plan
- The researcher can review a past decision: "I proposed this in March, here is what happened"

## Explicitly Deferred

The following are intentionally out of scope until the MVP golden path (Epics 5–7) is complete and usable:

- Additional construction policies (inverse-volatility, risk-parity)
- Full Russell 1000 ingestion; Russell 2000; MSCI EAFE
- Optimizer expansion beyond the shipped hypothetical preview
- Cross-sectional research expansion
- Broader monitoring workflows: broaden monitoring beyond the shipped active alert-episode inbox, definition-scoped persisted alert-episode history index, definition-scoped alert-review timeline, and latest persisted alert-episode lifecycle for one persisted `monitor_definition_id`
- Additional monitor families beyond `benchmark_trend_overlay_v1` and `data_quality_monitor_v1`
- Additional ranking factors beyond the 19 shipped

## Core Principles (unchanged)

1. Financial outputs must stay methodologically explicit.
2. Every displayed metric must trace to one engine output and one code path.
3. Trust classes, trust states, degradation, and withholding must remain explicit.
4. Ranking and construction rules remain primary; optimization is a constrained refinement layer.
5. The UI must present decision-grade outputs — not debug dumps or methodology walls of text.
6. Desktop stays thin on finance logic. The engine owns the math.

## Documentation Rule

Any financially meaningful change must update:
- `docs/finance/financial-methodology.md`
- relevant field inventory docs
- tests that lock down formulas, trust semantics, degradation, or withholding behavior

Any product-shape change should keep this file future-looking and keep
shipped-state detail in `docs/product/current-product-state.md`.
