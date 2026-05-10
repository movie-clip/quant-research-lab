# Quant Research Lab

Local-first quant research and portfolio construction platform for imported portfolios, factor and ETF research, deterministic construction, hypothetical optimizer handoff replay, and systematic portfolio improvement.

For the canonical shipped-state boundary, see `docs/product/current-product-state.md`.

## Product Direction

The core direction of the project is:
- `portfolio intelligence`
- `quant ranking`
- `portfolio construction`
- `portfolio improvement`
- `allocation replay`
- `optimizer preview and handoff replay`
- `overlay and monitoring`

Highest-priority quant methods for the platform:
- factor investing
- momentum and relative strength
- ranking systems
- rule-based construction
- risk budgeting
- constrained optimization under guardrails
- trend / risk overlays
- monitoring

The product is not intended to be a black-box prediction engine.
It is intended to be a deterministic, auditable decision-support platform for systematic investing.

## Repo Structure

```text
quant-research-lab/
  README.md
  CLAUDE.md                       # Agent onboarding (Claude Code auto-loads this)
  apps/
    desktop/                      # Tauri/React desktop UI
  services/
    quant-engine/                 # Python FastAPI quant engine
  docs/
    product/
      current-product-state.md    # Canonical shipped-state inventory
      epic-roadmap.md             # Living execution roadmap (active epics + slice log)
      roadmap.md                  # Future-looking product direction
      technical-roadmap.md        # Future-looking technical sequencing
    finance/
      financial-methodology.md    # Source of truth for financial formulas
    architecture/
      system-architecture.md      # Backend seams, truth classes, data flow
    contracts/                    # 9 field inventory docs (backend ↔ TS ↔ UI)
      backtest-fields.md
      candidate-workflow-fields.md
      dashboard-fields.md
      diagnostics-fields.md
      etf-ranking-fields.md
      exposure-fields.md
      generic-ranking-fields.md
      import-admission-fields.md
      research-artifact-fields.md
  data/
    artifacts/                    # Persisted decision artifacts (committed)
      construction-artifacts/
      etf-ranking-artifacts/
      etf-replacement-ranking-artifacts/
      generic-ranking-artifacts/
      optimizer-handoffs/
      cross-sectional-research-artifacts/
      monitor-definitions/
  scripts/
  .claude/
    skills/                       # On-demand specialist knowledge
```

## Documentation Structure

Core docs:
- `docs/product/current-product-state.md`
  - canonical source for what is shipped today, what is narrow, and what is still future
- `docs/product/epic-roadmap.md`
  - living execution roadmap for the four active product epics, including a per-slice update log
- `docs/product/roadmap.md`
  - concise product roadmap for remaining work only
- `docs/product/technical-roadmap.md`
  - concise technical roadmap for remaining implementation work
- `docs/finance/financial-methodology.md`
  - source of truth for financial formulas, trust semantics, and implemented methods
- `docs/architecture/system-architecture.md`
  - current seams, engine responsibilities, truth classes, and provenance rules
- `docs/contracts/*-fields.md`
  - 9 field inventory docs covering dashboard, exposure, diagnostics, backtest, ETF ranking, generic ranking, candidate workflows, research artifacts, and import admission

Rule:
- shipped-state truth lives in `docs/product/current-product-state.md`
- live execution status lives in `docs/product/epic-roadmap.md`
- `roadmap.md` and `technical-roadmap.md` stay future-looking and concise
- if a financially meaningful formula or withholding rule changes, update `docs/finance/financial-methodology.md` and the relevant field inventory in the same pass

## Financial Accuracy Rules

The project follows these rules:
- every displayed financial metric must be traceable to one engine output and one code path
- imported broker truth, snapshot current-state analytics, synthetic history, persisted construction artifacts, optimizer previews, and hypothetical replay must remain clearly separated
- return-based paths must expose trust explicitly through verification, degradation, withholding, or unavailability semantics
- if a financially meaningful result cannot be supported faithfully, the system should degrade or withhold explicitly rather than fabricate plausible values
- import admission summaries are read-only evidence, and desktop-local admission review dispositions do not mutate broker truth, trust, admission state, imported values, or workspace creation

See:
- `docs/finance/financial-methodology.md`
- `docs/architecture/system-architecture.md`

## Main Workflows

### 1. Imported Portfolio Truth
- import broker statements
- normalize positions, balances, and ledger activity
- reconstruct portfolio truth and history context
- surface read-only import admission evidence with finite-only numeric checks; optional reviewer dispositions stay desktop-local and non-trust-changing

### 2. Portfolio Intelligence
- analyze holdings, look-through exposure, benchmark overlap, factors, volatility, drawdown, and concentration

### 3. Ranking
- rank ETFs or instruments systematically using transparent components such as momentum, volatility, drawdown, liquidity, and implementation fit

### 4. Construction
- build deterministic candidate portfolios from explicit policies, constraints, and persisted input artifacts

### 5. Improvement
- compare baseline vs candidate portfolios through replay and before/after diagnostics

### 6. Optimizer Workflow
- generate hypothetical optimizer previews
- persist explicit handoff lineage
- validate and replay the handoff without treating it as applied portfolio truth

### 7. Monitoring
- monitor drift, factor changes, volatility regime, and concentration over time

## Development Notes

Desktop app:
- `apps/desktop`

Python quant engine:
- `services/quant-engine`

Run the backend and browser/Vite dev servers only:

```bash
python scripts/run_dev.py
```

This web dev flow is fixed to `http://127.0.0.1:5173`.
If port `5173` is already in use, the script fails fast and prints an error instead of switching to another port.

Check only:

```bash
python scripts/run_dev.py --check
```

## Naming Direction

Recommended project / repo name:
- `quant-research-lab`

Current local folder may still be named differently until a full rename pass is completed.

Target git remote:
- `git@github.com:movie-clip/quant-research-lab.git`
