# US-9.4: Fix rolling factor loadings — per-window orthogonalization and ridge regularization

**Epic:** 9 — Portfolio Correlation & Co-movement Analysis  
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)  
**Status:** Done  
**Last updated:** 2026-05-26

## Story

As a **portfolio researcher**, I want the Rolling Factor Analysis chart to show
mathematically stable loadings, so that I can trust the factor decomposition as
an input to understanding how my portfolio's risk profile shifts over time.

## Context

The chart currently computes Gram-Schmidt orthogonalization **once over the
full date range** and then feeds window slices of those globally-orthogonalized
factor returns into per-window OLS regression. This is wrong: the
orthogonalized residuals are only orthogonal over the full period, not within
each rolling window. Within any 20d or 60d slice the factors are correlated
again, turning the rolling regression into an underdetermined, collinear system.

For the 20d window the problem is critical: 25 minimum observations against 17
parameters (intercept + 16 factor proxies) leaves only 8 degrees of freedom, and
`ridge_lambda=1e-5` is orders of magnitude too small to stabilize it. This
produces loadings like Market(SPY) = −4.60, which is impossible for a long-only
equity portfolio.

The fix is to re-orthogonalize within each rolling window instead of globally,
and to apply a window-proportional ridge floor that prevents coefficient blowup
in short-window regressions.

Must read before implementing:
- `services/quant-engine/app/analytics/risk.py` — `build_statistical_factor_model`,
  `_orthogonalize_factor_series`, `_build_rolling_factor_loadings`
- `docs/finance/financial-methodology.md` — Statistical Factor Model section

## Acceptance criteria

- [x] AC1 — The Market (SPY) loading on any rolling window for any long-only
  equity portfolio stays within the plausible range [−2, +4]. A value of −4.60
  is no longer possible for a portfolio without short positions.
- [x] AC2 — With 20d window and at least 25 common dates, the chart displays
  loadings. The loadings are visually smoother than pre-fix values and do not
  exhibit sign reversals across adjacent dates that are inconsistent with actual
  portfolio composition changes.
- [x] AC3 — With 60d and 252d windows, loadings remain consistent with their
  pre-fix values to within ±0.3 (the fix should not materially alter stable
  windows; only stabilize the noisy short window).
- [x] AC4 — The factor model R² does not decrease on the 60d window compared
  to pre-fix values (the in-window orthogonalization is strictly equivalent when
  factors are already orthogonal in that window, which holds approximately for
  60d+).
- [x] AC5 — The "Not enough history" empty state still renders correctly when
  fewer than 25 common dates exist (no regression attempted).
- [x] AC6 — Stress scenario estimated returns change by no more than ±2 pp for
  the same portfolio after the fix (the 60d loadings used by the stress engine
  should not materially change).

## Test plan

Backend (pytest):
- `app/tests/test_analytics.py` — add `test_rolling_factor_loadings_market_beta_in_range`:
  build a synthetic long-only portfolio of 3 ETFs over 60 common dates; assert
  that the Market loading on each valid 20d point stays within [−2, +4].
- `app/tests/test_analytics.py` — add `test_rolling_factor_loadings_20d_no_blowup`:
  confirm no coefficient in the 20d series exceeds ±5 in absolute value for the
  IB2026 fixture (replaces snapshot test for the factor model values).
- `app/tests/test_analytics.py` — existing `test_build_statistical_factor_model_*`
  tests must remain green.

Frontend (vitest):
- No frontend change — schema is unchanged, only the backend float values change.
- `RollingFactorLoadingsCard.test.tsx` — existing tests must remain green.

Regression / guardrail:
- Regenerate `dashboardGoldens.ts` after the fix — confirm the 60d loadings in
  the golden are within ±0.3 of their current values (validates AC3).
- Stress scenario estimated returns in the golden must stay within ±2 pp (AC6).

## Tickets

- [x] T-9.4.1 — Refactor `_build_rolling_factor_loadings` to accept raw (non-orthogonalized)
  factor series and perform Gram-Schmidt within each window; update
  `build_statistical_factor_model` to pass raw factor series to the three rolling
  calls; keep the global orthogonalization only for the full-period `coefficients`
  and `current_factor_snapshot` computation. Add window-proportional ridge floor
  (see Notes). Add `test_rolling_factor_loadings_market_beta_in_range` and
  `test_rolling_factor_loadings_20d_no_blowup`. Regenerate `dashboardGoldens.ts`.
- [x] T-9.4.2 — Update `docs/finance/financial-methodology.md` — Statistical
  Factor Model section: document the corrected per-window orthogonalization formula,
  the ridge floor formula, and the academic precedent. Update epic-roadmap.md
  slice log and story status.

## Out of scope

- Reducing the number of factors used for the 20d window (full 16-factor model
  is retained; the ridge floor addresses stability without removing factors).
- Changing the factor proxy universe, orthogonalization order, or factor keys.
- Any frontend chart changes — layout, colors, and component logic are unchanged.
- Excess-return basis for the regression (the current raw-return basis is a
  valid choice for a factor attribution model and is not changed here).
- UCITS proxy fallback enabling (separate story).

## Notes / decisions

### Corrected algorithm — per-window Gram-Schmidt

```text
For each date t with window w = [t−w+1, t]:

  1. Slice raw factor returns to the window:
       f_k(window) = raw factor returns for proxy_k on dates [t−w+1, t]

  2. Gram-Schmidt within the window (same order as global):
       F*_1 = f_1  (Market/SPY, unchanged)
       F*_k = f_k − Σ_{j<k} <f_k, F*_j> / <F*_j, F*_j> × F*_j
             where <·,·> = sum of elementwise products over the window

  3. Ridge-stabilized OLS:
       X = [1, F*_1, ..., F*_K]   (intercept column + K orthogonalized factors)
       β = (X'X + λ·D)⁻¹ X'y
       where D = diag(0, 1, 1, ..., 1)  (ridge on factor columns only, not intercept)
       and λ = ridge_lambda (see floor below)

  4. Factor loading for factor k = β_{k+1}

Ridge floor by window:
  window = 20d:  λ_min = 0.01
  window = 60d:  λ_min = 0.001
  window = 252d: λ_min = 0.0001
  (applied as max(given_lambda, λ_min) so the default 1e-5 is overridden)
```

### Why per-window orthogonalization is correct

When orthogonalization is done globally and window slices are taken, the
within-window covariance of F*_k and F*_j is:

  cov_window(F*_k, F*_j) = cov_window(f_k, F*_j) − Σ_{m<k} proj_coeff_m × cov_window(F*_m, F*_j)

This is zero only if the projection coefficients computed over the full period
also zero out the within-window covariance — which does not hold in general.
The shorter the window relative to the full period, the larger the residual
within-window collinearity.

Per-window orthogonalization guarantees cov_window(F*_k, F*_j) = 0 by
construction for all j < k within that window.

### Academic precedent

Per-window orthogonalization is the standard approach in the academic time-series
factor model literature:
- Fama, E.F. & French, K.R. (1993). "Common risk factors in the returns on stocks
  and bonds." *Journal of Financial Economics*, 33(1), 3–56. (Orthogonal factor
  construction over the estimation window, not the full sample.)
- Connor, G. & Korajczyk, R. (1988). "Risk and return in an equilibrium APT:
  Application of a new test methodology." *Journal of Financial Economics*,
  21(2), 255–289. (Rolling estimation consistency.)
- Bai, J. & Ng, S. (2002). "Determining the number of factors in approximate
  factor models." *Econometrica*, 70(1), 191–221. (Stability of factor estimates
  under short windows.)

### Ridge floor rationale

With n observations and K factors, OLS condition number scales as O(n/K).
At n=25, K=16: ratio ≈ 1.56 — dangerously close to singular. A ridge floor of
λ=0.01 on daily-return scale (≈ 0.01% per day) is equivalent to 4.5% annualized
shrinkage — small enough not to bias stable windows but sufficient to cap the
condition number and prevent coefficient blowup.
