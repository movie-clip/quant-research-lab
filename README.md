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
  apps/
    desktop/                # Desktop UI for research, diagnostics, replay, and review
  services/
    quant-engine/           # Python engine for imports, factors, ranking, construction, optimizer preview, and replay
  docs/
    product/
      current-product-state.md
      roadmap.md
      technical-roadmap.md
    finance/
      financial-methodology.md
    architecture/
      system-architecture.md
    contracts/
      dashboard-fields.md
      exposure-fields.md
      backtest-fields.md
  scripts/
  data/
```

## Documentation Structure

Core docs:
- `docs/product/current-product-state.md`
  - canonical source for what is shipped today, what is narrow, and what is still future
- `docs/product/roadmap.md`
  - concise product roadmap for remaining work only
- `docs/product/technical-roadmap.md`
  - concise technical roadmap for remaining implementation work
- `docs/finance/financial-methodology.md`
  - source of truth for financial formulas, trust semantics, and implemented methods
- `docs/architecture/system-architecture.md`
  - current seams, engine responsibilities, truth classes, and provenance rules
- `docs/contracts/dashboard-fields.md`
  - dashboard financial field traceability
- `docs/contracts/exposure-fields.md`
  - exposure and diagnostics field traceability
- `docs/contracts/backtest-fields.md`
  - backtest, replay, optimizer handoff, and construction replay field traceability

Rule:
- keep shipped-state detail in `docs/product/current-product-state.md`
- keep roadmap docs future-looking and concise
- if a financially meaningful formula or withholding rule changes, update methodology text and the relevant field inventory at the same time

## Financial Accuracy Rules

The project follows these rules:
- every displayed financial metric must be traceable to one engine output and one code path
- imported broker truth, snapshot current-state analytics, synthetic history, persisted construction artifacts, optimizer previews, and hypothetical replay must remain clearly separated
- return-based paths must expose trust explicitly through verification, degradation, withholding, or unavailability semantics
- if a financially meaningful result cannot be supported faithfully, the system should degrade or withhold explicitly rather than fabricate plausible values

See:
- `docs/finance/financial-methodology.md`
- `docs/architecture/system-architecture.md`

## Main Workflows

### 1. Imported Portfolio Truth
- import broker statements
- normalize positions, balances, and ledger activity
- reconstruct portfolio truth and history context

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
