# OpenCode Spec: Portfolio Improvement Workspace

```text
Build a new `Portfolio Improvement Workspace` on top of the existing portfolio allocation backtest flow.

Important product constraint:
- Do NOT add narrative explanations, educational text, or recommendation text
- Only provide structured controls, before/after metrics, comparison tables, charts, and diagnostics
- The user will interpret the outputs manually

Goal:
Turn the current allocation backtest into a professional portfolio-construction workflow that helps the user understand how portfolio changes affect performance, risk, concentration, and factor exposures.

Core principle:
- this is not a strategy backtest workspace
- this is a portfolio-construction and what-if workspace
- the key workflow is `Current Portfolio vs Candidate Portfolio`

The user should be able to:
- start from the imported portfolio as a baseline
- edit/add/remove instruments in a candidate portfolio
- rerun a historical allocation replay
- compare before/after portfolio behavior
- see how risk, drawdown, concentration, and factor exposures changed

================================
PRODUCT STRUCTURE
================================

Refactor the current allocation backtest experience into these sections:

1. `Baseline Portfolio`
2. `Candidate Portfolio Builder`
3. `Historical Replay Comparison`
4. `Before / After Diagnostics`
5. `Implementation Details`

This should become the main portfolio-improvement workflow in the backtest area.

The older signal/strategy backtest can remain available, but should be visually and conceptually secondary.

================================
SECTION 1: BASELINE PORTFOLIO
================================

Goal:
- seed the comparison using the imported portfolio or another explicit reference portfolio

Required behavior:
- if imported portfolio data exists, derive baseline weights automatically from current market values
- use those weights as default `reference_weights`
- if imported portfolio is unavailable, keep manual reference entry as fallback

Required UI:
- a `Use Current Portfolio` action that populates the baseline/reference portfolio automatically
- baseline summary table showing:
  - symbol
  - current weight
  - market value

Required backend support:
- if useful, expose a helper payload that returns current imported weights in normalized form
- or derive them client-side from imported snapshot if already available in the analysis payload

================================
SECTION 2: CANDIDATE PORTFOLIO BUILDER
================================

Goal:
- make candidate construction much easier than the current plain form

Required controls:
- add row
- remove row
- edit symbol
- edit weight
- normalize weights to 100%
- copy baseline to candidate
- clear candidate

Optional but recommended:
- lock some rows from normalization
- small cash sleeve support later

Required UI behavior:
- show total candidate weight live
- visually warn when total != 1.0
- keep candidate and baseline side-by-side

Professional workflow rule:
- candidate editing must feel iterative and fast
- the panel should support repeated reruns after small changes

================================
SECTION 3: HISTORICAL REPLAY COMPARISON
================================

Goal:
- compare baseline vs candidate on historical allocation replay

This reuses the current portfolio allocation backtest engine, but comparison becomes a primary part of the product.

Required outputs:
- baseline equity curve
- candidate equity curve
- baseline drawdown curve
- candidate drawdown curve
- metrics comparison table

Required metrics:
- total return
- annualized return
- annualized volatility
- downside volatility
- max drawdown
- sharpe ratio
- sortino ratio
- benchmark return
- excess return
- tracking error
- information ratio
- beta vs benchmark
- correlation vs benchmark
- total turnover
- total cost paid

Comparison block should show:
- baseline value
- candidate value
- difference

Do not show diff-only cards without the raw baseline/candidate values.
Professionals need all 3:
- baseline
- candidate
- delta

================================
SECTION 4: BEFORE / AFTER DIAGNOSTICS
================================

This is the most important addition.

Goal:
- show how the candidate portfolio changed portfolio characteristics, not just return metrics

Required diagnostic categories:

1. `Factor Exposure Change`
- compare baseline vs candidate current factor loadings
- show delta per factor

2. `Volatility / Drawdown Change`
- compare baseline vs candidate:
  - annualized vol
  - downside vol
  - max drawdown
  - tracking error

3. `Risk Contribution Change`
- compare baseline vs candidate factor risk shares
- compare baseline vs candidate position concentration

4. `Concentration Change`
- compare:
  - top 1 position risk share
  - top 5 position risk share
  - factor HHI
  - position HHI

5. `Stress Scenario Change`
- compare baseline vs candidate scenario outcomes using the existing scenario engine or a comparable candidate run

Required product rule:
- this section must be built from the same baseline/candidate portfolios that were backtested
- do not mix unrelated analytics snapshots

================================
SECTION 5: IMPLEMENTATION DETAILS
================================

Goal:
- show what the candidate portfolio implies operationally

Required outputs:
- starting weights
- ending weights
- rebalance events
- trade log
- total turnover
- total cost
- instrument metadata

This remains useful, but should come after the risk/performance comparison sections.

================================
BACKEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `services/quant-engine/app/backtests/portfolio_engine.py`
- `services/quant-engine/app/services/portfolio_backtest_engine.py`
- `services/quant-engine/app/schemas/research.py`
- `services/quant-engine/app/api/routes/backtests.py`
- potentially reuse analytics logic from:
  - `services/quant-engine/app/analytics/risk.py`

The current allocation backtest response should be extended so the compare workflow can support before/after diagnostics.

Required additions:

1. `baseline_diagnostics`
2. `candidate_diagnostics`
3. `diagnostics_comparison`

Suggested structure:

```python
class PortfolioDiagnosticsSnapshot(BaseModel):
    factor_snapshot: list[SnapshotItem]
    volatility_snapshot: VolatilitySnapshot | None = None
    risk_contribution: RiskContributionBreakdownPayload | None = None
    stress_scenarios: list[StressScenarioResult] = []
```

```python
class PortfolioDiagnosticsComparisonRow(BaseModel):
    key: str
    label: str
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
```

```python
class PortfolioImprovementComparison(BaseModel):
    factor_exposure_changes: list[PortfolioDiagnosticsComparisonRow]
    volatility_changes: list[PortfolioDiagnosticsComparisonRow]
    concentration_changes: list[PortfolioDiagnosticsComparisonRow]
    stress_scenario_changes: list[PortfolioDiagnosticsComparisonRow]
```

Then extend:

```python
class PortfolioAllocationBacktestResponse(BaseModel):
    methodology: str
    reference_result: AllocationBacktestResult | None = None
    candidate_result: AllocationBacktestResult
    comparison: AllocationBacktestComparison | None = None
    reference_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    candidate_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    diagnostics_comparison: PortfolioImprovementComparison | None = None
```

================================
BACKEND IMPLEMENTATION RULES
================================

Important rule:
- diagnostics must be recomputed from the baseline and candidate portfolio definitions used in the backtest flow

Do not reuse the imported portfolio analytics blindly for the candidate portfolio.

Required approach:
- for each tested portfolio, derive a synthetic portfolio context from the candidate/reference weights
- generate the same or comparable analytics used elsewhere:
  - factor model snapshot
  - volatility snapshot
  - risk contribution
  - stress scenarios

If full daily synthetic diagnostics are too heavy for v1:
- start with snapshot-level diagnostics only
- but they must still be computed from the candidate/reference portfolio definition and aligned historical data

================================
FRONTEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `apps/desktop/src/features/backtest/PortfolioAllocationBacktestPanel.tsx`
- `apps/desktop/src/features/backtest/BacktestWorkspacePanel.tsx`
- `apps/desktop/src/features/portfolio/types.ts`

Rework the current panel into a workspace-like layout.

Recommended order:

1. `Baseline Portfolio`
2. `Candidate Portfolio Builder`
3. `Replay Summary`
4. `Replay Charts`
5. `Before / After Diagnostics`
6. `Implementation Details`

Required UI improvements:

1. Baseline controls
- `Use Current Portfolio`
- `Copy Baseline -> Candidate`

2. Candidate builder controls
- add/remove row
- normalize
- clear

3. Replay summary table
Show baseline / candidate / delta columns for key metrics.

4. Diagnostics comparison blocks
Add compact tables/cards for:
- factor exposure changes
- volatility changes
- concentration changes
- stress scenario changes

5. Implementation details block
- keep assumptions, metadata, rebalance events, and trades here

================================
WHAT TO DE-EMPHASIZE
================================

Do not center the experience around:
- strategy backtest presets
- signal backtests
- isolated equity curve without before/after diagnostics

Those can remain in the workspace, but the portfolio improvement workflow should be the primary one.

================================
PROFESSIONAL PRODUCT RULES
================================

The final workflow should answer these professional questions:
- if I change weights, how do return and drawdown change?
- if I change weights, how do factor exposures change?
- if I change weights, how does total risk concentration change?
- if I reduce one sleeve and add another, what is the trade-off in tracking error and benchmark sensitivity?

If the feature cannot answer those, it is not yet a professional portfolio-improvement workspace.

================================
TESTING
================================

Add backend tests for:
- reference and candidate diagnostics both populate
- diagnostics comparison rows are computed correctly
- baseline and candidate comparison uses the same aligned dates

Add frontend tests for:
- baseline can be copied to candidate
- candidate weights can be normalized
- comparison table renders baseline/candidate/delta values
- before/after diagnostics section renders when present

================================
DELIVERY NOTES
================================

Implement in this order:

1. baseline seeding from current portfolio
2. candidate builder improvements
3. replay summary with baseline/candidate/delta layout
4. diagnostics payload extension
5. before/after diagnostics UI
6. implementation details cleanup
7. tests

When finished, report:
- files changed
- what portfolio-improvement workflow was added
- what before/after diagnostics were implemented
- what remains manual vs automated
```
