# quant-research-lab

A **local-first, deterministic, auditable** decision-support platform for systematic personal investing. The product imports broker portfolios, computes deterministic analytics, and supports a rank → construct → replay → optimize workflow under explicit guardrails.

> The product is **not** a black-box prediction engine. It is a research workbench where every displayed financial number must be explainable, traceable, and reproducible.

## ⚠️ Critical: financial accuracy comes first

**If the math or financial methodology is wrong, nothing else matters.** Before changing any analytics, factor formula, replay basis, or trust-state logic:

1. **Read `docs/finance/financial-methodology.md`** — the canonical source of truth for every implemented formula
2. **Cite academic precedent** in the methodology doc when introducing a new factor, weighting scheme, normalization, or universe definition
3. **Update tests in the same pass** — every methodology change must include or update regression tests
4. **Surface trust state explicitly** — never fabricate, never silently fallback, never collapse `withheld` into `unavailable`

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
| `docs/product/epic-roadmap.md` | **Living execution roadmap** — epic snapshot + slice update log + the delivery-model overview (read this first to know where we are) |
| `docs/product/prd/` | **PRDs** — one per epic: problem, goals, non-goals, success signals, story list (`README.md` explains the PRD → story → ticket model) |
| `docs/product/stories/` | **User stories** — one file per story: statement, acceptance criteria, test plan, tickets, status (`README.md` is the live index) |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory — what works today, what's intentionally narrow, what's still future |
| `docs/product/roadmap.md` | Future-looking product direction (concise) |
| `docs/product/technical-roadmap.md` | Future-looking technical sequencing (concise) |
| `docs/finance/financial-methodology.md` | **Source of truth for every implemented financial formula**, trust semantics, methodology |
| `docs/architecture/system-architecture.md` | Backend seams, route inventory, truth class semantics, data flow |
| `docs/contracts/*.md` | Field inventory docs — backend ↔ TS type ↔ UI traceability per feature surface |
| `.claude/skills/write-story/SKILL.md` | The `write-story` skill — how an agent authors a User Story from a feature idea (statement → ACs → test plan → tickets) |
| `.claude/skills/build-story/SKILL.md` | The `build-story` skill — how an agent implements a ticketed story end-to-end |

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
  product/
    prd/                # PRDs — one per epic (problem, goals, story list)
    stories/            # User stories — one file per story (tickets, test plan)
    epic-roadmap.md     # Epic snapshot + slice log + delivery model
    current-product-state.md  # Shipped-state inventory
  finance/              # Financial methodology
  architecture/         # System architecture + truth classes
  contracts/            # Field inventory docs (backend ↔ TS ↔ UI)

.claude/
  settings.json         # Permissions
  skills/build-story/   # The build-story skill — deliver one user story end-to-end
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

# Tests — `run_all_tests.py` is the canonical entrypoint.
# It regenerates the dashboard golden fixtures BEFORE pytest runs, then runs
# vitest. Bare `pytest` and bare `vitest` are fine for narrow iteration, but
# the goldens must be fresh; an autouse session-scope fixture in
# `services/quant-engine/app/tests/conftest.py` fails pytest fast with an
# actionable message if they have drifted. Set `SKIP_GOLDEN_FRESHNESS_CHECK=1`
# to bypass for a narrow run (only when you know the surface you're touching
# doesn't depend on the dashboard goldens).
python scripts/run_all_tests.py             # all (canonical)
cd services/quant-engine && pytest          # backend (freshness-checked)
cd apps/desktop && npx vitest run           # frontend
python -m app.scripts.export_dashboard_goldens  # regenerate goldens (from services/quant-engine/)

# FMP cache management
python scripts/manage_cache.py
```

## Delivery model & project skills

Work is delivered as **PRD → User Story → Ticket** — vertical slices of user
value, not isolated technical features.

- PRDs: `docs/product/prd/` (one per epic). User stories:
  `docs/product/stories/` (one file per story, each with acceptance criteria,
  a test plan, tickets, status). See `docs/product/prd/README.md`.
- Only the next-phase story is broken into tickets; backlog stories are
  defined but not yet decomposed.

Two project skills drive the workflow:

| Skill | When to use |
|---|---|
| **`write-story`** | You have a feature idea and want it turned into a complete, ticketed User Story file. Invoke it before any code is written. |
| **`build-story`** | A story file exists with tickets and you want to implement it — reads PRD + story, works tickets in order, writes tests, satisfies acceptance criteria, updates docs, opens a PR. |

Workflow: `write-story` → story file (Next phase) → `build-story` → merged PR.

## Backend Conventions (`services/quant-engine/`)

- **Schemas first**: `app/schemas/` is the contract source of truth. Change schemas before changing routes or business logic.
- **Market data via FMP client**: `app/clients/fmp.py` handles caching. Never call FMP directly from routes.
- **Trust semantics**: Every field that can be missing carries a trust level. Never fabricate.
- **Truth-class separation**: See the table above. Never mix in one response.
- **Route pattern**: Check existing routes in `app/api/routes/` first. Schemas → service → route → register in `app/main.py` → tests in `app/tests/`.
- **Persisted artifacts**: Content-addressed IDs (`<prefix>_<sha256(canonical_json)[:16]>`), write-once, fail-closed validation.

## Frontend Conventions (`apps/desktop/`)

- **Types mirror backend schemas exactly**: When a Pydantic schema changes, update the desktop TS types and the matching `docs/contracts/<area>-fields.md` in the same pass.
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

1. **For methodology questions** → `docs/finance/financial-methodology.md`
2. **For "what's shipped today"** → `docs/product/current-product-state.md`
3. **For "what's the next story / how do I deliver it"** → `docs/product/stories/` + the `build-story` skill
4. **For "what's the scope of this epic"** → `docs/product/prd/<epic>.md`
5. **For "where are we overall"** → `docs/product/epic-roadmap.md`
6. **For "where does this field come from"** → `docs/contracts/<area>-fields.md`
7. **For "how do I add an artifact kind / sync a schema / triage tests"** → `docs/architecture/system-architecture.md` and the contract docs; follow the conventions above

**Default bias**: when uncertain about a financial calculation, degrade trust or fail-closed. It is always safer to surface "I'm not sure this is right" than to ship a plausible-looking wrong number.
