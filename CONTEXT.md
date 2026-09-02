# Context — domain & module vocabulary

Names for the seams in this codebase. Use the term as spelled here in issue
titles, story text, test names, and refactor proposals; don't drift to a
synonym.

This file covers **module and seam vocabulary** only. It sits on top of the
canonical doc map in `CLAUDE.md`, which stays authoritative for everything it
covers:

| For | Read |
|---|---|
| Financial formulas | `docs/finance/financial-methodology.md` |
| Backend seams, routes, truth classes | `docs/architecture/system-architecture.md` |
| Field traceability (backend ↔ TS ↔ UI) | `docs/contracts/<area>-fields.md` |
| Current epic + slice log | `docs/product/epic-roadmap.md` |
| Dead-code + improvement backlog | `docs/tech-debt-register.md` |

## Truth classes

Defined in `CLAUDE.md` and `docs/architecture/system-architecture.md`. Named
here because the module vocabulary below refers to them: **Broker Truth**,
**Snapshot Analytics**, **Synthetic History**, **Persisted Imports**. Trust
ladder: `verified > degraded > withheld > unavailable`.

## Modules

### synthetic-history construction

The reconstruction of a daily portfolio-state series from **current holdings ×
historical market data** — the Synthetic History truth class. Lives in
`services/synthetic_history.py` (`build_synthetic_snapshot_history_states`,
`..._with_coverage`) and is consumed by every diagnostics-family engine
(diagnostics, attribution, correlation, distribution, drawdown, stress). It is
*not* the imported ledger replay — that is Broker Truth, built in
`analytics/performance.py` + `engine/portfolio_state.py`.

### factor model

The statistical (PCA-style) factor decomposition of a return series: fit,
factor orthogonalisation, rolling loadings, model reliability. The internals
(`_fit_factor_model`, `_orthogonalize_factors_window`, the factor definitions
and proxy maps) live in `analytics/factor_model.py`; the response-shaping entry
points that call them stay in `analytics/risk.py`. Methodology:
`financial-methodology.md` §Statistical Factor Model.

### trust gate

The decision "is this output trustworthy enough to publish, and at what trust
level" — section-trust rollups, the output-admission policy per section
(drawdown, investor-economics, benchmark-relative), price-history presence, and
return-basis classification. Lives in `services/trust_gate.py`; the Dashboard
history engine and the Diagnostics engine both call it. Each engine keeps its
own `SectionTrust` builder function (the two sections' shapes differ); only the
byte-identical primitives are shared.

### import bootstrap

The single flow that turns broker statement paths (or a snapshot request) into
an `ImportedBootstrapResponse` — statement import, exposure, history context,
response assembly. Lives in `services/import_engine.py`; the response-assembly
step is a private helper, not its own module.
