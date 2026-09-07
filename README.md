# Quant Research Lab

Local-first desktop portfolio analytics for a systematic personal investor.
Import broker statements, inspect portfolio performance and holdings, and review
risk under explicit data-quality and trust disclosures. The app is decision
support only: it never places trades or moves money.

## What is in the product

- **Dashboard** — performance, benchmark comparison, monthly returns, risk
  summary, and replay disclosures.
- **Exposure** — holdings, concentration, sector and currency composition,
  factor analysis, drift, and correlation.
- **Risk** — stress scenarios, drawdown analysis, and return distribution.

The product distinguishes imported broker truth, current snapshot analytics,
synthetic history, and persisted imports. A result is marked `verified`,
`degraded`, `withheld`, or `unavailable`; missing evidence is never replaced
with a plausible value.

## Repository

```text
apps/desktop/             React, TypeScript, Vite, and Tauri desktop client
services/quant-engine/    Python FastAPI analytics engine
docs/                     Current product, architecture, finance, and contracts
data/                     Committed fixtures and reference data
scripts/                  Development, test, cache, and statement-refresh tools
```

## Documentation

- [Current product state](docs/product/current-product-state.md) — shipped
  user-facing scope and known limitations.
- [System architecture](docs/architecture/system-architecture.md) — runtime
  seams, routes, truth classes, and data flow.
- [Financial methodology](docs/finance/financial-methodology.md) — implemented
  formulas and trust semantics.
- [Testing architecture](docs/architecture/testing-architecture.md) —
  deterministic fixture and verification model.
- [Contracts](docs/contracts/) — backend-to-desktop field traceability.
- [Technical debt register](docs/tech-debt-register.md) — current actionable
  engineering issues only.

Historical implementation plans and delivery tickets are intentionally kept in
Git history, not maintained as active repository documentation.

## Development

```bash
# Start backend (:8000) and desktop web server (:5173)
python scripts/run_dev.py

# Canonical, deterministic project verification
python scripts/run_all_tests.py

# Individual checks
cd services/quant-engine && pytest
cd apps/desktop && npx vitest run
cd apps/desktop && npx tsc --noEmit
```

The canonical test run regenerates frozen dashboard fixtures, runs backend and
frontend tests, type-checks TypeScript, and enforces the strict dead-code gate.
It does not require live market-data access.

To refresh the committed market-data fixture after replacing `docs/IB2026.csv`,
run `python scripts/refresh_statement.py` with `FMP_API_KEY` configured. Read
the statement-refresh section in the testing architecture first.
