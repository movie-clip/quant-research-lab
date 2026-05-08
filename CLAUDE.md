# quant-research-lab

Local-first quant research and portfolio construction platform. Deterministic, auditable workflows for imported broker portfolios, factor/ETF research, and systematic portfolio improvement.

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
  app/              # Core state + storage
  features/
    portfolio/      # Holdings, exposure, diagnostics
    backtest/       # Improvement workflows
    strategy-lab/   # ETF ranking + construction
    market-data/    # Market data integration
    llm/            # LLM-assisted features (stub)
    settings/

services/quant-engine/app/
  api/routes/       # 11 REST endpoint modules
  analytics/        # Portfolio analytics engine
  backtests/        # Replay + backtest engines
  clients/          # FMP market data client
  domain/           # Ledger + accounting
  importers/        # Broker parsers (IB, Freedom24, ESPP)
  schemas/          # Pydantic data contracts (source of truth)
  strategies/       # ETF ranking + research
  services/         # Business logic
  overlay/          # Portfolio overlays

docs/
  product/          # Current state + roadmap
  finance/          # Financial methodology
  architecture/     # System architecture + truth classes
  contracts/        # Field inventory docs (7 files)

data/artifacts/     # Persisted analysis outputs (committed)
  construction-artifacts/
  etf-ranking-artifacts/
  etf-replacement-ranking-artifacts/
  optimizer-handoffs/

.opencode/skills/   # Guardrail skill docs (manually referenced)
.claude/agents/     # Specialist subagent definitions
```

## Development Commands

```bash
# Start both servers
python scripts/run_dev.py

# Backend only (quant engine)
cd services/quant-engine
uvicorn app.main:app --reload --port 8000

# Frontend only
cd apps/desktop
npm run dev

# Tests
python scripts/run_all_tests.py        # all
cd services/quant-engine && pytest     # backend
cd apps/desktop && npm test            # frontend

# FMP cache management
python scripts/manage_cache.py
```

## Architecture: Truth Classes

The system enforces strict separation between data origins. Never mix these:

| Class | Description |
|-------|-------------|
| **Broker Truth** | Imported positions/ledger from broker statements |
| **Snapshot Analytics** | Point-in-time computed metrics |
| **Synthetic History** | Reconstructed historical returns |
| **Persisted Artifacts** | Saved construction/ranking/optimizer outputs |
| **Optimizer Previews** | Hypothetical allocations (never execution) |
| **Replay** | Re-running persisted artifact workflows |

Trust semantics for data availability: `verified > degraded > withheld > unavailable`. Never fabricate or fill missing data — surface the trust level instead.

## Core Guardrails

1. **Artifact lineage**: Every persisted artifact must carry provenance (selection rules, input IDs, timestamps). Never load artifacts without validation.
2. **Analytics comparability**: Return basis must be consistent across comparisons. Benchmark-relative suppression requires explicit attestation.
3. **Contract sync**: `services/quant-engine/app/schemas/` is the source of truth. Desktop types in `apps/desktop/src/` must match. `docs/contracts/` must reflect both.
4. **No execution**: Optimizer and overlay workflows are hypothetical previews only. The system never places trades or moves money.

Reference `.opencode/skills/` for detailed guardrail checklists:
- `artifact-workflow-guard.md` — artifact lineage + replay boundaries
- `quant-contract-sync.md` — schema → desktop type → docs sync
- `portfolio-analytics-guard.md` — analytics methodology + benchmark separation

## Multi-Agent Orchestration

Agent teams are enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Specialist agents are defined in `.claude/agents/`. Spawn them when tasks are naturally parallelizable or require deep domain focus.

### When to Spawn Specialist Agents

| Scenario | Agents to spawn |
|----------|-----------------|
| New API endpoint + matching frontend | `quant-engine` + `frontend` in parallel |
| Schema change | `quant-engine` + `contract-sync` sequentially, then `frontend` |
| ETF ranking research | `financial-research` independently |
| Test failures across both services | `testing` independently |
| Large refactor touching both layers | `quant-engine` + `frontend` in parallel |

### Spawning Pattern

```
Spawn a quant-engine specialist to add the new /overlay/stress-test route,
and a frontend specialist to wire it up in the strategy-lab feature — run in parallel.
```

### Agent Capabilities

- **quant-engine**: Python/FastAPI backend, analytics, schemas, importers, backtests
- **frontend**: React/TypeScript/Tauri desktop, all features under apps/desktop/
- **financial-research**: Market data via Alpha Vantage MCP + web search; ETF/factor analysis
- **testing**: Test suite health across both services; runs + fixes failing tests
- **contract-sync**: Keeps schemas ↔ desktop types ↔ docs/contracts/ synchronized

## MCP Capabilities

| Server | What it enables |
|--------|----------------|
| `filesystem` | Read/write project files and data/artifacts |
| `github` | PRs, issues, repo management |
| `brave-search` | Web research for financial news, quant papers |
| `fetch` | Direct HTTP to FMP, Alpha Vantage, external APIs |
| `memory` | Persist research findings across agent sessions |
| `sequential-thinking` | Structured multi-step analysis for complex quant problems |
| `alpha-vantage` | Stock prices, ETF data, economic indicators, technical indicators |

Keys needed (set in environment or `.env`):
- `ALPHA_VANTAGE_API_KEY` — free tier sufficient for most research
- `BRAVE_API_KEY` — for web search
- `GITHUB_PERSONAL_ACCESS_TOKEN` — for GitHub MCP

## Key Conventions

- Pydantic schemas in `services/quant-engine/app/schemas/` are the contract source of truth — change them first, then desktop types, then docs
- All API routes follow the pattern in `app/api/routes/` — check an existing route before adding a new one
- Market data goes through `app/clients/fmp_client.py` with local caching — never call FMP directly from routes
- Desktop stores live in `apps/desktop/src/app/` — use existing store patterns before adding new state
- Persisted artifacts in `data/artifacts/` are committed to git — treat them as auditable records
