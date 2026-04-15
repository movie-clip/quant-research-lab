# Quant Framework Research

This document captures recommended research/design directions for a personal-investing quant framework built on this project.

Design goals:
- deterministic and financially auditable
- local-first and reproducible
- explicit truth classes and degraded states
- thin desktop UI with finance logic in Python engines

Recommended implementation order:
1. Core portfolio diagnostics
2. ETF ranking model
3. Portfolio construction rules
4. Allocation replay for current vs candidate
5. Simple trend overlay

# Core Portfolio Diagnostics
## Objective
- Build a deterministic diagnostics layer for factor exposure, benchmark overlap, drawdown, volatility, concentration, and risk decomposition.

## Why It Matters
- Personal portfolios often hide concentration by ticker count while remaining concentrated by factor, sector, or benchmark overlap.
- Decision-grade diagnostics improve rebalance review, benchmark comparison, and candidate-vs-current analysis.

## Recommended Methodology
- Keep current-state diagnostics in `exposure_engine.py`.
- Keep history-aware diagnostics in `diagnostics_engine.py`.
- Keep daily-state and drawdown-path support in `dashboard_history_engine.py`.
- Use snapshot current-state analytics for look-through, overlap, and current-state concentration.
- Use broker-truth historical diagnostics only when imported portfolio replay/history is actually available.
- Treat the current `run_diagnostics_engine(...)` path as synthetic snapshot-history diagnostics, even when it produces full-looking historical sections, because it currently rebuilds history from the snapshot plus market data.

## Core Formulas
- `w_i = market_value_i / total_portfolio_market_value`
- `overlap_weight = sum(min(w_i, b_i))`
- `active_share = 0.5 * sum(abs(w_i - b_i))`
- `daily_return_t = ((V_t - CF_t) / V_(t-1)) - 1`
- `drawdown_t = (W_t / running_peak_t) - 1`
- `vol = stdev(r) * sqrt(252)`
- `HHI = sum(w_i^2)`
- `sigma_p = sqrt(w' * Sigma * w)`
- `risk_share_i = (w_i * MRC_i) / sigma_p`

## Required Inputs
- Portfolio snapshot, cash balances, benchmark symbol
- Adjusted-close or total-return-aware histories
- Benchmark holdings for overlap
- ETF holdings for look-through
- Factor proxy histories from the factor registry
- Historical portfolio states or history context for historical sections

## Output Contract
- Explicit section-level status/confidence/note fields
- Separate sections for:
  - current-state exposure and overlap
  - drawdown
  - volatility
  - factor diagnostics
  - risk decomposition
  - current-state concentration
  - history-derived risk concentration

## Risk Controls And Guardrails
- Missing benchmark holdings -> `null`, never fake zero overlap
- Missing history -> unavailable historical sections
- Missing factor histories -> partial/unavailable, never guessed
- Never present synthetic history as broker-truth history

## Project Adaptation
- Backend:
  - `services/quant-engine/app/services/exposure_engine.py`
  - `services/quant-engine/app/services/diagnostics_engine.py`
  - `services/quant-engine/app/services/dashboard_history_engine.py`
- Schemas:
  - extend existing diagnostics and exposure schemas with explicit provenance / availability where needed
- Desktop:
  - render section badges and degraded notes directly from engine outputs

## Validation And Tests
- Weight, overlap, drawdown, volatility, and contribution sum-checks
- Truth-class tests for imported base vs variant vs snapshot-only paths
- Edge cases for missing benchmark holdings, short histories, unresolved ETFs, large cash positions

## MVP Scope
- Current-state overlap and current-state concentration
- Historical drawdown, volatility, beta, tracking error
- Rolling ETF-proxy factor loadings
- Position/factor risk contribution plus history-derived risk concentration

## Future Extensions
- Drawdown duration and recovery diagnostics
- Asset-class-aware decomposition beyond equity-heavy portfolios
- More robust covariance estimation

# ETF Ranking Model
## Objective
- Rank ETFs within the same mandate using momentum, volatility, drawdown, liquidity, and mapping fit.

## Why It Matters
- Many ETFs offer similar exposure but differ materially in path risk, tradability, and implementation fit.
- A mandate-aware ranking model helps choose substitutes without turning into a hype screener.

## Recommended Methodology
- Use a two-stage flow: eligibility first, ranking second.
- Only compare ETFs inside the same peer group.
- Rank monthly, not daily.
- Normalize components cross-sectionally with bounded percentile ranks.

## Core Formulas
- `momentum_12_1 = (P_(t-21) / P_(t-252)) - 1`
- `momentum_6_1 = (P_(t-21) / P_(t-126)) - 1`
- `raw_momentum = 0.6 * momentum_12_1 + 0.4 * momentum_6_1`
- `realized_vol_126 = stdev(r) * sqrt(252)`
- `max_drawdown_252 = abs(min(drawdown_t))`
- `liquidity = log(1 + median(close * volume over 60d))`
- `composite = 0.40 * momentum + 0.20 * volatility + 0.20 * drawdown + 0.10 * liquidity + 0.10 * mapping_fit`

## Required Inputs
- Adjusted-close histories
- Daily volume histories
- ETF metadata and mandate labels
- Mapping-fit metadata aligned with factor/UCITS registry direction

## Output Contract
- Ranked rows with:
  - composite score
  - component raw values
  - normalized scores
  - exclusions and rationale
  - confidence and warnings

## Risk Controls And Guardrails
- Exclude mandate mismatches before scoring
- Conservative missing-data handling
- Monthly reranking and minimum score gap before switching
- No hidden ML or non-deterministic ranking

## Project Adaptation
- Recommended backend location:
  - MVP in `services/quant-engine/app/services/strategy_lab.py`
  - later dedicated `ranking_engine.py`
- Data sources:
  - `MarketDataService`
  - `InstrumentRegistry`
  - factor / mapping metadata already used in the project

## Validation And Tests
- Formula tests for momentum/volatility/drawdown/liquidity
- Determinism tests and missing-data tests
- Mandate eligibility tests
- Regression snapshots on pinned ETF universes and dates

## MVP Scope
- Curated ETF universes
- Five requested components only
- Long-only, monthly ranking
- Deterministic exclusions and rationale fields

## Future Extensions
- Expense ratio, spread, AUM, tracking difference
- Turnover-aware switching thresholds
- Regime-aware score weighting

# Portfolio Construction Rules
## Objective
- Turn ranked candidates plus current diagnostics into auditable target weights under explicit rules.

## Why It Matters
- Ranking does not control concentration, overlap, or beta by itself.
- Construction rules are the safety layer between ideas and capital allocation.

## Recommended Methodology
- Use a staged deterministic process:
  1. apply eligibility filters
  2. choose investable set
  3. create seed weights from ranking scores
  4. repair against hard constraints
  5. choose best feasible portfolio by soft preferences
- Hard constraints define feasibility; soft preferences rank feasible outcomes.

## Core Formulas
- `sum(w_i) = 1`
- `0 <= w_i <= w_i_max`
- `N_eff = 1 / sum(w_i^2)`
- `HHI = sum(w_i^2)`
- `beta_p = sum(w_i * beta_i)`
- `b_k = sum(w_i * f_i,k)`
- `turnover = 0.5 * sum(abs(w_i - w_i_current))`

## Required Inputs
- Ranked ETF universe
- Current portfolio weights
- Current diagnostics and factor model outputs
- Constraint set and soft-preference parameters

## Output Contract
- Seed weights vs final target weights
- Constraint report with binding rules
- Predicted diagnostics and turnover
- Status: `accepted`, `accepted_with_repairs`, or `rejected_infeasible`

## Risk Controls And Guardrails
- Detect infeasible rule sets early
- Never treat missing factor data as zero exposure
- Fall back or reject explicitly when factor reliability is weak
- Keep long-only, fully invested assumptions for MVP

## Project Adaptation
- New construction engine/module in `services/quant-engine`
- Consume ranking outputs, current portfolio snapshot, diagnostics outputs, and factor model outputs
- Feed candidate targets into allocation replay rather than mixing construction with replay logic

## Validation And Tests
- Formula tests for caps, `HHI`, `N_eff`, beta, turnover
- Hard-vs-soft preference tests
- Infeasibility tests and degraded-data tests

## MVP Scope
- Max position size
- Minimum active names / `N_eff`
- Target beta band
- Max factor concentration
- Soft turnover preference and ranking fidelity

## Future Extensions
- Sleeve budgets
- Overlap caps
- Liquidity limits
- Tax-aware rules
- Bounded optimization as a later refinement layer

# Allocation Replay For Current vs Candidate Portfolio Decisions
## Objective
- Compare the current portfolio against a candidate allocation and show whether the change is materially better after turnover, cost, and diagnostics deltas.

## Why It Matters
- Allocation changes can look better before costs, drift, or factor/risk tradeoffs are included.
- Investors need a baseline-vs-candidate review, not just standalone backtests.

## Recommended Methodology
- Replay baseline and candidate over the same window and same capital base.
- Include transition turnover, slippage/commission assumptions, and optional dated contributions.
- Compare outcomes on three layers:
  - implementation
  - portfolio performance/risk
  - diagnostics deltas

## Core Formulas
- `delta_w_i = w_candidate_i - w_baseline_i`
- `turnover_0 = 0.5 * sum(abs(delta_w_i))`
- `cost_t = traded_notional_t * (commission_bps + slippage_bps) / 10000`
- `r_net_t = (V_t - V_(t-1) - CF_t) / V_(t-1)`
- `improvement_M = M_candidate - M_baseline`

## Required Inputs
- Baseline weights
- Candidate target weights
- Replay window and benchmark
- Cost assumptions
- Initial capital / current market value
- Optional contribution schedule
- Factor/risk histories for diagnostics deltas

## Output Contract
- Baseline replay block
- Candidate replay block
- Improvement-vs-baseline block
- Diagnostics comparison block
- Provenance for replay-derived and synthetic diagnostics outputs

## Risk Controls And Guardrails
- Enforce common-date alignment
- Keep long-only, sum-to-one validation for MVP
- Separate cash-flow effects from performance
- Mark proxy/missing-history states as degraded
- Present cost assumptions explicitly and with sensitivity ranges when possible

## Project Adaptation
- Extend the current allocation replay / backtest foundation rather than building a separate toy engine
- Reuse diagnostics comparison concepts already present in the project
- Keep explicit provenance aligned with current backtest diagnostics provenance style

## Validation And Tests
- Identical baseline/candidate -> near-zero deltas
- Known turnover/cost toy cases
- Contribution-adjusted return tests
- Delta reconciliation tests
- Provenance tests

## MVP Scope
- Current vs candidate weights over one replay window
- One-time transition and ongoing rebalance turnover
- Simple contribution schedule
- Diagnostics comparison and cost drag

## Future Extensions
- Asset-class-specific slippage schedules
- Tax-aware transitions
- Multi-stage rebalance paths
- Confidence scoring for replay diagnostics

# Simple Trend Overlay For Risk Reduction
## Objective
- Add a simple deterministic overlay that reduces risky exposure when broad market structure weakens.

## Why It Matters
- Ranking and construction alone may still keep the portfolio fully exposed during deep downtrends.
- A slow overlay can reduce drawdown and improve behavioral stability without becoming a noisy market-timing toy.

## Recommended Methodology
- Use one broad market benchmark as the overlay driver.
- Evaluate monthly.
- Prefer a 10-month SMA on month-end observations.
- Add hysteresis and confirmation.
- Keep the overlay binary for MVP:
  - `risk_on`
  - `risk_reduced`
- Apply the overlay after ranking/construction and before replay.

## Core Formulas
- `SMA_L(t) = average(P_t ... P_(t-L+1))`
- `R_t = P_t / SMA_L(t)`
- `risk_on` when `R_t >= 1 + h`
- `risk_reduced` when `R_t <= 1 - h`
- require confirmation over `c` review periods
- `m_t = 1.00` in `risk_on`
- `m_t = 0.35` in `risk_reduced`
- `w_final_i,t = m_t * w_core_i,t`

## Required Inputs
- Benchmark history
- Overlay spec: window, hysteresis band, confirmation, multiplier
- Candidate risky-sleeve weights from construction
- Optional defensive destination policy

## Output Contract
- Current state
- Signal metrics
- State history / transition log
- Allocation adjustments
- Provenance and degraded-status metadata

## Risk Controls And Guardrails
- Slow schedule only
- Adjusted-close / total-return-aware history required
- Use hysteresis plus confirmation together
- Default reduced capital to cash unless a defensive asset is explicitly configured
- Overlay may scale sleeves, not bypass construction constraints

## Project Adaptation
- Overlay engine sits between construction output and allocation replay input
- Ranking remains unchanged
- Construction determines relative risky weights
- Overlay changes total risky budget and hands adjusted targets to replay

## Validation And Tests
- State-machine tests for trend, hysteresis, and confirmation
- No-lookahead and review-date enforcement tests
- Defensive fallback tests
- Replay integration tests

## MVP Scope
- One benchmark-driven binary overlay
- Monthly review schedule
- 10-month SMA, 1% band, 2-period confirmation
- Risky sleeve 100% -> 35% when reduced
- Cash as default defensive destination

## Future Extensions
- Partial states
- Breadth confirmation
- Region-specific benchmark overlays
- Portfolio-aware overlays with drawdown triggers
