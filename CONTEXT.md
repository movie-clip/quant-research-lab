# Context — domain and module vocabulary

Use these names in code, tests, and technical discussion. This glossary
complements the canonical documentation map in `CLAUDE.md`.

| Topic | Source of truth |
|---|---|
| Financial formulas and trust semantics | `docs/finance/financial-methodology.md` |
| Runtime seams, routes, and truth classes | `docs/architecture/system-architecture.md` |
| Backend ↔ TypeScript ↔ UI fields | `docs/contracts/<area>-fields.md` |
| Current user-facing scope | `docs/product/current-product-state.md` |
| Open engineering work | `docs/tech-debt-register.md` |

## Truth classes

- **Broker Truth** — statement-derived positions, balances, and ledger history.
- **Snapshot Analytics** — calculations over the current portfolio state.
- **Synthetic History** — a reconstructed daily series from current holdings
  and historical market data; not imported replay.
- **Persisted Imports** — desktop-local, immutable import snapshots and metadata.

Trust order: `verified > degraded > withheld > unavailable`.

## Module vocabulary

### Synthetic-history construction

`services/quant-engine/app/services/synthetic_history.py` builds the daily
current-holdings × market-data series consumed by diagnostics-family engines.

### Factor model

`services/quant-engine/app/analytics/factor_model.py` contains statistical
factor definitions, orthogonalisation, and model fitting. `analytics/risk.py`
owns response shaping.

### Trust gate

`services/quant-engine/app/services/trust_gate.py` determines whether dashboard
and diagnostics outputs are publishable and at which trust level.

### Import bootstrap

`services/quant-engine/app/services/import_engine.py` turns statement paths or
snapshot requests into an `ImportedBootstrapResponse`: import, exposure,
history context, and response assembly.
