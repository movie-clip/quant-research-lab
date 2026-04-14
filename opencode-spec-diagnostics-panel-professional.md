# OpenCode Spec: Diagnostics Panel (Professional-Only)

```text
Refactor the current `Diagnostics` panel into a more professional portfolio-manager workflow.

Important product constraint:
- Do NOT add narrative explanations, educational text, or recommendation text
- Only provide raw metrics, structured reliability fields, contribution tables, concentration metrics, and monitoring data
- The user will interpret the outputs manually

Goal:
Transform the current diagnostics view from a quant-debug-style panel into a professional portfolio risk review panel.

Core principle:
- prioritize tools that professionals actually use for portfolio balancing
- demote or remove tools that are mostly heuristic/debug-oriented

The final panel should emphasize:
1. current risk contribution
2. concentration
3. model reliability
4. factor change monitoring

It should NOT emphasize:
- raw “top mover” style diagnostics as the main decision surface
- heuristic flag chips as the main product output

================================
CURRENT PROBLEMS TO FIX
================================

Current implementation problems:

1. Factor risk contribution is not professional enough
- current backend uses a simplified variance proxy based largely on `loading^2 * factor variance`
- this ignores covariance interaction across factors
- professionals use factor covariance-based component contributions

2. Specific risk share is not fully reconciled
- factor-side variance and residual variance should come from a consistent total-variance framework

3. Factor shift diagnostics are too heuristic-first
- current threshold flags (`S20`, `S60`, `STAB`, `COL`, `VOL`) are acceptable as internal signals but too noisy as primary output

4. UI prioritization is wrong for portfolio management
- current panel leads with shifts and biggest movers
- professionals care more about current risk, concentration, and model reliability

================================
TARGET PANEL STRUCTURE
================================

Refactor the panel into these sections, in this order:

1. `Risk Contribution`
2. `Risk Concentration`
3. `Model Reliability`
4. `Factor Change Monitor`

Optional later:
5. `Stress Contribution`

================================
SECTION 1: RISK CONTRIBUTION
================================

This becomes the main diagnostics section.

Backend requirements:
- replace simplified factor contribution logic with covariance-based factor contribution logic
- use latest valid 60d factor loadings by default
- use aligned factor return covariance over the same window

Professional formula:
- let `b` = factor loading vector
- let `Sigma_f` = factor covariance matrix
- factor variance = `b' Sigma_f b`
- factor component contribution should be derived from the covariance framework, not diagonal-only approximations

Required outputs per factor:
- `key`
- `label`
- `us_proxy`
- `loading`
- `factor_volatility`
- `variance_contribution`
- `risk_share`

Required portfolio-level outputs:
- `factor_total_variance`
- `specific_variance`
- `total_variance`
- `specific_risk_share`
- `factor_risk_share_total`
- `residual_volatility`

Acceptance requirement:
- factor and specific shares should reconcile consistently to total variance within rounding tolerance

UI requirements:
- make this the first visible diagnostics block
- default sort by descending `risk_share`
- no prose commentary

================================
SECTION 2: RISK CONCENTRATION
================================

This becomes the second section.

Required outputs:
- `top_1_factor_risk_share`
- `top_3_factor_risk_share`
- `top_1_position_risk_share`
- `top_5_position_risk_share`
- `factor_hhi`
- `position_hhi`

Optional later:
- effective number of bets from HHI

UI requirements:
- compact numeric cards only
- no narrative interpretation
- keep factor and position concentration side-by-side if layout allows

================================
SECTION 3: MODEL RELIABILITY
================================

This is missing today as a first-class section.

Backend should expose a dedicated structured block, for example:
- `model_reliability`

Required fields:
- `window_days`
- `observation_count`
- `r_squared`
- `residual_volatility`
- `collinearity_pair_count`
- `max_abs_factor_correlation`
- `status`
- `confidence`

Optional but recommended:
- `factor_count_used`
- `missing_factor_count`
- `stability_score`

Definitions:
- `r_squared` and `residual_volatility` should come from the same 60d factor model snapshot used in diagnostics
- `collinearity_pair_count` should count flagged pairs for the selected diagnostics window
- `max_abs_factor_correlation` should reflect the current diagnostics window, not max-ever history

UI requirements:
- create a dedicated `Model Reliability` block
- show only structured numeric/status values
- do not bury this inside factor shift diagnostics

================================
SECTION 4: FACTOR CHANGE MONITOR
================================

Keep factor change monitoring, but demote it to a secondary monitoring tool.

Backend changes:
- keep current shift snapshot fields for now
- add more professional fields over time:
  - `change_percentile_20d`
  - `change_percentile_60d`
  - `window_divergence`
  - `persistence_score`

For v1 of this refactor:
- retain existing shift snapshot table
- keep flags if already implemented
- remove emphasis on “Largest Positive/Negative Shifts” as major visual sections

UI requirements:
- one compact monitoring table only
- do not lead with separate top-positive/top-negative/top-absolute sections
- optional filters can remain
- keep confidence field
- keep raw values visible

Recommended columns:
- Factor
- Proxy
- Category
- 20d Loading
- 60d Loading
- 252d Loading
- 20d Change
- 60d Change
- Gap 20/60
- Gap 60/252
- Confidence
- Flags (optional, low emphasis)

================================
REMOVE OR DOWNGRADE
================================

Downgrade or remove these as primary sections:
- `Largest Positive Shifts 20d`
- `Largest Negative Shifts 20d`
- `Largest Absolute Shifts 20d`
- `Largest Absolute Shifts 60d`

If retained, move them behind an expandable advanced section or remove entirely.

Reason:
- professionals do not usually balance portfolios by looking at “biggest factor movers” lists first

================================
BACKEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `services/quant-engine/app/analytics/risk.py`
- `services/quant-engine/app/schemas/reconciliation.py`
- `services/quant-engine/app/services/import_engine.py`
- related tests under `services/quant-engine/app/tests/`

Add or revise these backend blocks:

1. `risk_contribution_breakdown`
- replace simplified factor contribution math with covariance-based component contribution math

2. `model_reliability`
- add a dedicated response block for current diagnostics window

3. `factor_shift_diagnostics`
- keep as monitoring-oriented data, not the main decision block

Suggested new schema:

```python
class ModelReliabilitySnapshot(BaseModel):
    window_days: int
    observation_count: int
    r_squared: float | None = None
    residual_volatility: float | None = None
    collinearity_pair_count: int
    max_abs_factor_correlation: float | None = None
    factor_count_used: int
    missing_factor_count: int
    status: str
    confidence: str
```
```

Add to the imported diagnostics/upload contract:
- `model_reliability: ModelReliabilitySnapshot`

================================
FACTOR CONTRIBUTION MATH REQUIREMENT
================================

Do not use diagonal-only factor approximation as the main production result.

Use covariance-based factor component contribution.

Required implementation behavior:
- build aligned factor return matrix over diagnostics window
- compute factor covariance matrix
- use latest valid loading vector for same window
- compute total factor variance from covariance matrix
- compute factor component variance contributions consistently
- reconcile specific variance against residual variance from the model

Return deterministic values only.

================================
FRONTEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `apps/desktop/src/features/portfolio/DiagnosticsPanel.tsx`
- `apps/desktop/src/features/portfolio/types.ts`

Refactor panel order to:

1. `Risk Contribution`
2. `Risk Concentration`
3. `Model Reliability`
4. `Factor Change Monitor`

UI rules:
- no prose interpretation
- no recommendation text
- no lead section focused on biggest movers
- emphasize current risk and concentration first

Recommended UI structure:

1. `Risk Contribution`
- factor table
- position table
- specific risk summary card row

2. `Risk Concentration`
- concentration cards

3. `Model Reliability`
- compact cards/table for current model quality

4. `Factor Change Monitor`
- one monitoring table with filters and sort controls

Optional:
- collapse advanced diagnostics by default if screen becomes too dense

================================
TESTING
================================

Add backend tests for:
- covariance-based factor contribution reconciles with total factor variance
- specific variance and factor variance sum consistently
- model reliability fields populate correctly from current 60d model snapshot
- collinearity pair count and max abs correlation are correct

Add frontend tests for:
- diagnostics section order is updated
- largest shift tables are removed or hidden
- model reliability block renders
- risk contribution remains the first major section

================================
DELIVERY NOTES
================================

Implement in this order:

1. fix factor contribution math
2. add model reliability payload
3. refactor DiagnosticsPanel order and layout
4. remove or demote largest-shift sections
5. update tests

When finished, report:
- files changed
- whether factor contribution now uses covariance-based math
- what reliability fields were added
- what sections were removed, demoted, or reordered
```
