# Quant Research Lab

Local-first quant research and portfolio construction platform for imported real portfolios, ETF and factor research, allocation replay, and systematic portfolio improvement.

For the canonical shipped-scope status, see `docs/product/current-product-state.md`.

This project is designed to become a practical `quant-research-lab` for personal investing and research workflows:
- import broker statements and reconstruct portfolio truth
- analyze exposures, factors, overlap, and risk
- rank ETFs and instruments systematically
- build candidate portfolios with explicit rules and constraints
- compare baseline vs candidate portfolios through historical replay
- monitor drift, concentration, volatility, and benchmark-relative behavior

The product is not intended to be a black-box prediction engine.
It is intended to be a deterministic, auditable, decision-support platform for systematic investing.

## Product Direction

The core direction of the project is:
- `portfolio intelligence`
- `quant ranking`
- `portfolio construction`
- `portfolio improvement`
- `allocation replay`
- `overlay and monitoring`

Highest-priority quant methods for the platform:
- factor investing
- momentum and relative strength
- ranking systems
- risk budgeting
- portfolio construction rules
- trend / risk overlays
- scenario analysis
- monitoring

## Repo Structure

```text
quant-research-lab/
  README.md
  apps/
    desktop/                # Desktop UI for research, diagnostics, replay, and review
  services/
    quant-engine/           # Python engine for imports, factors, analytics, ranking, and replay
  docs/
    product/
      current-product-state.md
      docs-execution-checklist.md
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

The docs folder should stay small and high-signal.

Core docs:
- `docs/product/current-product-state.md`
  - canonical source for what is shipped today, what is narrow, and what is still future
- `docs/product/roadmap.md`
  - product direction and execution order
- `docs/product/technical-roadmap.md`
  - technical implementation roadmap for the quant-lab pivot
- `docs/product/docs-execution-checklist.md`
  - ownership and next steps for the docs accuracy / consolidation pass
- `docs/finance/financial-methodology.md`
  - source of truth for financial formulas, assumptions, and implemented methods
- `docs/architecture/system-architecture.md`
  - system boundaries, truth classes, engine responsibilities, and provenance rules
- `docs/contracts/dashboard-fields.md`
  - dashboard financial field traceability
- `docs/contracts/exposure-fields.md`
  - exposure and diagnostics field traceability
- `docs/contracts/backtest-fields.md`
  - backtest and replay field traceability

Rule:
- keep current shipped-scope summary in `docs/product/current-product-state.md`
- if a financially meaningful formula changes, update methodology text and the relevant field inventory at the same time

## Financial Accuracy Rules

The project follows these rules:
- every displayed financial metric must be traceable to one engine output and one code path
- imported broker truth, snapshot current-state analytics, synthetic history, and hypothetical replay must remain clearly separated
- if a historical result cannot be produced faithfully, the system should degrade explicitly rather than fabricate plausible values
- adjusted-close or total-return-aware inputs are required for return-based analytics wherever economically meaningful

See:
- `docs/finance/financial-methodology.md`
- `docs/architecture/system-architecture.md`

## Broker Fixtures and Test Inputs

The project already has source-of-truth broker statement examples from:
- `IB2026.pdf`
- `FF2026.pdf`
- `ESPP2026.pdf`

Important usage rule:
- use the document layout, section structure, and data-shape expectations from those broker exports as parser and regression references
- do not hardcode tests to exact file binaries if you expect the user to re-export fresh copies over time
- tests should prefer normalized expectations for:
  - section layout
  - field extraction shape
  - accounting semantics
  - combined snapshot behavior

In other words:
- use the files as format references
- use extracted normalized data patterns as the durable test contract

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
- build candidate portfolios from rules and constraints

### 5. Improvement
- compare baseline vs candidate portfolios through replay and before/after diagnostics

### 6. Monitoring
- monitor drift, factor changes, volatility regime, and concentration over time

## Current Architecture Direction

The project is organized around engine outputs rather than one monolithic analysis payload.

The main engine families are:
- import / truth engines
- exposure and diagnostics engines
- ranking and research engines
- construction and replay engines
- overlay and monitoring engines

The frontend should remain thin on finance logic and should not synthesize financial analytics locally.

## Development Notes

Desktop app:
- `apps/desktop`

Python quant engine:
- `services/quant-engine`

Run both dev servers:

```bash
python scripts/run_dev.py
```

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
