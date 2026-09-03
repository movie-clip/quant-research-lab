"""Statistical factor-model internals, extracted verbatim from analytics/risk.py (US-43.2).

This module holds the factor-definition vocabulary (UcitsCandidateMapping,
FactorDefinition, DEFAULT_FACTOR_DEFINITIONS and the proxy/key maps), the
per-window Gram-Schmidt orthogonalisation and ridge-OLS fit
(orthogonalize_factors_window, fit_factor_model), and their linear-algebra
primitives (_least_squares, _solve_linear_system, _dot).

Behaviour-neutral relocation (US-43.2): formulas, ridge floors and factor
definitions are unchanged from the pre-extraction risk.py code. See
docs/finance/financial-methodology.md §Statistical Factor Model and
§Per-window orthogonalization. This module is a leaf -- it imports nothing
from risk.py, so risk.py imports these names back.
"""
from __future__ import annotations

from dataclasses import dataclass



@dataclass(frozen=True)
class UcitsCandidateMapping:
    provider: str
    fund_name: str
    example_tickers: tuple[str, ...]
    asset_exposure: str
    domicile: str | None
    trading_currency: str | None
    base_currency: str | None
    currency_hedged: bool | None
    distribution_policy: str
    mapping_quality: str
    notes: str | None = None
    isin: str | None = None


@dataclass(frozen=True)
class FactorDefinition:
    key: str
    label: str
    category: str
    us_proxy: str
    target_exposure: str
    primary_mapping: UcitsCandidateMapping | None
    alternative_mappings: tuple[UcitsCandidateMapping, ...]
    ucits_examples: tuple[str, ...]
    mapping_quality: str
    default_enabled: bool
    orthogonalization_order: int
    description: str


DEFAULT_FACTOR_DEFINITIONS: tuple[FactorDefinition, ...] = (
    FactorDefinition("market", "Market", "market", "SPY", "US large-cap broad market / S&P 500", UcitsCandidateMapping("iShares", "iShares Core S&P 500 UCITS ETF", ("CSPX", "SXR8"), "S&P 500", "Ireland", "USD", "USD", False, "accumulating", "high", "Best institutional UCITS mapping for broad US market beta"), (UcitsCandidateMapping("Vanguard", "Vanguard S&P 500 UCITS ETF", ("VUAA",), "S&P 500", "Ireland", "USD", "USD", False, "accumulating", "high"),), ("CSPX", "SXR8", "VUAA"), "high", True, 1, "Broad US equity beta."),
    FactorDefinition("growth", "Growth", "style", "QQQ", "Nasdaq-100 / US mega-cap growth", UcitsCandidateMapping("Invesco", "Invesco EQQQ Nasdaq-100 UCITS ETF", ("EQQQ",), "Nasdaq-100", "Ireland", "USD", "USD", False, "distributing", "high"), (UcitsCandidateMapping("iShares", "iShares Nasdaq 100 UCITS ETF", ("CNDX",), "Nasdaq-100", "Ireland", "USD", "USD", False, "accumulating", "high"),), ("EQQQ", "CNDX"), "high", True, 2, "Mega-cap growth and tech tilt."),
    FactorDefinition("value", "Value", "style", "IWD", "US large-cap value", UcitsCandidateMapping("iShares", "iShares Edge MSCI USA Value Factor UCITS ETF", ("IWVL",), "US value factor", "Ireland", "USD", "USD", False, "unknown", "medium-high", "Good practical UCITS mapping; not a perfect Russell/CRSP-style value clone"), (), ("IWVL",), "medium-high", True, 3, "Value style exposure."),
    FactorDefinition("small_cap", "Small Cap", "style", "IWM", "US small caps", UcitsCandidateMapping("iShares", "iShares MSCI USA Small Cap UCITS ETF", ("IUSN",), "US small caps", "Ireland", "USD", "USD", False, "unknown", "medium", "Good practical mapping, but not a perfect Russell 2000 replication"), (), ("IUSN",), "medium", True, 4, "Size exposure outside large caps."),
    FactorDefinition("technology", "Technology", "sector", "XLK", "US technology sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Information Technology Sector UCITS ETF", (), "S&P 500 Information Technology", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 5, "Core technology sector exposure."),
    FactorDefinition("financials", "Financials", "sector", "XLF", "US financials sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Financials Sector UCITS ETF", ("IUFS",), "S&P 500 Financials", "Ireland", "USD", "USD", False, "unknown", "high"), (), ("IUFS",), "high", True, 6, "Rate-sensitive financial sector exposure."),
    FactorDefinition("health_care", "Health Care", "sector", "XLV", "US health care sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Health Care Sector UCITS ETF", ("IUHC",), "S&P 500 Health Care", "Ireland", "USD", "USD", False, "unknown", "high"), (), ("IUHC",), "high", True, 7, "Defensive health care exposure."),
    FactorDefinition("energy", "Energy", "sector", "XLE", "US energy sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Energy Sector UCITS ETF", (), "S&P 500 Energy", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 8, "Commodity-linked equity exposure."),
    FactorDefinition("industrials", "Industrials", "sector", "XLI", "US industrials sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Industrials Sector UCITS ETF", (), "S&P 500 Industrials", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 9, "Cyclical and capex-linked industrial exposure."),
    FactorDefinition("consumer_staples", "Consumer Staples", "sector", "XLP", "US consumer staples sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Consumer Staples Sector UCITS ETF", (), "S&P 500 Consumer Staples", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 10, "Defensive consumer staples exposure."),
    FactorDefinition("utilities", "Utilities", "sector", "XLU", "US utilities sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Utilities Sector UCITS ETF", (), "S&P 500 Utilities", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 11, "Rate-sensitive utilities exposure."),
    FactorDefinition("consumer_discretionary", "Consumer Discretionary", "sector", "XLY", "US consumer discretionary sector", UcitsCandidateMapping("iShares", "iShares S&P 500 Consumer Discretionary Sector UCITS ETF", (), "S&P 500 Consumer Discretionary", "Ireland", "USD", "USD", False, "unknown", "high", "Validate local exchange ticker from broker/data source"), (), (), "high", True, 12, "Cyclical consumer spending exposure."),
    FactorDefinition("rates_ief", "Intermediate Rates", "macro", "IEF", "US Treasuries 7-10 year", UcitsCandidateMapping("iShares", "iShares USD Treasury Bond 7-10yr UCITS ETF", (), "US Treasury 7-10yr", "Ireland", "USD", "USD", False, "unknown", "high", "Validate exact share class and exchange ticker"), (), (), "high", True, 13, "Intermediate Treasury duration exposure."),
    FactorDefinition("rates_tlt", "Long Rates", "macro", "TLT", "US Treasuries 20+ year", UcitsCandidateMapping("iShares", "iShares USD Treasury Bond 20+yr UCITS ETF", ("DTLA",), "US Treasury 20+yr", "Ireland", "USD", "USD", False, "unknown", "medium-high", "Good practical TLT mapping if DTLA is the unhedged 20+ year Treasury share class on the target exchange"), (), ("DTLA",), "medium-high", True, 14, "Long-duration Treasury exposure."),
    FactorDefinition("credit", "Credit", "macro", "LQD", "USD investment-grade corporate bonds", UcitsCandidateMapping("iShares", "iShares $ Corp Bond UCITS ETF", (), "USD investment-grade corporate bonds", "Ireland", "USD", "USD", False, "unknown", "medium-high", "Validate duration and share class against desired LQD-like exposure"), (UcitsCandidateMapping("iShares", "iShares Core $ Corp Bond UCITS ETF", (), "USD investment-grade corporate bonds", "Ireland", "USD", "USD", False, "unknown", "medium-high"),), (), "medium-high", True, 15, "Investment-grade credit spread exposure."),
    FactorDefinition("commodities", "Commodities", "macro", "DBC", "Broad commodities basket", UcitsCandidateMapping("WisdomTree / Invesco / broad commodity UCITS provider", "Broad Commodity UCITS ETF/ETC", (), "Broad commodities", "Ireland", "USD", "USD", None, "unknown", "medium", "This is the weakest mapping group; roll methodology and product structure vary materially"), (), (), "medium", True, 16, "Broad commodity and inflation exposure."),
)


FACTOR_PROXY_MAP: dict[str, str] = {item.label: item.us_proxy for item in DEFAULT_FACTOR_DEFINITIONS}
FACTOR_KEY_MAP: dict[str, str] = {item.label: item.key for item in DEFAULT_FACTOR_DEFINITIONS}


# Ridge regularization floor per window. Per-window Gram-Schmidt ensures factors are
# orthogonal within each rolling window, so X'X is well-conditioned and λ=1e-5 provides
# adequate numerical stability without material coefficient shrinkage. Larger λ values
# (like 0.01) would shrink daily-return-scale coefficients by >80% — unacceptable bias.
ROLLING_RIDGE_FLOOR: dict[int, float] = {20: 1e-5, 60: 1e-5, 252: 1e-5}


# A factor whose Gram-Schmidt residual never exceeds this within a window is
# treated as exactly collinear with the higher-priority factors (zero-variance
# residual up to float noise) and is DROPPED for that window per methodology
# §Per-window orthogonalization — "skip that factor's coefficient (null), do
# not propagate to later factors" (US-27.6). Near-collinear factors above this
# floor stay in the design matrix; the ridge floor handles them.
ORTHOGONALIZATION_ZERO_RESIDUAL_THRESHOLD = 1e-12


def orthogonalize_factors_window(
    raw_factors: list[tuple[str, str, list[float]]],
) -> tuple[list[tuple[str, str, list[float]]], list[str]]:
    """Gram-Schmidt orthogonalization over a single pre-sliced window.

    Unlike _orthogonalize_factor_series (which works from a full-series dict),
    this helper operates on already-windowed (factor, proxy, values) tuples.
    Calling this inside every rolling-window iteration guarantees that the
    resulting factors are mutually uncorrelated *within that window*, which is
    the correctness requirement for per-window ridge OLS.

    Returns (orthogonalized, dropped_factor_labels). A factor whose residual
    is ~zero (exactly collinear with earlier factors in this window) is
    EXCLUDED from the design matrix and reported in dropped_factor_labels —
    its coefficient is null for this window, and later factors are
    orthogonalized against the surviving set only (US-27.6; the previous
    behaviour kept the raw series, letting the ridge split the loading
    arbitrarily between the collinear pair).
    """
    orthogonalized: list[tuple[str, str, list[float]]] = []
    dropped_factor_labels: list[str] = []
    for factor, proxy, values in raw_factors:
        if not orthogonalized:
            orthogonalized.append((factor, proxy, values))
            continue
        design_matrix = [[1.0] + [prior_values[i] for _, _, prior_values in orthogonalized] for i in range(len(values))]
        # Exact projection (λ=0), matching the methodology's Gram-Schmidt step —
        # F*_k = f_k − Σ proj(f_k onto F*_j). Ridge belongs only to the final OLS
        # (§Per-window orthogonalization step 3); a ridged projection leaves an
        # exact duplicate with a ~λ/S residual, which silently defeated the
        # collinearity drop below (US-27.6). The earlier factors are already
        # mutually orthogonal, so the projection solve is well-conditioned;
        # _solve_linear_system skips genuinely zero pivots.
        proj_coefficients = _least_squares(design_matrix, values, ridge_lambda=0.0)
        fitted = [_dot(row, proj_coefficients) for row in design_matrix]
        residualized = [actual - expected for actual, expected in zip(values, fitted, strict=False)]
        if not any(abs(v) > ORTHOGONALIZATION_ZERO_RESIDUAL_THRESHOLD for v in residualized):
            dropped_factor_labels.append(factor)
            continue
        orthogonalized.append((factor, proxy, residualized))
    return orthogonalized, dropped_factor_labels


def fit_factor_model(y: list[float], orthogonalized_factors: list[tuple[str, str, list[float]]], ridge_lambda: float = 1e-5) -> tuple[list[float], list[float], float | None]:
    x = [[1.0] + [values[index] for _, _, values in orthogonalized_factors] for index in range(len(y))]
    coefficients = _least_squares(x, y, ridge_lambda=ridge_lambda)
    fitted = [_dot(row, coefficients) for row in x]
    residuals = [actual - expected for actual, expected in zip(y, fitted, strict=False)]
    mean_y = sum(y) / len(y)
    ss_total = sum((value - mean_y) ** 2 for value in y)
    ss_resid = sum(residual**2 for residual in residuals)
    r_squared = None if ss_total == 0 else max(0.0, 1 - (ss_resid / ss_total))
    return coefficients, residuals, r_squared


def _least_squares(x: list[list[float]], y: list[float], ridge_lambda: float = 0.0) -> list[float]:
    xt: list[list[float]] = [[float(x[row_index][column_index]) for row_index in range(len(x))] for column_index in range(len(x[0]))]
    xtx: list[list[float]] = [
        [float(sum(left * right for left, right in zip(row, col, strict=False))) for col in xt]
        for row in xt
    ]
    for index in range(1, len(xtx)):
        xtx[index][index] += ridge_lambda
    xty: list[float] = [float(sum(left * right for left, right in zip(row, y, strict=False))) for row in xt]
    return _solve_linear_system(xtx, xty)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]

    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            continue
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [value - (factor * pivot_value) for value, pivot_value in zip(augmented[row], augmented[col], strict=False)]

    return [augmented[row][-1] for row in range(size)]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(l * r for l, r in zip(left, right, strict=False))
