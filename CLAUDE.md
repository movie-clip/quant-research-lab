# quant-research-lab

A **local-first, deterministic, auditable** decision-support platform for systematic personal investing. The product imports broker portfolios, computes deterministic analytics, and supports a rank → construct → replay → optimize workflow under explicit guardrails.

> The product is **not** a black-box prediction engine. It is a research workbench where every displayed financial number must be explainable, traceable, and reproducible.

## ⚠️ Critical: financial accuracy comes first

**If the math or financial methodology is wrong, nothing else matters.** Before changing any analytics, factor formula, replay basis, or trust-state logic:

1. **Read `docs/finance/financial-methodology.md`** — the canonical source of truth for every implemented formula
2. **Invoke the `portfolio-analytics` skill** if the change touches return construction, drawdown, volatility, benchmark separation, or factor analytics
3. **Invoke the `financial-research` skill** if the change introduces a new factor, normalization scheme, or universe definition — cite academic precedent
4. **Update tests in the same pass** — every methodology change must include or update regression tests
5. **Surface trust state explicitly** — never fabricate, never silently fallback, never collapse `withheld` into `unavailable`

The four hard guardrails (in priority order):

1. **Methodology traceability** — every UI metric maps to one engine formula and one code path. If you can't trace it, don't ship it.
2. **Truth-class separation** — broker truth, snapshot analytics, synthetic history, persisted artifacts, optimizer previews, and replay are distinct. Never mix them in a single response.
3. **Trust semantics over fabrication** — `verified > degraded > withheld > unavailable`. Surface the level; don't fill in plausible values.
4. **No execution** — optimizer and overlay are hypothetical previews only. The system never places trades or moves money.

## Project goals (what we're building toward)

The product evolves through 4 active epics, tracked in `docs/product/epic-roadmap.md`:

| Epic | Objective | Status |
|---|---|---|
| 1. Imported-portfolio truth & reconciliation | Keep imported broker truth, trust semantics, and reconciliation explicit before downstream layers can overclaim | Foundation strong; admission summary + local review metadata shipped |
| 2. Ranking & selection methodology | Generalize ranking into a broader methodology platform with explicit selection guardrails and artifact-backed reuse | Active — `generic_ranking` platform + construction eligibility shipped; Workspace browser integration is the next slice |
| 3. Construction & optimizer methodology | Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts | Phase-closed for current phase; breadth expansion remains |
| 4. Monitoring & overlay review | Extend narrow review-scoped monitoring into broader persisted discipline workflows | Phase-closed for current phase; breadth expansion remains |

**Cross-epic guardrails** (always-on): truth classes stay explicit · persisted artifacts and typed handoffs stay authoritative · desktop stays thin on finance · optimization stays hypothetical · fail-closed loading must not be weakened.

## Where to find what (canonical doc map)

| Doc | Purpose |
|---|---|
| `README.md` | Public-facing project overview |
| `CLAUDE.md` (this file) | Always-on agent onboarding: project identity, guardrails, conventions, skill map |
| `docs/product/epic-roadmap.md` | **Living execution roadmap** — current epic status, planned slices, slice update log (read this first to know where we are) |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory — what works today, what's intentionally narrow, what's still future |
| `docs/product/roadmap.md` | Future-looking product direction (concise) |
| `docs/product/technical-roadmap.md` | Future-looking technical sequencing (concise) |
| `docs/finance/financial-methodology.md` | **Source of truth for every implemented financial formula**, trust semantics, methodology |
| `docs/architecture/system-architecture.md` | Backend seams, route inventory, truth class semantics, data flow |
| `docs/contracts/*.md` | 9 field inventory docs — backend ↔ TS type ↔ UI traceability per feature surface |
| `.claude/skills/*/SKILL.md` | On-demand specialist knowledge (5 skills — see table below) |

When shipping any methodology-meaningful change, update **all three**: methodology doc + relevant contract doc + tests.

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
    backtest/           # Improvement workflows, replay, Workspace
    strategy-lab/       # ETF ranking + cross-sectional research
    generic-ranking/    # Generic ranking platform UI
    market-data/        # Market data integration
    llm/                # LLM-assisted features (stub)
    settings/

services/quant-engine/app/
  api/routes/           # FastAPI routes (strategy_lab, construction, backtests, optimizer, etc.)
  analytics/            # Portfolio analytics (returns, drawdown, exposure, risk)
  backtests/            # Replay + backtest engines
  clients/              # FMP market data client (with caching)
  core/                 # Settings, logging, caching infrastructure
  domain/               # Ledger + accounting domain model
  importers/            # Broker parsers (Interactive Brokers, Freedom24, ESPP)
  instruments/          # Instrument registry
  datasets/             # Sample data + catalog
  schemas/              # Pydantic models (CONTRACT SOURCE OF TRUTH)
  services/             # Business logic services
  strategies/           # ETF ranking + cross-sectional research
  overlay/              # Portfolio overlay systems
  tests/                # Pytest suite

data/artifacts/         # Persisted decision artifacts (committed, auditable)
  construction-artifacts/
  etf-ranking-artifacts/
  etf-replacement-ranking-artifacts/
  generic-ranking-artifacts/
  optimizer-handoffs/
  cross-sectional-research-artifacts/
  monitor-definitions/

docs/
  product/              # Roadmap + current state + epic execution log
  finance/              # Financial methodology
  architecture/         # System architecture + truth classes
  contracts/            # Field inventory docs (backend ↔ TS ↔ UI)

.claude/
  settings.json         # Permissions
  skills/               # On-demand specialist knowledge (5 skills)
```

## Architecture: Truth Classes

The system enforces strict separation between data origins. **Never mix these in a single response or computation:**

| Class | Description |
|-------|-------------|
| **Broker Truth** | Imported positions/ledger from broker statements |
| **Snapshot Analytics** | Point-in-time computed metrics from current holdings |
| **Synthetic History** | Reconstructed historical returns from current holdings + market data |
| **Persisted Artifacts** | Saved construction/ranking/optimizer outputs (immutable, content-addressed) |
| **Optimizer Previews** | Hypothetical allocations (never execution) |
| **Replay** | Re-running persisted artifact workflows against historical market data |

Trust ladder: `verified > degraded > withheld > unavailable`. Never fabricate or fill missing data — surface the trust level instead.

## Development Commands

```bash
# Start both dev servers (backend on :8000, frontend on :5173)
python scripts/run_dev.py

# Pre-flight check only
python scripts/run_dev.py --check

# Backend only
cd services/quant-engine
uvicorn app.main:app --reload --port 8000

# Frontend only
cd apps/desktop
npm run dev

# Tests
python scripts/run_all_tests.py             # all
cd services/quant-engine && pytest          # backend
cd apps/desktop && npx vitest run           # frontend

# FMP cache management
python scripts/manage_cache.py
```

## Project Skills (load on-demand)

Each skill ships its own non-negotiable rules and validation commands. Invoke via the `Skill` tool when work shifts focus — they're free until used.

| Skill | Trigger |
|-------|---------|
| `financial-research` | Factor methodology, FMP/Alpha Vantage data sourcing, universe definitions, citing academic precedent |
| `portfolio-analytics` | Portfolio risk, performance, volatility, drawdown, factor analytics; cash-flow-neutral basis, benchmark separation |
| `artifact-workflow` | Creating/loading/extending persisted artifacts in `data/artifacts/`; content-addressed IDs, fail-closed validation |
| `contract-sync` | After any Pydantic schema change — keep schemas ↔ TS types ↔ docs/contracts/ aligned |
| `testing-triage` | When tests fail, when adding coverage, or when verifying a refactor didn't regress |

## Backend Conventions (`services/quant-engine/`)

- **Schemas first**: `app/schemas/` is the contract source of truth. Change schemas before changing routes or business logic.
- **Market data via FMP client**: `app/clients/fmp.py` handles caching. Never call FMP directly from routes.
- **Trust semantics**: Every field that can be missing carries a trust level. Never fabricate.
- **Truth-class separation**: See the table above. Never mix in one response.
- **Route pattern**: Check existing routes in `app/api/routes/` first. Schemas → service → route → register in `app/main.py` → tests in `app/tests/`.
- **Persisted artifacts**: Content-addressed IDs (`<prefix>_<sha256(canonical_json)[:16]>`), write-once, fail-closed validation. See `artifact-workflow` skill.

## Frontend Conventions (`apps/desktop/`)

- **Types mirror backend schemas exactly**: When schemas change, update TS types — invoke `contract-sync` skill.
- **Trust levels rendered visibly**: Never silently suppress `withheld` or `degraded` — show the badge.
- **Feature isolation**: Each `features/<name>/` owns its components/hooks/types; cross-feature sharing only via `app/store/` and `app/types/`.
- **No fabrication**: If data is `null`/`unavailable`, render the unavailable state, never zero or placeholder.
- **Stores in `app/store/`**: Use existing patterns; check before adding new state slices.
- **Frontend stays thin on finance**: No portfolio math in components. Ask the engine.

## MCP Capabilities

| Server | What it enables |
|--------|----------------|
| `filesystem` | Read/write project files and `data/artifacts/` |
| `github` | PRs, issues, repo management |
| `brave-search` | Web research for financial news, quant papers |
| `fetch` | Direct HTTP to FMP, Alpha Vantage, external APIs |
| `memory` | Persist research findings across agent sessions |
| `sequential-thinking` | Structured multi-step analysis for complex quant problems |
| `alpha-vantage` | Stock prices, ETF data, economic indicators, sentiment, earnings |

Keys (in environment or `.env`):
- `ALPHA_VANTAGE_API_KEY` — free tier sufficient for most research
- `BRAVE_API_KEY` — for web search
- `GITHUB_PERSONAL_ACCESS_TOKEN` — for GitHub MCP
- `FMP_API_KEY` — for live FMP data (optional; sample data fallback exists)

## When in doubt

1. **For methodology questions** → `docs/finance/financial-methodology.md` + `portfolio-analytics` skill
2. **For "what's shipped today"** → `docs/product/current-product-state.md`
3. **For "what's the next slice"** → `docs/product/epic-roadmap.md`
4. **For "where does this field come from"** → `docs/contracts/<area>-fields.md`
5. **For "how do I add an artifact kind"** → `artifact-workflow` skill
6. **For "schema just changed"** → `contract-sync` skill
7. **For "tests are red"** → `testing-triage` skill

**Default bias**: when uncertain about a financial calculation, degrade trust or fail-closed. It is always safer to surface "I'm not sure this is right" than to ship a plausible-looking wrong number.
