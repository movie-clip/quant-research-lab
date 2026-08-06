"""Factor return attribution engine.

Decomposes portfolio daily returns into per-factor contributions and an
unexplained (idiosyncratic) residual using the same rolling OLS + per-window
Gram-Schmidt orthogonalization pipeline as _build_rolling_factor_loadings in
risk.py.  This is Option (a) from the PRD: a new function that mirrors the
rolling loop without modifying the existing tested path.

Formula (see docs/finance/financial-methodology.md §Factor Return Attribution):

  contribution_k(t) = β̂_k(w, t) × f*_k(t)
  residual(t)        = r_p(t) − Σ_k contribution_k(t)

where f*_k(t) = orthogonalized_window[k][-1] — the last element of factor k's
Gram-Schmidt residual series within the rolling window ending at date t.

The reconciliation identity Σ_k contribution_k(t) + residual(t) = r_p(t) holds
by construction (arithmetic).  A floating-point sanity check is performed for
every attributed date; violation raises ValueError (caught by the route as 422).

Trust class: synthetic history.  Never label the residual "alpha".
"""
from __future__ import annotations

import math
from collections import defaultdict

from app.analytics.risk import (
    DEFAULT_FACTOR_DEFINITIONS,
    FACTOR_KEY_MAP,
    FACTOR_PROXY_MAP,
    ROLLING_RIDGE_FLOOR,
    ReturnBasis,
    _fit_factor_model,
    _orthogonalize_factors_window,
    _selected_history_return_series,
)
from app.schemas.attribution import (
    AttributionSeriesEntry,
    FactorAttributionResponse,
    FactorContributionPoint,
    FactorPeriodRow,
)
from app.schemas.reconciliation import DailyPortfolioState


ATTRIBUTION_METHODOLOGY_NOTE = (
    "Arithmetic (not compounded). "
    "Sum of daily factor contributions + unexplained equals arithmetic portfolio return."
)

# Floating-point tolerance for the per-date reconciliation sanity check.
_RECONCILIATION_TOLERANCE = 1e-9

_FACTOR_LABEL: dict[str, str] = {d.key: d.label for d in DEFAULT_FACTOR_DEFINITIONS}
_FACTOR_ORDER: dict[str, int] = {d.key: d.orthogonalization_order for d in DEFAULT_FACTOR_DEFINITIONS}


def _portfolio_return_series(
    daily_states: list[DailyPortfolioState],
    *,
    basis: ReturnBasis = "portfolio_value",
) -> dict[str, float]:
    """Daily portfolio return keyed by date, under a provenance-selected basis.

    Mirrors _portfolio_time_weighted_return_series from risk.py (same basis
    semantics — see its docstring) but returns a dict instead of a list of
    tuples, for easier intersection with factor dates. Defaults to the
    cash-flow-neutral TWR (`"portfolio_value"`); the attribution engine, which
    is always synthetic, passes `"market_value"`.
    """
    ordered = sorted(daily_states, key=lambda s: s.date)
    returns: dict[str, float] = {}
    prev: DailyPortfolioState | None = None
    for state in ordered:
        if prev is None:
            prev = state
            continue
        if basis == "market_value":
            if prev.total_market_value == 0.0:
                prev = state
                continue
            daily_return = (state.total_market_value / prev.total_market_value) - 1.0
        else:
            if prev.total_portfolio_value == 0.0:
                prev = state
                continue
            daily_return = (
                (state.total_portfolio_value - state.external_cash_flow) / prev.total_portfolio_value
            ) - 1.0
        # US-31.3 (Epic 31 F-3): a reconciliation-adjusted day is an accounting
        # correction, not performance — never attribute it to factors.
        if not state.return_is_publishable:
            prev = state
            continue
        returns[state.date] = daily_return
        prev = state
    return returns


def build_factor_attribution(
    daily_states: list[DailyPortfolioState],
    factor_histories: dict[str, list[dict]],
    window: int = 60,
    *,
    return_basis: ReturnBasis = "portfolio_value",
) -> FactorAttributionResponse:
    """Decompose portfolio daily returns into per-factor contributions.

    Args:
        daily_states:     Ordered daily portfolio valuations.
        factor_histories: Mapping proxy_symbol → list of price-history dicts
                          (same format as diagnostics engine input).
        window:           Rolling estimation window in trading days (20/60/252).
        return_basis:     Portfolio return basis (see _portfolio_return_series).
                          The attribution engine is always synthetic and passes
                          "market_value"; defaults to "portfolio_value" (TWR).

    Returns:
        FactorAttributionResponse with cumulative_series and period_attribution,
        or attribution_status="unavailable" when history is too short.

    Raises:
        ValueError: if the per-date reconciliation identity is violated beyond
                    _RECONCILIATION_TOLERANCE (should never happen in practice;
                    indicates a bug in the implementation).
    """
    portfolio_returns = _portfolio_return_series(daily_states, basis=return_basis)

    # Build daily factor return series keyed by proxy symbol.
    factor_returns: dict[str, dict[str, float]] = {
        symbol: _selected_history_return_series(rows)
        for symbol, rows in factor_histories.items()
    }

    # Active factors: only those whose proxy has price data.
    active_factors: list[tuple[str, str]] = [
        (label, proxy)
        for label, proxy in FACTOR_PROXY_MAP.items()
        if factor_returns.get(proxy)
    ]

    # Attribution only requires the rolling window to be filled once.
    # WINDOW_MIN_OBSERVATIONS adds a buffer for OLS stability in the risk path,
    # but attribution uses the same Gram-Schmidt + ridge pipeline and works fine
    # with exactly `window` observations.  Using the inflated value caused a
    # spurious "unavailable" for portfolios with slightly more than `window`
    # common dates (e.g. 21 days with the 20d selector).
    min_observations = window

    # Common dates: intersection of portfolio return dates and all active factor dates.
    if not active_factors or not portfolio_returns:
        return _unavailable_response(window)

    active_proxy_date_sets = [
        set(factor_returns[proxy])
        for _, proxy in active_factors
        if factor_returns.get(proxy)
    ]
    common_dates = sorted(
        set(portfolio_returns).intersection(*active_proxy_date_sets)
    )

    if len(common_dates) < min_observations:
        return _unavailable_response(window)

    y = [portfolio_returns[date] for date in common_dates]
    factor_series_dict: dict[str, list[float]] = {
        label: [factor_returns[proxy][date] for date in common_dates]
        for label, proxy in active_factors
    }
    raw_factor_data: list[tuple[str, str, list[float]]] = [
        (label, proxy, factor_series_dict[label])
        for label, proxy in active_factors
    ]

    ridge_floor = ROLLING_RIDGE_FLOOR.get(window, 1e-5)

    # Per-date attribution results.
    date_contributions: dict[str, dict[str, float]] = {}
    date_residuals: dict[str, float] = {}
    date_betas: dict[str, dict[str, float]] = {}
    date_factor_returns: dict[str, dict[str, float]] = {}

    for index, date in enumerate(common_dates):
        if index + 1 < min_observations:
            continue  # window not yet filled — exclude this date

        start = max(0, index - window + 1)
        y_window = y[start : index + 1]
        raw_window = [
            (label, proxy, values[start : index + 1])
            for label, proxy, values in raw_factor_data
        ]

        # Per-window Gram-Schmidt: mirrors _build_rolling_factor_loadings exactly.
        orthogonalized_window, dropped_factor_labels = _orthogonalize_factors_window(raw_window)
        if dropped_factor_labels:
            # A factor exactly collinear within this window has a null loading
            # (US-27.6) — per the methodology edge case ("any factor
            # contribution null on date t → exclude date t entirely"), skip
            # the date rather than attribute with a partial factor set.
            continue
        coefficients, _, _ = _fit_factor_model(
            y_window, orthogonalized_window, ridge_lambda=ridge_floor
        )

        r_p_t = y[index]
        contributions: dict[str, float] = {}
        betas: dict[str, float] = {}
        f_stars: dict[str, float] = {}

        for position, (label, _, orth_values) in enumerate(orthogonalized_window):
            factor_key = FACTOR_KEY_MAP.get(label)
            if factor_key is None:
                continue
            beta_k = coefficients[position + 1]
            # f*_k(t) = last element of the orthogonalized series within this window.
            f_star_k = orth_values[-1]
            contributions[factor_key] = beta_k * f_star_k
            betas[factor_key] = beta_k
            f_stars[factor_key] = f_star_k

        sum_contributions = sum(contributions.values())
        residual = r_p_t - sum_contributions

        # Fail-closed on degenerate windows: a singular / zero-variance rolling
        # window can make the OLS solve return a non-finite beta, producing NaN
        # contributions that (a) silently pass the reconciliation check below
        # (NaN comparisons are always False) and (b) break JSON serialization of
        # the response. Skip such dates entirely — never emit NaN.
        if not (
            math.isfinite(r_p_t)
            and math.isfinite(residual)
            and all(math.isfinite(v) for v in contributions.values())
            and all(math.isfinite(b) for b in betas.values())
            and all(math.isfinite(fs) for fs in f_stars.values())
        ):
            continue

        # Sanity check: reconciliation identity holds by construction.
        discrepancy = abs((sum_contributions + residual) - r_p_t)
        if discrepancy > _RECONCILIATION_TOLERANCE:
            raise ValueError(
                f"Attribution reconciliation failed on {date}: "
                f"|Σcontrib + residual − r_p| = {discrepancy:.2e} "
                f"(tolerance = {_RECONCILIATION_TOLERANCE:.2e})"
            )

        date_contributions[date] = contributions
        date_residuals[date] = residual
        date_betas[date] = betas
        date_factor_returns[date] = f_stars

    if not date_contributions:
        return _unavailable_response(window)

    attributed_dates = sorted(date_contributions)

    # ── Cumulative series ──────────────────────────────────────────────────────
    cumul_by_factor: dict[str, float] = defaultdict(float)
    cumul_unexplained = 0.0
    cumul_portfolio = 0.0
    cumulative_series: list[AttributionSeriesEntry] = []

    for date in attributed_dates:
        r_p_t = portfolio_returns[date]
        contributions = date_contributions[date]
        residual = date_residuals[date]

        for factor_key, contrib in contributions.items():
            cumul_by_factor[factor_key] += contrib
        cumul_unexplained += residual
        cumul_portfolio += r_p_t

        contribution_points = [
            FactorContributionPoint(
                factor_key=fk,
                cumul_contribution=round(cv, 8),
            )
            for fk, cv in sorted(
                cumul_by_factor.items(),
                key=lambda item: _FACTOR_ORDER.get(item[0], 999),
            )
        ]
        cumulative_series.append(
            AttributionSeriesEntry(
                date=date,
                contributions=contribution_points,
                cumul_unexplained=round(cumul_unexplained, 8),
                cumul_portfolio_return=round(cumul_portfolio, 8),
            )
        )

    # ── Period attribution table ───────────────────────────────────────────────
    factor_period_betas: dict[str, list[float]] = defaultdict(list)
    factor_period_contributions: dict[str, float] = defaultdict(float)
    factor_period_f_stars: dict[str, float] = defaultdict(float)

    for date in attributed_dates:
        for fk, beta in date_betas[date].items():
            factor_period_betas[fk].append(beta)
        for fk, contrib in date_contributions[date].items():
            factor_period_contributions[fk] += contrib
        for fk, f_star in date_factor_returns[date].items():
            factor_period_f_stars[fk] += f_star

    sorted_factor_keys = sorted(
        factor_period_contributions,
        key=lambda fk: _FACTOR_ORDER.get(fk, 999),
    )

    period_attribution: list[FactorPeriodRow] = []
    for fk in sorted_factor_keys:
        betas_list = factor_period_betas[fk]
        avg_beta = sum(betas_list) / len(betas_list) if betas_list else None
        period_attribution.append(
            FactorPeriodRow(
                factor_key=fk,
                factor_label=_FACTOR_LABEL.get(fk, fk),
                avg_beta=round(avg_beta, 4) if avg_beta is not None else None,
                factor_return_pct=round(factor_period_f_stars[fk] * 100, 4),
                contribution_pct=round(factor_period_contributions[fk] * 100, 4),
            )
        )

    return FactorAttributionResponse(
        attribution_status="available",
        window=window,
        cumulative_series=cumulative_series,
        period_attribution=period_attribution,
        total_portfolio_return_pct=round(cumul_portfolio * 100, 4),
        total_unexplained_pct=round(cumul_unexplained * 100, 4),
        methodology_note=ATTRIBUTION_METHODOLOGY_NOTE,
    )


def _unavailable_response(window: int) -> FactorAttributionResponse:
    return FactorAttributionResponse(
        attribution_status="unavailable",
        window=window,
        cumulative_series=[],
        period_attribution=[],
        total_portfolio_return_pct=None,
        total_unexplained_pct=None,
        methodology_note=ATTRIBUTION_METHODOLOGY_NOTE,
    )
