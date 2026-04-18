# Quant Research Lab Technical Roadmap

## Goal

Evolve the project into a local-first quant research lab for personal and systematic investing.

Recommended naming direction:
- product: `Quant Research Lab`
- repo: `quant-research-lab`

The target product is a deterministic research and decision platform for:
- imported portfolio truth and reconciliation
- systematic ranking and portfolio construction
- historical portfolio-improvement workflows
- overlay and monitoring systems
- financially accurate, auditable analytics

The product should optimize for disciplined portfolio decisions, not black-box prediction.

## Consolidation Guidance

Keep this file technical and future-looking.

Retain in this file:
- `## Goal`
- `## Product Principles`
- `## Target Architecture`
- `## Canonical Data Model`
- `## Ranking System Roadmap`
- `## Portfolio Construction Roadmap`
- `## Portfolio Improvement Workflow`
- `## Overlay Roadmap`
- `## Monitoring Roadmap`
- `## Optimization Roadmap`
- `## Financial Accuracy Requirements`
- `## Delivery Plan`
- `## Immediate Priorities`
- `## Definition of Done for the Pivot`

Trim or move into `docs/product/current-product-state.md` on the next pass:
- `## Current State`
- under `## Ranking System Roadmap`
  - `Current implemented slice`
- under `## Portfolio Construction Roadmap`
  - `Current implemented slice`
- under `## Portfolio Improvement Workflow`
  - step 2 bullet `current implemented state`
  - `Current implemented progress inside this flow`
  - `Current boundary before replay/construction`
- under `## Overlay Roadmap`
  - `Current implemented slice`
- under `## Delivery Plan`
  - Stage 2 `Current partial state`
  - Stage 3 `Current partial state`
  - Stage 4 `Current partial state`
  - Stage 5 `Current partial state`

Working rule:
- keep target engine families, target contracts, and staged delivery here
- move shipped-route inventories, narrow implemented slices, and current-boundary notes into the canonical current-state doc

## Current State

The project already has strong foundations in:
- local-first architecture with desktop UI plus Python quant engine
- broker import and portfolio snapshot workflows
- factor, exposure, overlap, and risk diagnostics
- allocation replay / candidate-vs-baseline backtests
- ETF ranking contracts, including intent-bound seeded replacement ranking
- explicit single-replacement candidate formation and candidate construction flows
- hypothetical replacement replay and overlay-aware hypothetical replay
- PM-first replay review plus local proposal artifact persistence/readout
- DuckDB / Parquet-friendly data direction
- methodology documentation and truth-class awareness

The main gap is not missing infrastructure. The main gap is product unification:
- engines exist, but are not yet organized around a complete quant-research workflow
- ranking exists today, but only in narrow ETF-oriented slices rather than as a generalized first-class engine family
- portfolio construction exists today, but only in narrow single-replacement rule-based slices rather than as a generalized first-class engine family
- improvement, overlay, monitoring, and optimization need explicit boundaries
- replay/construction provenance needs tighter end-to-end contract consistency
- financial-accuracy rules need to be elevated from good practice to hard platform requirements

## Product Principles

1. Deterministic calculations own all portfolio decisions and analytics.
2. Every displayed metric must map to one engine output, one methodology, and one code path.
3. Imported broker truth, current snapshot analytics, synthetic approximations, and hypothetical backtests must remain explicitly separated.
4. Research outputs must be reproducible from versioned inputs, parameters, and dataset timestamps.
5. Ranking and construction rules are primary; optimization is a constrained refinement layer.
6. The frontend remains thin on finance logic and never becomes a second calculation engine.
7. LLM features may explain, summarize, and suggest, but never authoritatively calculate.

## Target Architecture

### System shape

Keep the local-first monorepo and harden the current split:
- `apps/desktop`: workflow UI, workspace state, visualization, review flows
- `services/quant-engine`: deterministic engines, datasets, portfolio truth, research computation
- `data/curated`, `data/duckdb`, `data/exports`: local dataset and result persistence

### Backend engine families

#### 1. Truth and Data Engines
Own imported and market-data truth.
- import engine
- reconciliation engine
- portfolio state engine
- market data ingestion engine
- dataset builder / catalog engine
- benchmark and metadata service

#### 2. Portfolio Intelligence Engines
Own understanding of the current portfolio.
- exposure engine
- diagnostics engine
- factor model engine
- dashboard history engine
- scenario engine

#### 3. Quant Research Engines
Own universe evaluation and systematic research.
- ranking engine
- signal / factor composite engine
- strategy research engine
- cross-sectional analytics engine

#### 4. Portfolio Construction Engines
Own conversion of research into allocations.
- candidate construction engine
- constraint engine
- turnover and implementation-cost engine
- allocation replay engine
- optimization engine

#### 5. Portfolio Improvement Engines
Own baseline-vs-candidate decision workflows.
- improvement comparison engine
- attribution and change engine
- diagnostics delta engine
- proposal persistence engine

#### 6. Overlay and Monitoring Engines
Own ongoing portfolio discipline.
- overlay engine
- drift monitoring engine
- regime / volatility monitor
- alert and review engine

## Canonical Data Model

### Domain entities that must become first-class

#### Portfolio truth
- `Portfolio`
- `Account`
- `ImportedStatement`
- `Transaction`
- `CashLedgerEntry`
- `CorporateAction`
- `TaxLot`
- `Position`
- `PortfolioSnapshot`
- `DailyPortfolioState`

#### Market and research data
- `Instrument`
- `Listing`
- `Benchmark`
- `PriceBar`
- `AdjustedPriceSeries`
- `FundamentalPoint`
- `ETFConstituentSnapshot`
- `FactorDefinition`
- `UniverseDefinition`
- `DatasetVersion`

#### Research and construction
- `RankingSpec`
- `RankingComponent`
- `RankingRun`
- `EligibilityFilter`
- `ConstructionSpec`
- `ConstraintSet`
- `CandidatePortfolio`
- `AllocationReplayRun`
- `OptimizationRun`

#### Improvement, overlay, monitoring
- `ImprovementRun`
- `OverlaySpec`
- `OverlayRun`
- `MonitorDefinition`
- `MonitorObservation`
- `AlertEvent`

### Data-model rules

- Portfolio truth and research outputs must never share the same truth class.
- Every persisted result must include dataset version, parameter set, timestamps, and methodology id.
- Any synthetic or replay-derived artifact must carry explicit provenance.
- Instruments need stable canonical identity independent of broker naming or ETF aliases.
- Benchmarks, factors, and proxies must be modeled explicitly rather than inferred ad hoc in UI code.

## Ranking System Roadmap

Make ranking a first-class engine, not a side effect of backtests.

Current implemented slice:
- generic ETF ranking exists at `POST /strategy-lab/etf-ranking`
- intent-bound seeded ETF replacement ranking exists at `POST /ranking/etf-replacements`
- current ranking scope is deterministic and auditable, but still ETF-specific and not yet modeled as a generalized ranking-run platform across universes

### Ranking engine responsibilities
- define investable universes
- apply eligibility filters
- compute component scores
- produce composite ranks
- expose score breakdown and exclusion reasons
- persist ranking runs for reproducibility

### Initial ranking components
- medium-term momentum
- long-term momentum
- realized volatility
- downside volatility
- max drawdown
- trend confirmation
- liquidity / tradability
- expense ratio or implementation drag
- benchmark-relative strength
- mapping-fit score for proxy translation where relevant

### Ranking design rules
- each component must have economic meaning
- all scores must define direction, normalization, and missing-data degradation
- composite weights must be configurable but versioned
- ranks must expose raw values, normalized values, and final score
- no hidden winsorization, clipping, or proxy substitution without metadata

## Portfolio Construction Roadmap

Portfolio construction should become its own engine family with explicit rules.

Current implemented slice:
- candidate formation exists for review-only same-weight single replacement
- candidate construction exists for explicit single-replacement rules at `POST /backtests/candidate-construction/replacement-intent`
- currently supported rules are:
  - `same_weight_substitution_v1`
  - `fixed_split_50_50_substitution_v2`
- current construction outputs are hypothetical candidate inputs only; they do not mutate portfolio truth or create optimizer-style allocations

### Rule-based construction modes
- equal weight
- capped score weight
- volatility-scaled weight
- benchmark plus tilt
- sleeve-budgeted construction
- concentration-capped allocation
- risk-budget-aware allocation

### Constraint model
Support explicit hard and soft constraints:
- max position weight
- min position weight
- max sleeve weight
- sector / factor exposure caps
- benchmark deviation caps
- turnover budget
- liquidity guardrails
- cash floor
- tax-aware exclusions later

### Construction outputs
- target weights
- constraint satisfaction report
- turnover estimate
- implementation assumptions
- expected exposure profile
- baseline-vs-candidate delta preview

## Portfolio Improvement Workflow

Make current-vs-candidate the core product workflow.

### Target flow
1. load imported or current portfolio baseline
2. seed candidate from baseline or ranking output
   - current implemented state: ETF ranking can seed draft-scoped candidate review metadata without mutating `PortfolioSnapshot`
   - seed metadata persists locally per draft and has explicit no-propagation lifecycle rules
   - replacement intent can now be recorded explicitly as a separate draft-scoped review object
3. form candidate review artifact from the replacement intent
4. select and run construction rule for a constructed candidate review artifact
5. run historical allocation replay
6. compare baseline, candidate, and delta
7. inspect diagnostics changes
8. save candidate as a versioned proposal

Current implemented progress inside this flow:
- replacement intent can now feed explicit candidate formation and candidate construction backend routes before replay
- construction is backend-owned and deterministic; the desktop does not author finance logic for candidate weights
- Workspace now owns an explicit shell-first workflow order: current portfolio, candidate idea, candidate formation, construction rule, hypothetical replay, diagnostics change, and saved proposal
- hypothetical replacement replay now has a PM-first diagnostics delta review surface
- hypothetical replay can consume either direct same-weight derivation or an accepted constructed candidate payload
- diagnostics groups currently read in decision order: concentration, factor exposure, volatility/drawdown, risk contribution, stress/scenario
- each diagnostics group can surface a backend-ranked top callout with explicit selection-rule provenance and rationale
- desktop renders backend-ranked diagnostics callouts directly and does not infer salience from array order
- a reviewed hypothetical replay can now be saved locally as an immutable versioned proposal artifact within the workspace
- the latest saved proposal can now be reviewed in a proposal-specific readout that is rendered from saved artifact data only, without depending on active draft or live replay state
- overlay-aware hypothetical replay now exists as a narrow backend slice for `benchmark_trend_overlay_v1` applied to the hypothetical candidate only
- replay-scoped Monitoring now lives inside `Workspace`, after the shell and before the lower-level builder, and it is not a separate continuous monitoring system yet
- Monitoring-to-Workspace continuity is currently a narrow explicit handoff into shell sections, not a persistent alert/review-history workflow

### Required comparison surfaces
- total and annualized return
- volatility and downside volatility
- drawdown profile
- tracking error and information ratio
- factor exposure change
- risk contribution change
- concentration change
- overlap and active share change
- scenario sensitivity change
- turnover and implementation cost change

### Product rule
No candidate portfolio should be shown without:
- implementation assumptions
- truth-class label
- replay methodology
- risk and concentration delta

Current boundary before replay/construction:
- seeded candidates and replacement intents are metadata-only review objects
- they must not be treated as candidate portfolio truth, replay output, or applied portfolio change
- formed candidates, constructed candidates, and draft-scoped hypothetical replays are also review artifacts only until explicitly saved as immutable proposal artifacts

## Overlay Roadmap

Overlays should be treated as explicit, testable sleeves applied to a base portfolio.

Current implemented slice:
- overlay-aware hypothetical replay exists at `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
- current overlay scope is intentionally narrow:
  - only `benchmark_trend_overlay_v1`
  - only one overlay at a time
  - only replay integration, not execution or scheduling
  - only candidate-side application, not baseline mutation
  - `risk_reduced` scales risky candidate weights by `0.35` and sends residual weight to synthetic replay cash `__CASH__`
- a legacy generic overlay preview path still exists separately and should not be treated as the canonical forward path without further cleanup

### Initial overlay types
- trend filter overlay
- volatility-targeting overlay
- risk-on / risk-off overlay
- defensive benchmark substitution overlay
- cash-raising overlay under risk triggers

### Overlay engine responsibilities
- accept a baseline portfolio and overlay spec
- compute overlay-adjusted target weights
- replay combined portfolio behavior
- report risk, return, and exposure impact
- isolate overlay contribution from base portfolio behavior

### Overlay rules
- overlays must be transparent, parameterized, and reversible
- overlay effects must be attributable
- overlays must not mutate imported portfolio truth

## Monitoring Roadmap

Monitoring should become a continuous review layer, not a dashboard afterthought.

### First monitoring surfaces
- factor drift
- concentration drift
- benchmark-relative drift
- volatility regime change
- drawdown escalation
- turnover creep
- unresolved data-quality degradation
- overlay trigger state

### Monitoring engine requirements
- versioned monitor definitions
- scheduled or on-demand evaluation
- explicit thresholds and hysteresis rules
- alert severity and confidence
- clear unavailable / degraded semantics

## Optimization Roadmap

Optimization should be introduced only after rule-based construction is strong.

### Allowed optimization uses
- constrained minimum volatility
- tracking-error-aware refinement
- turnover-aware refinement
- exposure target matching
- risk-budget balancing

### Non-goals
- unconstrained mean-variance optimization
- optimizer-generated portfolios without interpretable constraints
- expected-return forecasting as a required input

### Optimization rules
- optimization must start from a candidate or benchmark anchor
- every objective must be regularized and bounded
- infeasible constraint sets must fail explicitly
- optimizer outputs must include shadow diagnostics: turnover, concentration, exposure, and stability

## Financial Accuracy Requirements

This is a gating layer, not a polish task.

### Hard requirements
- adjusted-close or total-return-aware inputs for all return-based analytics
- explicit methodology strings for every economically meaningful engine
- truth-class metadata on every analytics and backtest payload
- provenance for benchmark, factor, and synthetic-history inputs
- clear degraded semantics for missing, stale, unresolved, or proxy-based data
- formula traceability from UI field to schema field to implementation

### Validation requirements
- lock formulas with tests
- add dataset-quality assertions for price basis and date alignment
- separate financially exact imported-history metrics from approximations
- expose reliability metadata for factor and diagnostics outputs
- persist versioned inputs for replay reproducibility

### Minimum reliability fields
- methodology id
- price basis
- observation count
- lookback window
- factors used vs dropped
- missing-data coverage
- model reliability status
- provenance / truth class

## Delivery Plan

### Stage 1: Financial Core Hardening
- harden adjusted-price and benchmark assumptions
- normalize truth-class and provenance metadata
- add reliability fields to diagnostics and factor outputs
- update methodology docs and tests together

Exit: current analytics are decision-grade or explicitly degraded.

### Stage 2: Ranking Engine
- define universe, filter, component, and composite contracts
- implement reproducible ranking runs
- expose ranked universes and score breakdowns

Current partial state: ETF ranking and intent-bound replacement ranking already exist; remaining work is generalization, persisted run identity, and broader universe support.

Exit: rankings are first-class inputs to construction workflows.

### Stage 3: Construction Engine
- implement rule-based weight builders
- add explicit constraint and turnover models
- produce candidate portfolios from ranking outputs

Current partial state: single-replacement formation/construction already exist; replay provenance for constructed candidates is now explicit in the hypothetical replay contract; remaining work is broader construction modes, richer constraints, and stronger constraint-validation lineage into replay outputs.

Exit: candidate portfolios can be built systematically and audited.

### Stage 4: Improvement Workspace
- make baseline-vs-candidate the primary workflow
- add replay, diagnostics delta, and proposal persistence
- optimize UI around PM decisions rather than debug surfaces
- add proposal-specific saved-artifact review/readout so recorded proposals remain inspectable after reload and outside active draft context

Current partial state: replacement-intent replay, PM-first diagnostics review, proposal persistence/readout, and overlay-aware replay already exist in narrow form.

Exit: users can decide whether a change improves the portfolio.

### Stage 5: Overlay and Monitoring
- implement transparent overlay specs
- add drift, regime, and risk monitors
- persist alerts and review history

Current partial state: one transparent overlay-aware replay path exists; monitoring remains the larger unfinished slice.

Exit: the platform supports ongoing portfolio discipline.

### Stage 6: Constrained Optimization
- add bounded optimizers behind rule-based baselines
- keep optimization explainable and constraint-led
- compare optimized vs rule-based candidates

Exit: optimization improves candidates without becoming the product’s logic center.

### Stage 7: Research Expansion
- broaden ranking experiments, sleeves, and reusable templates
- expand datasets and cross-sectional research depth
- support more robust validation workflows

Exit: the platform operates as a true personal quant research lab.

## Immediate Priorities

1. turn financial-accuracy requirements into enforced engine contracts
2. tighten canonical docs and replay/construction provenance so implemented slices are accurately described
3. generalize the ranking engine beyond the current ETF-focused slices
4. generalize rule-based portfolio construction beyond current single-replacement flows
5. add broader overlays and monitoring only after baseline construction/replay contracts are clean

## Definition of Done for the Pivot

The pivot is successful when the project can:
- import and reconstruct true portfolio state reliably
- rank a defined investable universe reproducibly
- construct a candidate portfolio under explicit constraints
- compare baseline vs candidate with historically replayed evidence
- apply transparent overlays and monitor drift over time
- explain every material metric with clear methodology and provenance
