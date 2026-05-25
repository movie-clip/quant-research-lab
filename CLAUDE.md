# quant-research-lab

A **local-first, deterministic, auditable** decision-support platform for systematic personal investing. The product imports broker portfolios, computes deterministic analytics, and presents holdings analysis under explicit financial guardrails.

> The product is **not** a black-box prediction engine. It is a research workbench where every displayed financial number must be explainable, traceable, and reproducible.

## ⚠️ Critical: financial accuracy comes first

**If the math or financial methodology is wrong, nothing else matters.** Before changing any analytics, factor formula, or trust-state logic:

1. **Read `docs/finance/financial-methodology.md`** — the canonical source of truth for every implemented formula
2. **Update tests in the same pass** — every methodology change must include or update regression tests
3. **Surface trust state explicitly** — never fabricate, never silently fallback, never collapse `withheld` into `unavailable`

The four hard guardrails (in priority order):

1. **Methodology traceability** — every UI metric maps to one engine formula and one code path. If you can't trace it, don't ship it.
2. **Truth-class separation** — broker truth, snapshot analytics, synthetic history, and persisted imports are distinct. Never mix them in a single response.
3. **Trust semantics over fabrication** — `verified > degraded > withheld > unavailable`. Surface the level; don't fill in plausible values.
4. **No execution** — the system never places trades or moves money.

## Product: two tabs

The product has two tabs: **Dashboard** and **Exposure**.

| Tab | What it shows |
|---|---|
| Dashboard | Portfolio performance — time-weighted returns, benchmark comparison, monthly returns, risk metrics, investor economics |
| Exposure | Holdings breakdown — sector exposure, ETF look-through, market overlap, factor model |

Exposure also shows a **vs Market drift panel** at the top: rolling portfolio return vs a selectable benchmark (SPY default) for 1m, 3m, 6m, 12m, and since-import windows.

## Where to find what (canonical doc map)

| Doc | Purpose |
|---|---|
| `README.md` | Public-facing project overview |
| `CLAUDE.md` (this file) | Agent onboarding: project identity, guardrails, conventions |
| `docs/product/epic-roadmap.md` | Epic snapshot + slice log |
| `docs/product/prd/epic-8-reset-to-analysis-core.md` | Active PRD |
| `docs/product/stories/` | User stories — one file per story |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory |
| `docs/finance/financial-methodology.md` | Source of truth for every financial formula |
| `docs/architecture/system-architecture.md` | Backend seams, route inventory, truth class semantics |
| `docs/contracts/*.md` | Field inventory — backend ↔ TS type ↔ UI traceability |
| `.claude/skills/build-story/SKILL.md` | Build-story skill |
| `.claude/skills/write-story/SKILL.md` | Write-story skill |

## Tech Stack

| Layer | Tech |
|-------|------|
| Desktop | React 18 + TypeScript + Vite, Tauri 2 (Rust shell) |
| Quant Engine | Python FastAPI + Uvicorn + Pydantic |
| Market Data | FMP (Financial Modeling Prep) via local cache |
| Testing | Vitest (frontend), Pytest (backend) |

## Repository Layout

```
apps/desktop/src/
  app/                  # Core state, storage, App shell, routing
  features/
    portfolio/          # Holdings, exposure, diagnostics, dashboard
    market-data/        # Market data integration
    settings/

services/quant-engine/app/
  api/routes/           # FastAPI routes: exposure, dashboard_history, diagnostics, imports, market_data, health
  analytics/            # Portfolio analytics (returns, drawdown, exposure, risk)
  clients/              # FMP market data client (with caching)
  core/                 # Settings, logging, caching infrastructure
  domain/               # Ledger + accounting domain model
  importers/            # Broker parsers (Interactive Brokers, Freedom24, ESPP)
  instruments/          # Instrument registry
  schemas/              # Pydantic models (CONTRACT SOURCE OF TRUTH)
  services/             # Business logic services (dashboard, diagnostics, exposure, drift)
  tests/                # Pytest suite

docs/
  product/
    prd/                # PRDs — one per epic
    stories/            # User stories
    epic-roadmap.md     # Epic snapshot + slice log
    current-product-state.md  # Shipped-state inventory
  finance/              # Financial methodology
  architecture/         # System architecture + truth classes
  contracts/            # Field inventory docs (backend ↔ TS ↔ UI)
```

## Architecture: Truth Classes

| Class | Description |
|-------|-------------|
| **Broker Truth** | Imported positions/ledger from broker statements |
| **Snapshot Analytics** | Point-in-time computed metrics from current holdings |
| **Synthetic History** | Reconstructed historical returns from current holdings + market data |
| **Persisted Imports** | Saved import artifacts (content-addressed, immutable) |

Trust ladder: `verified > degraded > withheld > unavailable`. Never fabricate or fill missing data — surface the trust level instead.

## Development Commands

```bash
# Start both dev servers (backend on :8000, frontend on :5173)
python scripts/run_dev.py

# Tests — canonical entrypoint
python scripts/run_all_tests.py             # all
cd services/quant-engine && pytest          # backend
cd apps/desktop && npx vitest run           # frontend
cd apps/desktop && npx tsc --noEmit         # type-check

# FMP cache management
python scripts/manage_cache.py
```

## Backend Conventions (`services/quant-engine/`)

- **Schemas first**: `app/schemas/` is the contract source of truth. Change schemas before routes or business logic.
- **Market data via FMP client**: `app/clients/fmp.py` handles caching. Never call FMP directly from routes.
- **Trust semantics**: Every field that can be missing carries a trust level. Never fabricate.
- **Route pattern**: Check existing routes in `app/api/routes/` first. Schemas → service → route → register in `app/main.py` → tests.

## Frontend Conventions (`apps/desktop/`)

- **Types mirror backend schemas exactly**: When a Pydantic schema changes, update the desktop TS types and the matching `docs/contracts/<area>-fields.md` in the same pass.
- **Trust levels rendered visibly**: Never silently suppress `withheld` or `degraded` — show the badge.
- **No fabrication**: If data is `null`/`unavailable`, render the unavailable state, never zero or placeholder.
- **Frontend stays thin on finance**: No portfolio math in components. Ask the engine.

## Delivery model

Work is delivered as **PRD → User Story → Ticket**. See `docs/product/stories/README.md` for the story index.

Two project skills drive the workflow:

| Skill | When to use |
|---|---|
| **`write-story`** | Feature idea → complete, ticketed User Story file |
| **`build-story`** | Implement a ticketed story end-to-end |

## When in doubt

1. **For methodology questions** → `docs/finance/financial-methodology.md`
2. **For "what's shipped today"** → `docs/product/current-product-state.md`
3. **For "what's the next story"** → `docs/product/stories/` + the `build-story` skill
4. **For "what's the scope of this epic"** → `docs/product/prd/epic-8-reset-to-analysis-core.md`
5. **For "where are we overall"** → `docs/product/epic-roadmap.md`
6. **For "where does this field come from"** → `docs/contracts/<area>-fields.md`
