# Quant Research Lab

This is a **local-first, deterministic, auditable** portfolio analytics
application for systematic personal investing. It imports broker portfolios,
computes analytics under explicit financial guardrails, and never places trades
or moves money.

## Non-negotiable guardrails

1. **Methodology traceability** — every displayed financial metric has one
   documented formula and one executable code path.
2. **Truth-class separation** — never mix broker truth, snapshot analytics,
   synthetic history, and persisted imports in one claim or response.
3. **Trust over fabrication** — preserve `verified > degraded > withheld >
   unavailable`; do not invent values or turn `withheld` into `unavailable`.
4. **No execution** — this product is decision support only.

Before changing analytics, financial formulas, or trust-state logic, read
`docs/finance/financial-methodology.md`, update the relevant contract, and add
or update regression tests in the same change.

## Product surface

The desktop has three tabs:

| Tab | Purpose |
|---|---|
| Dashboard | Performance, benchmark comparison, monthly returns, risk summary, and replay disclosures. |
| Exposure | Holdings, concentration, sector/currency composition, factors, drift, and correlation. |
| Risk | Stress scenarios, drawdown analytics, and return distribution/VaR. |

Read `docs/product/current-product-state.md` for exact shipped scope and known
limitations. Ranking, construction, optimizer, backtesting, and monitoring are
not current product surfaces.

## Canonical documentation

| Need | Read |
|---|---|
| Current product scope | `docs/product/current-product-state.md` |
| Financial formulas and trust rules | `docs/finance/financial-methodology.md` |
| Runtime seams, routes, and truth classes | `docs/architecture/system-architecture.md` |
| Test model and statement refresh | `docs/architecture/testing-architecture.md` |
| Backend ↔ TypeScript ↔ UI traceability | `docs/contracts/<area>-fields.md` |
| Current actionable engineering work | `docs/tech-debt-register.md` |
| Module vocabulary | `CONTEXT.md` |

Historical implementation tickets and roadmaps are preserved in Git history,
not maintained as active documentation.

## Stack and layout

| Layer | Technology |
|---|---|
| Desktop | React 18, TypeScript, Vite, Tauri 2 |
| Engine | Python, FastAPI, Pydantic, Uvicorn |
| Market data | FMP with explicit yfinance fallback |
| Testing | Pytest, Vitest, TypeScript, ruff, vulture, knip |

```text
apps/desktop/src/
  app/                  App shell, API base, local workspace persistence
  features/portfolio/   Dashboard, exposure, risk components and API adapter
services/quant-engine/app/
  api/routes/           HTTP routes; register in app/api/main.py
  analytics/            Portfolio math and statistical models
  clients/              FMP and Yahoo Finance data clients
  core/                 Settings, caching, logging, shared constants
  domain/               Ledger semantics
  importers/            Interactive Brokers, Freedom24, and ESPP parsers
  instruments/          Registry and sector/identity resolution
  schemas/              Pydantic contract source of truth
  services/             Import, data, analytics, history, and trust orchestration
  tests/                Pytest suite and frozen fixtures
```

## Engineering rules

- **Schemas first:** update `app/schemas/` before routes and services. Mirror
  contract changes in desktop types and `docs/contracts/`.
- **Thin frontend:** components render engine results; financial calculations
  belong in the engine.
- **Market-data seam:** use `app/services/market_data.py` and its clients;
  routes and analytics must not call vendors directly.
- **Routes:** add a route module, register it in `app/api/main.py`, and add
  route tests. Keep route code thin.
- **Trust rendering:** display degraded, withheld, and unavailable states
  honestly; never render a missing financial value as zero.
- **Local security boundary:** import routes are localhost/single-user only.
  Revisit their unauthenticated file-path behavior before remote deployment.

## Development and verification

```bash
# Start backend (:8000) and frontend (:5173)
python scripts/run_dev.py

# Canonical full suite
python scripts/run_all_tests.py

# Targeted checks
cd services/quant-engine && pytest
cd apps/desktop && npx vitest run
cd apps/desktop && npx tsc --noEmit
python scripts/detect_deadcode.py --strict
```

`run_all_tests.py` is the acceptance command. It regenerates deterministic
dashboard goldens, runs backend/frontend tests, type-checks TypeScript, and
enforces dead-code checks. Do not bypass a failed test or commit gate.

The frozen suite does not require network access. When replacing
`docs/IB2026.csv`, read the statement-refresh workflow in
`docs/architecture/testing-architecture.md` and use
`python scripts/refresh_statement.py` with `FMP_API_KEY` configured.

## Truth classes

| Class | Meaning |
|---|---|
| Broker Truth | Statement-derived positions, balances, and ledger activity. |
| Snapshot Analytics | Calculations over the current portfolio state. |
| Synthetic History | Current holdings × historical market data; not broker replay. |
| Persisted Imports | Desktop-local import snapshots and metadata. |

When unsure, prefer explicit provenance, a narrower claim, or withholding the
output. Financial plausibility is never enough.
