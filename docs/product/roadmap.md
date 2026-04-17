# Quant Research Lab Roadmap

This roadmap replaces the older engine-refactor roadmap as the main product direction.

The project is being steered toward a `quant-research-lab` model:
- a local-first portfolio intelligence and construction platform
- grounded in financially meaningful analytics
- focused on systematic portfolio decisions rather than generic dashboarding
- built for portfolio improvement, risk control, ranking, factor analysis, allocation replay, and disciplined research workflows

The target product is not a black-box predictor.
It is a transparent systematic investing and portfolio-construction workbench.

## Consolidation Guidance

Keep this file future-looking.

Retain in this file:
- `## Product Thesis`
- `## Core Product Principles`
- `## What the Project Should Become`
- `## Quant Methods the Product Should Prioritize`
- `## Required Financial Accuracy Work`
- `## Architecture Direction`
- `## Execution Plan`
- `## Immediate Priorities`
- `## Naming Direction`
- `## Documentation Rules`

Trim or move into `docs/product/current-product-state.md` on the next pass:
- `## Current Project Strengths to Build On`
- `## Current Product Gaps`
- under `### Stage 4. Portfolio Improvement Workspace`
  - `Current implemented Stage 4 slice`
  - `Current implemented pre-stage boundary`

Working rule:
- keep stage goals, tasks, and exit criteria here
- move shipped-scope snapshots and narrow implemented-slice detail into the canonical current-state doc

## Product Thesis

The project should evolve into a professional-grade workflow for:
- understanding current portfolio exposures and risks
- ranking ETFs / instruments systematically
- constructing candidate portfolios with explicit rules
- comparing current vs candidate portfolios historically
- monitoring factor drift, concentration, volatility, and benchmark-relative behavior
- applying quant methods that professionals actually use in practice

The strongest quant direction for this product is:
- `ranking systems`
- `factor investing`
- `risk budgeting`
- `portfolio construction`
- `allocation replay`
- `trend / momentum overlays`
- `scenario analysis`
- `monitoring`

The project should avoid centering itself on:
- opaque ML return prediction
- unconstrained Markowitz optimization
- short-horizon mean reversion trading
- overfit macro regime forecasting

## Core Product Principles

1. Financial outputs must be methodologically explicit.
2. Every displayed metric must be traceable to one engine output and one implementation path.
3. Broker-truth history, snapshot current-state analytics, and synthetic history approximations must remain clearly separated.
4. Systematic decision support is more important than signal novelty.
5. Portfolio construction rules and risk controls matter more than black-box alpha.
6. The UI should present decision-grade information, not quant-debug noise.
7. Any quant model added to the project must justify its economic meaning, data requirements, and operational usefulness.

## What the Project Should Become

### 1. Portfolio Intelligence Layer

Purpose:
- explain what the portfolio currently is
- identify hidden exposures and concentrations
- benchmark the portfolio against market, style, sector, and macro factors

Core capabilities:
- look-through exposure
- benchmark overlap / active share
- sector exposure
- factor model
- volatility / drawdown / tracking error
- risk contribution
- concentration
- stress scenarios

### 2. Quant Ranking Layer

Purpose:
- rank ETFs and instruments using systematic criteria
- support candidate selection and sleeve rotation

Target methods:
- momentum ranking
- volatility-adjusted ranking
- drawdown-aware ranking
- liquidity-aware ranking
- mapping-fit-aware ranking for UCITS vs US proxy translation
- later: factor-composite ranking

Outputs:
- ranked universe
- composite score
- component score breakdown
- inclusion/exclusion filters

### 3. Portfolio Construction Layer

Purpose:
- convert rankings, exposures, and constraints into target weights

Target methods:
- equal weight
- capped score-weighting
- volatility-scaled weighting
- benchmark + tilt construction
- risk-budget-aware sizing
- concentration-constrained allocation

Outputs:
- target weights
- turnover estimate
- implementation assumptions
- baseline vs candidate comparison

### 4. Portfolio Improvement Layer

Purpose:
- show whether changes actually improve the portfolio

Target workflow:
- baseline portfolio
- candidate portfolio
- historical allocation replay
- before/after diagnostics

Comparison dimensions:
- return
- annualized return
- volatility
- downside volatility
- drawdown
- tracking error
- information ratio
- factor exposure change
- risk contribution change
- concentration change
- stress scenario change

### 5. Overlay and Monitoring Layer

Purpose:
- maintain discipline after the portfolio is built

Target methods:
- trend-following overlay
- risk-on / risk-off overlay
- volatility / regime monitoring
- factor drift monitoring
- concentration drift monitoring
- benchmark-relative drift monitoring

## Quant Methods the Product Should Prioritize

### Tier 1: Highest-Value Methods

These are the most realistic and useful quant methods for this project and for personal investing.

1. `Ranking systems`
2. `Momentum`
3. `Factor investing`
4. `Portfolio construction rules`
5. `Risk budgeting`
6. `Allocation replay / current vs candidate comparison`
7. `Monitoring`

### Tier 2: Strong Supporting Methods

1. `Trend-following overlays`
2. `Scenario analysis`
3. `Simple regime flags`
4. `Constrained minimum-volatility construction`
5. `Multi-asset risk budgeting`

### Tier 3: Use Carefully

1. `Risk parity`
2. `Optimization`
3. `Theme rotation`

These should only be implemented with strong constraints and clear economic framing.

### Deprioritized / Not Core

1. `Short-horizon mean reversion`
2. `Black-box ML return prediction`
3. `Complex macro regime engines`
4. `Unconstrained expected-return optimization`

## Current Project Strengths to Build On

The project already has strong foundations in:
- factor and exposure analytics
- look-through and overlap analysis
- volatility and relative-risk diagnostics
- candidate vs reference allocation replay
- ETF momentum / ranking-adjacent strategy-lab workflow
- financial methodology documentation

This means the project is already best positioned as:
- a `portfolio intelligence + portfolio construction` platform

not yet as:
- a full institutional alpha-research stack

## Current Product Gaps

The main gaps blocking a real quant-research-lab direction are:

1. no unified instrument / ETF ranking engine
2. no true portfolio-construction rule engine
3. no robust optimization layer with constraints
4. the integrated portfolio-improvement workspace is now shipped in a narrow Workspace-owned form, but it is not yet the fully generalized primary product workflow
5. insufficiently production-grade factor math and reliability framing
6. diagnostics panels still partly optimized for debug-style outputs rather than PM decision flow
7. strategy research workflows are narrower than portfolio construction workflows

## Required Financial Accuracy Work

Before the quant lab can be treated as decision-grade, the project must harden the financial math behind the analytics.

### Production-Grade Factor Math Hardening

Required work:
- guarantee adjusted-close or total-return-equivalent input series for benchmark and ETF factor returns
- degrade explicitly when benchmark or factor histories are not total-return-aware
- expose factor-model assumptions structurally:
  - price basis
  - orthogonalization order
  - windows used
  - ridge parameter
- add stronger model reliability fields:
  - factors used vs dropped
  - observation count
  - collinearity severity
  - residual volatility / residual share
  - current-window reliability status
- make synthetic snapshot-history factor outputs visibly distinct from broker-truth historical diagnostics
- expand tests around proxy overlap, missing adjusted-price histories, and degradation semantics

### Production-Grade Diagnostics Prioritization

Diagnostics should prioritize:
1. risk contribution
2. concentration
3. model reliability
4. factor change monitoring

Not:
- biggest movers
- heuristic flags as the main decision surface

## Architecture Direction

The project should remain engine-based, with product framing centered on a quant research lab.

Target engine families:

### Import / Truth Engines
- import engine
- history-context builder
- benchmark service

### Portfolio Intelligence Engines
- exposure engine
- diagnostics engine
- dashboard history engine

### Portfolio Construction Engines
- portfolio allocation replay engine
- portfolio improvement engine
- later: construction / optimizer engine

### Quant Research Engines
- ranking engine
- momentum engine
- later: factor-composite engine
- later: overlay engine

The UI should consume narrow engine outputs rather than one broad analysis blob.

## Execution Plan

### Stage 1. Production-Grade Financial Core

Goal:
- make existing analytics trustworthy enough to serve as the base of a quant lab

Tasks:
- complete production-grade factor math hardening
- strengthen diagnostics ordering and reliability fields
- keep truth classes explicit in payloads and UI
- update financial methodology and inventory docs alongside code changes

Exit criteria:
- rolling factor and risk diagnostics are decision-grade or explicitly degraded
- model reliability is visible anywhere factor outputs are shown

### Stage 2. ETF / Instrument Ranking Engine

Goal:
- make ranking a first-class product capability

Tasks:
- define ranking request/response contracts
- build ranking components such as:
  - momentum
  - realized volatility
  - downside volatility
  - drawdown
  - benchmark-relative strength
  - liquidity and implementation fit
- support configurable composite weights
- expose ranked universe and component scores to the UI

Exit criteria:
- the project can rank ETF universes systematically
- ranked output is usable as input to construction workflows

### Stage 3. Portfolio Construction Rules

Goal:
- turn ranked or chosen assets into candidate portfolios using systematic rules

Tasks:
- implement rule-based weighting modes:
  - equal weight
  - capped score-weight
  - volatility-scaled
  - benchmark + tilt
  - concentration-capped
- expose hard constraints:
  - max position weight
  - max sleeve weight
  - turnover guardrails
  - concentration guardrails

Exit criteria:
- candidate portfolios can be built systematically rather than only manually

### Stage 4. Portfolio Improvement Workspace

Goal:
- make current vs candidate the central product workflow

Tasks:
- baseline seeding from current portfolio
- candidate builder with fast editing
- historical replay summary with baseline / candidate / delta
- before/after diagnostics:
  - factor exposure changes
  - volatility and drawdown changes
  - concentration changes
  - risk contribution changes
  - stress scenario changes

Current implemented Stage 4 slice:
- ETF ranking can seed a draft-scoped candidate review workflow
- Workspace now owns an explicit shell-first workflow order: current portfolio -> candidate idea -> candidate formation -> construction rule -> hypothetical replay -> diagnostics change -> saved proposal
- explicit replacement intent can drive a hypothetical one-for-one replay preview
- replay review now includes PM-first diagnostics delta review
- replay-scoped Monitoring now lives inside Workspace as a narrow review surface, not as a broad continuous monitoring system
- Monitoring can hand off back into Workspace workflow sections through an explicit user-initiated continuity path
- diagnostics groups expose backend-ranked top callouts with visible selection-rule provenance and backend-provided rationale
- reviewed hypothetical replay results can now be recorded as immutable local versioned proposal artifacts
- saved proposals can now be inspected in a dedicated review/readout surface that uses persisted artifact data only rather than active draft state
- these callouts remain review support only and do not imply recommendation or applied portfolio change

Exit criteria:
- the user can tell whether a portfolio change is actually an improvement

Current implemented pre-stage boundary:
- ETF ranking can seed a draft-scoped candidate review artifact
- that seed can persist locally and be restored deterministically
- a draft-scoped replacement intent can be recorded explicitly
- draft-scoped formed candidate, constructed candidate, selected-rule, and hypothetical replay artifacts also persist locally and are reset with draft lineage changes where appropriate
- these artifacts remain review metadata only and do not mutate `PortfolioSnapshot`

### Stage 5. Overlay and Monitoring System

Goal:
- support disciplined ongoing management after portfolio construction

Tasks:
- trend filter overlay
- volatility / regime state monitoring
- drift alerts for exposures and concentration
- benchmark-relative drift monitoring

Current shipped boundary before Stage 5:
- a narrow overlay-aware hypothetical replay path exists for the benchmark-trend candidate-side review flow
- Monitoring exists today only as a replay-scoped Workspace surface and should not be described as a continuous alerting system yet

Exit criteria:
- the project can monitor and maintain a systematic portfolio, not just analyze it once

### Stage 6. Constrained Optimization

Goal:
- use optimization as a constrained refinement tool, not as a black-box portfolio generator

Tasks:
- implement minimum-volatility / tracking-error-aware / turnover-aware optimizers
- enforce strong constraints and regularization
- keep rule-based construction available as the primary baseline

Exit criteria:
- optimization improves construction under clear guardrails

### Stage 7. Strategy Research Expansion

Goal:
- broaden the strategy-lab side after portfolio construction workflows are strong

Tasks:
- expand universe presets
- add reusable research templates
- support richer ranking experiments
- support walk-forward comparisons where realistic

Exit criteria:
- the project supports both portfolio construction research and selected strategy research workflows

## Immediate Priorities

1. finish production-grade factor math hardening
2. turn diagnostics into a PM-first panel
3. build the ETF / instrument ranking engine
4. build portfolio construction rules on top of ranking
5. make the portfolio improvement workspace the main backtest workflow

## Naming Direction

Recommended product naming direction:
- `Quant Research Lab`
- `quant-research-lab`

This naming should reflect the actual product direction:
- systematic portfolio intelligence
- ranking and construction
- historical replay and improvement workflows
- transparent, documented quant methodology

## Documentation Rules

Any financially meaningful change must update:
- methodology strings in code
- `docs/finance/financial-methodology.md`
- relevant field inventory docs
- tests that lock down formulas and degraded semantics

This roadmap should remain focused on product direction and execution order.
Detailed implementation plans should live in dedicated specs and technical roadmap files.
