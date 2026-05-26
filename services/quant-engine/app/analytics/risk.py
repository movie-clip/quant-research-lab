from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Literal, Protocol

from app.instruments import InstrumentRegistry
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import (
    BenchmarkRelativePositioningCue,
    EtfOverlapConstituent,
    EtfOverlapPair,
    FactorCollinearityDiagnostics,
    FactorCollinearityWarning,
    FactorShiftDiagnosticsPayload,
    FactorShiftSnapshot,
    FactorProxyDefinition,
    FactorRiskContribution,
    FactorRiskContributionItem,
    FactorExposurePoint,
    LookThroughConstituent,
    LookThroughSectorExposure,
    LookThroughSource,
    MarketOverlapConstituent,
    MarketOverlapSummary,
    PositionRiskContributionItem,
    PortfolioRiskContribution,
    PortfolioRiskSummary,
    RelativeRiskSummary,
    MappingMatchComponents,
    MappingMatchSummary,
    ModelReliabilitySnapshot,
    RiskConcentrationSnapshot,
    RiskContributionBreakdownPayload,
    RankedFactorShiftItem,
    RegimeAssessment,
    RollingFactorLoadingPoint,
    RollingRiskPoint,
    RollingVolatilityPoint,
    SnapshotItem,
    InsufficientHistoryPoint,
    StatisticalFactorModel,
    StressScenarioResult,
    VolatilityRegimePayload,
    VolatilityAssumptions,
    VolatilitySnapshot,
    WindowSummary,
)
from app.services.market_data import detect_histories_return_basis, detect_history_return_basis


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
class SelectedHistoryPriceSeries:
    points: list[tuple[str, float]]
    return_basis_status: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"]
    selected_field: Literal["adjusted_close", "price", "unavailable"]


def is_history_series_verified_adjusted(rows: list[dict]) -> bool:
    return select_history_price_series(rows).return_basis_status == "verified_adjusted_close"


def selected_history_price_map(rows: list[dict]) -> tuple[dict[str, float], Literal["verified_adjusted_close", "unverified_close_only", "unavailable"]]:
    series = select_history_price_series(rows)
    return dict(series.points), series.return_basis_status


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
FACTOR_BY_LABEL: dict[str, FactorDefinition] = {item.label: item for item in DEFAULT_FACTOR_DEFINITIONS}

ROLLING_WINDOWS: tuple[int, ...] = (20, 60, 252)
COLLINEARITY_WARNING_THRESHOLD = 0.85
WINDOW_MIN_OBSERVATIONS: dict[int, int] = {20: 25, 60: 75, 252: 275}
# Ridge regularization floor per window. Per-window Gram-Schmidt ensures factors are
# orthogonal within each rolling window, so X'X is well-conditioned and λ=1e-5 provides
# adequate numerical stability without material coefficient shrinkage. Larger λ values
# (like 0.01) would shrink daily-return-scale coefficients by >80% — unacceptable bias.
ROLLING_RIDGE_FLOOR: dict[int, float] = {20: 1e-5, 60: 1e-5, 252: 1e-5}
SHIFT_FLAG_20D_THRESHOLD = 0.25
SHIFT_FLAG_60D_THRESHOLD = 0.35
STABILITY_GAP_THRESHOLD = 0.30
VOLATILITY_RATIO_FLAG_THRESHOLD = 1.2
RISK_CONTRIBUTION_WINDOW_DAYS = 60
VOLATILITY_ANNUALIZATION_DAYS = 252
VOLATILITY_DOWNSIDE_MAR = 0.0

STRESS_SCENARIOS: tuple[tuple[str, dict[str, float], str], ...] = (
    ("Broad Market Selloff", {"Market": -0.10, "Growth": -0.12, "Value": -0.08, "Small Cap": -0.11, "Financials": -0.09, "Health Care": -0.05, "Energy": -0.08, "Industrials": -0.09, "Intermediate Rates": 0.01, "Long Rates": 0.02, "Credit": -0.02, "Commodities": -0.02}, "Risk-off equity drawdown led by broad market and cyclicals."),
    ("Rates Down Risk-On", {"Market": 0.03, "Growth": 0.05, "Value": 0.01, "Small Cap": 0.02, "Financials": -0.01, "Health Care": 0.01, "Energy": 0.0, "Industrials": 0.02, "Intermediate Rates": 0.03, "Long Rates": 0.05, "Credit": 0.02, "Commodities": 0.01}, "Falling yields supporting duration and growth assets."),
    ("Inflation Reacceleration", {"Market": -0.02, "Growth": -0.05, "Value": 0.02, "Small Cap": -0.01, "Financials": 0.01, "Health Care": 0.0, "Energy": 0.06, "Industrials": 0.02, "Intermediate Rates": -0.03, "Long Rates": -0.06, "Credit": -0.02, "Commodities": 0.07}, "Sticky inflation with commodity strength and duration pressure."),
)


class HoldingsMarketData(Protocol):
    def get_etf_holdings(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> tuple[str | None, list[dict]]: ...
    def get_company_profile(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> dict | None: ...


def _compact_ucits_mappings(mappings: tuple | list) -> list:
    compact: list = []
    for mapping in mappings:
        mapped = _to_ucits_mapping(mapping)
        if mapped is not None:
            compact.append(mapped)
    return compact


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _asset_class_for_definition(definition: FactorDefinition) -> str:
    if definition.key in {"rates_ief", "rates_tlt", "credit"}:
        return "bond"
    if definition.key in {"commodities", "gold"}:
        return "commodity"
    return "equity"


def _compute_mapping_match_summary(definition: FactorDefinition, mapping: UcitsCandidateMapping | None) -> MappingMatchSummary | None:
    if mapping is None:
        return None

    exposure_match = _compute_exposure_match(definition, mapping)
    structure_fit = _compute_structure_fit(definition, mapping)
    implementation_fit = _compute_implementation_fit(definition, mapping)
    components = MappingMatchComponents(
        exposure_match=round(exposure_match, 4) if exposure_match is not None else None,
        historical_similarity=None,
        structure_fit=round(structure_fit, 4) if structure_fit is not None else None,
        implementation_fit=round(implementation_fit, 4) if implementation_fit is not None else None,
    )

    available = [value for value in [exposure_match, structure_fit, implementation_fit] if value is not None]
    if not available:
        return MappingMatchSummary(
            score_pct=None,
            label=None,
            score_basis="metadata_only",
            score_status="insufficient_data",
            hard_cap_reason=None,
            components=components,
        )

    raw_score_pct = 100 * ((0.60 * (exposure_match or 0.0)) + (0.25 * (structure_fit or 0.0)) + (0.15 * (implementation_fit or 0.0)))
    capped_score_pct, hard_cap_reason = _apply_mapping_hard_caps(definition, mapping, raw_score_pct)
    status = "degraded" if _metadata_mode_is_degraded(mapping) else "ok"
    score_pct = round(max(0.0, min(100.0, capped_score_pct)), 1)

    return MappingMatchSummary(
        score_pct=score_pct,
        label=_mapping_match_label(score_pct),
        score_basis="metadata_only",
        score_status=status,
        hard_cap_reason=hard_cap_reason,
        components=components,
    )


def _compute_mapping_match_summary_for_definition(mapping: UcitsCandidateMapping, definition: FactorDefinition | None) -> MappingMatchSummary | None:
    if definition is None:
        return None
    return _compute_mapping_match_summary(definition, mapping)


def _compute_exposure_match(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float | None:
    asset_class = _asset_class_for_definition(definition)
    if asset_class == "bond":
        return _compute_exposure_match_bond(definition, mapping)
    if asset_class == "commodity":
        return _compute_exposure_match_commodity(definition, mapping)
    return _compute_exposure_match_equity(definition, mapping)


def _compute_exposure_match_equity(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    index_match = _index_match_score(definition, mapping)
    holdings_overlap = None
    style_sector_similarity = _style_sector_similarity_score(definition, mapping)

    if holdings_overlap is None:
        return _clamp((0.65 * index_match) + (0.35 * style_sector_similarity))
    return _clamp((0.45 * index_match) + (0.30 * holdings_overlap) + (0.25 * style_sector_similarity))


def _compute_exposure_match_bond(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    duration_match = _duration_match_score(definition, mapping)
    maturity_bucket_match = _maturity_bucket_match_score(definition, mapping)
    credit_quality_match = _credit_quality_match_score(definition, mapping)
    issuer_curve_match = _issuer_curve_match_score(definition, mapping)
    return _clamp((0.40 * duration_match) + (0.25 * maturity_bucket_match) + (0.20 * credit_quality_match) + (0.15 * issuer_curve_match))


def _compute_exposure_match_commodity(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    basket_match = _commodity_basket_match_score(definition, mapping)
    roll_method_match = _commodity_roll_method_score(definition, mapping)
    collateral_structure_match = _commodity_collateral_structure_score(definition, mapping)
    return _clamp((0.50 * basket_match) + (0.30 * roll_method_match) + (0.20 * collateral_structure_match))


def _compute_structure_fit(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    hedge_status_fit = _hedge_status_fit_score(definition, mapping)
    distribution_fit = _distribution_fit_score(definition, mapping)
    ucits_fit = _ucits_fit_score(mapping)
    currency_share_class_fit = _currency_share_class_fit_score(mapping)
    return _clamp((0.35 * hedge_status_fit) + (0.25 * distribution_fit) + (0.20 * ucits_fit) + (0.20 * currency_share_class_fit))


def _compute_implementation_fit(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    liquidity_fit = _liquidity_fit_score(definition, mapping)
    history_fit = _history_fit_score(definition, mapping)
    cost_fit = _cost_fit_score(definition, mapping)
    availability_fit = _availability_fit_score(definition, mapping)
    return _clamp((0.40 * liquidity_fit) + (0.30 * history_fit) + (0.20 * cost_fit) + (0.10 * availability_fit))


def _apply_mapping_hard_caps(definition: FactorDefinition, mapping: UcitsCandidateMapping, raw_score_pct: float) -> tuple[float, str | None]:
    asset_class = _asset_class_for_definition(definition)
    exposure = (mapping.asset_exposure or "").lower()
    target = definition.target_exposure.lower()
    cap: float | None = None
    reason: str | None = None

    if asset_class == "equity":
        if not _contains_any(exposure, _equity_exposure_tokens(definition)):
            cap, reason = 50.0, "region_or_market_mismatch"
    elif asset_class == "bond":
        if definition.key == "credit" and "corporate" not in exposure:
            cap, reason = 45.0, "bond_credit_sleeve_mismatch"
        elif definition.key == "rates_tlt" and not _contains_any(exposure, ("20+", "20yr", "20+yr")):
            cap, reason = 60.0, "bond_duration_bucket_mismatch"
        elif definition.key == "rates_ief" and not _contains_any(exposure, ("7-10", "7-10yr", "7-10 year")):
            cap, reason = 60.0, "bond_duration_bucket_mismatch"
    elif asset_class == "commodity":
        if definition.key == "commodities" and "commodit" not in exposure:
            cap, reason = 25.0, "asset_class_mismatch"

    if definition.key in {"rates_ief", "rates_tlt"} and mapping.currency_hedged is True:
        cap, reason = 70.0, "hedge_status_mismatch"

    return (min(raw_score_pct, cap), reason) if cap is not None else (raw_score_pct, None)


def _mapping_match_label(score_pct: float | None) -> str | None:
    if score_pct is None:
        return None
    if score_pct >= 90:
        return "Exact / Best Match"
    if score_pct >= 80:
        return "Strong Match"
    if score_pct >= 65:
        return "Usable Proxy"
    if score_pct >= 50:
        return "Loose Proxy"
    return "Poor Match"


def _metadata_mode_is_degraded(mapping: UcitsCandidateMapping) -> bool:
    if mapping.distribution_policy == "distributing":
        return True
    return not bool(mapping.example_tickers)


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    return any(token in value for token in tokens)


def _equity_exposure_tokens(definition: FactorDefinition) -> tuple[str, ...]:
    token_map = {
        "market": ("s&p 500", "usa", "us", "large-cap"),
        "growth": ("nasdaq-100", "nasdaq 100", "mega-cap growth"),
        "value": ("value", "usa"),
        "small_cap": ("small cap", "small-cap"),
        "technology": ("technology", "information technology", "tech"),
        "financials": ("financial",),
        "health_care": ("health care",),
        "energy": ("energy",),
        "industrials": ("industrial",),
        "consumer_staples": ("consumer staples",),
        "utilities": ("utilities", "utility"),
        "consumer_discretionary": ("consumer discretionary", "consumer cyclical"),
    }
    return token_map.get(definition.key, ())


def _index_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    tokens = _equity_exposure_tokens(definition)
    if tokens and _contains_any(exposure, tokens):
        if definition.key == "market" and "s&p 500" in exposure:
            return 1.0
        if definition.key == "growth" and ("nasdaq-100" in exposure or "nasdaq 100" in exposure):
            return 1.0
        return 0.85
    if definition.key in {"value", "small_cap"} and "usa" in exposure:
        return 0.60
    return 0.30


def _style_sector_similarity_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key in {"technology", "financials", "health_care", "energy", "industrials", "consumer_staples", "utilities", "consumer_discretionary"}:
        return 1.0 if _contains_any(exposure, _equity_exposure_tokens(definition)) else 0.30
    if definition.key == "growth":
        return 1.0 if "nasdaq" in exposure else 0.60
    if definition.key == "value":
        return 0.90 if "value" in exposure else 0.60
    if definition.key == "small_cap":
        return 0.90 if "small" in exposure else 0.40
    return 0.85


def _duration_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key == "rates_ief":
        return 1.0 if _contains_any(exposure, ("7-10", "7-10yr", "7-10 year")) else 0.25
    if definition.key == "rates_tlt":
        return 1.0 if _contains_any(exposure, ("20+", "20yr", "20+yr", "20+ year")) else 0.25
    if definition.key == "credit":
        return 0.85 if "corporate" in exposure else 0.30
    return 0.50


def _maturity_bucket_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key == "rates_ief":
        return 1.0 if "7-10" in exposure else 0.25
    if definition.key == "rates_tlt":
        return 1.0 if "20+" in exposure else 0.25
    return 0.65


def _credit_quality_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key == "credit":
        return 1.0 if _contains_any(exposure, ("investment-grade", "investment grade", "corp bond", "corporate")) else 0.0
    return 1.0 if "treasury" in exposure else 0.0


def _issuer_curve_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key in {"rates_ief", "rates_tlt"}:
        return 1.0 if "treasury" in exposure else 0.0
    if definition.key == "credit":
        return 1.0 if "corporate" in exposure else 0.5
    return 0.5


def _commodity_basket_match_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    exposure = (mapping.asset_exposure or "").lower()
    if definition.key == "commodities":
        return 1.0 if "commodit" in exposure else 0.0
    return 0.60


def _commodity_roll_method_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    notes = (mapping.notes or "").lower()
    if definition.key == "commodities":
        return 0.50 if notes else 0.0
    return 0.50


def _commodity_collateral_structure_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    return 0.50 if mapping.provider else 0.0


def _hedge_status_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    if mapping.currency_hedged is None:
        return 0.70
    if definition.key in {"rates_ief", "rates_tlt"}:
        return 1.0 if mapping.currency_hedged is False else 0.40
    return 1.0 if mapping.currency_hedged is False else 0.40


def _distribution_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    preferred = "unknown"
    if definition.key in {"market", "value", "small_cap"}:
        preferred = "accumulating"
    elif definition.key == "growth":
        preferred = "accumulating"

    if mapping.distribution_policy == "unknown" or preferred == "unknown":
        return 0.75
    return 1.0 if mapping.distribution_policy == preferred else 0.60


def _ucits_fit_score(mapping: UcitsCandidateMapping) -> float:
    domicile = (mapping.domicile or "").lower()
    return 1.0 if domicile in {"ireland", "luxembourg"} else 0.0


def _currency_share_class_fit_score(mapping: UcitsCandidateMapping) -> float:
    if mapping.trading_currency == "USD":
        return 1.0
    if mapping.trading_currency:
        return 0.70
    return 0.40


def _liquidity_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    return 0.80 if mapping.example_tickers else 0.50


def _history_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    if mapping.example_tickers:
        return 0.75
    return 0.40


def _cost_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    quality_cost_map = {
        "high": 0.90,
        "medium-high": 0.78,
        "medium": 0.62,
        "low": 0.40,
    }
    return quality_cost_map.get(mapping.mapping_quality, 0.50)


def _availability_fit_score(definition: FactorDefinition, mapping: UcitsCandidateMapping) -> float:
    return 1.0 if mapping.example_tickers else 0.50


def build_portfolio_risk_summary(daily_states: list, benchmark_rows: list[dict], benchmark_symbol: str) -> PortfolioRiskSummary:
    paired_returns = _paired_portfolio_and_benchmark_returns(daily_states, benchmark_rows)
    portfolio_samples = [item[1] for item in paired_returns]
    benchmark_samples = [item[2] for item in paired_returns]
    beta = _calculate_beta(portfolio_samples, benchmark_samples)
    correlation = _calculate_correlation(portfolio_samples, benchmark_samples)

    return PortfolioRiskSummary(
        benchmark_symbol=benchmark_symbol,
        methodology="Historical regression using cash-flow-neutral daily portfolio returns and aligned benchmark daily returns.",
        start_date=paired_returns[0][0] if paired_returns else None,
        end_date=paired_returns[-1][0] if paired_returns else None,
        observations=len(paired_returns),
        portfolio_beta=round(beta, 4) if beta is not None else None,
        portfolio_correlation=round(correlation, 4) if correlation is not None else None,
        r_squared=round(correlation**2, 4) if correlation is not None else None,
        portfolio_volatility_pct=round(_calculate_annualized_volatility(portfolio_samples) * 100, 2) if portfolio_samples else None,
        benchmark_volatility_pct=round(_calculate_annualized_volatility(benchmark_samples) * 100, 2) if benchmark_samples else None,
    )


def build_rolling_risk_series(daily_states: list, benchmark_rows: list[dict]) -> list[RollingRiskPoint]:
    paired_returns = _paired_portfolio_and_benchmark_returns(daily_states, benchmark_rows)
    points: list[RollingRiskPoint] = []

    for index, (date, _, _) in enumerate(paired_returns):
        point_values: dict[str, float | None] = {}
        for window in ROLLING_WINDOWS:
            samples = paired_returns[max(0, index - window + 1) : index + 1]
            portfolio_window = [item[1] for item in samples]
            benchmark_window = [item[2] for item in samples]
            beta = _calculate_beta(portfolio_window, benchmark_window) if len(samples) >= window else None
            correlation = _calculate_correlation(portfolio_window, benchmark_window) if len(samples) >= window else None
            point_values[f"beta_{window}d"] = round(beta, 4) if beta is not None else None
            point_values[f"correlation_{window}d"] = round(correlation, 4) if correlation is not None else None
        points.append(
            RollingRiskPoint(
                date=date,
                **point_values,
            )
        )

    return points


def build_position_risk_contributions(snapshot: ImportedPortfolioSnapshot, price_histories: dict[str, list[dict]], benchmark_rows: list[dict]) -> list[PortfolioRiskContribution]:
    total_market_value = sum(position.market_value for position in snapshot.positions)
    benchmark_returns = _selected_history_return_series(benchmark_rows)

    contributions: list[PortfolioRiskContribution] = []
    for position in snapshot.positions:
        price_rows = price_histories.get(position.symbol, [])
        symbol_returns = _selected_history_return_series(price_rows)
        paired = [(symbol_returns[date], benchmark_returns[date]) for date in sorted(set(symbol_returns) & set(benchmark_returns))]
        symbol_samples = [item[0] for item in paired]
        benchmark_samples = [item[1] for item in paired]
        beta = _calculate_beta(symbol_samples, benchmark_samples)
        correlation = _calculate_correlation(symbol_samples, benchmark_samples)
        weight = (position.market_value / total_market_value) if total_market_value else 0.0
        contributions.append(
            PortfolioRiskContribution(
                symbol=position.symbol,
                market_value=round(position.market_value, 2),
                portfolio_weight=round(weight, 4),
                beta=round(beta, 4) if beta is not None else None,
                correlation=round(correlation, 4) if correlation is not None else None,
                contribution_to_portfolio_beta=round(weight * beta, 4) if beta is not None else None,
            )
        )

    return sorted(
        contributions,
        key=lambda item: abs(item.contribution_to_portfolio_beta) if item.contribution_to_portfolio_beta is not None else -1.0,
        reverse=True,
    )


def build_lookthrough_exposure(snapshot: ImportedPortfolioSnapshot, market_data: HoldingsMarketData, symbol_overrides: dict[str, list[str]] | None = None) -> tuple[list[LookThroughConstituent], dict[str, str], list[str], float]:
    """
    Build constituent-level exposure from current positions.

    Coverage methodology:
    - covered_market_value counts market value that is economically resolved to a
      constituent-level exposure.
    - direct single-name positions count as covered at 100% of their market value.
    - ETF positions count as covered only when ETF holdings are successfully resolved.
    - unresolved ETF positions may still appear as direct placeholders in the
      constituent list for usability, but they do not count toward covered_market_value.

    This makes coverage_ratio represent constituent-resolution coverage rather than
    generic current-holdings representability.
    """
    registry = InstrumentRegistry()
    metadata = registry.attach_snapshot_metadata(snapshot)
    total_market_value = sum(position.market_value for position in snapshot.positions)
    constituent_values: defaultdict[str, float] = defaultdict(float)
    constituent_names: dict[str, str] = {}
    constituent_sources: defaultdict[str, list[LookThroughSource]] = defaultdict(list)
    etf_resolution: dict[str, str] = {}
    uncovered_positions: list[str] = []
    covered_market_value = 0.0

    for position in sorted(snapshot.positions, key=lambda item: item.market_value, reverse=True):
        instrument = metadata.get(position.symbol)
        if instrument and instrument.asset_class == "etf":
            resolved_symbol, holdings = market_data.get_etf_holdings(position.symbol, symbol_overrides)
            if holdings:
                etf_resolution[position.symbol] = resolved_symbol or position.symbol
                covered_market_value += position.market_value
                for row in holdings:
                    holding_symbol = str(row.get("asset") or "").strip().upper()
                    holding_name = str(row.get("name") or holding_symbol).strip()
                    holding_weight_pct = float(row.get("weightPercentage") or 0.0)
                    if not holding_symbol or holding_weight_pct <= 0:
                        continue
                    effective_market_value = position.market_value * (holding_weight_pct / 100.0)
                    constituent_values[holding_symbol] += effective_market_value
                    constituent_names.setdefault(holding_symbol, holding_name)
                    constituent_sources[holding_symbol].append(
                        LookThroughSource(
                            source_symbol=position.symbol,
                            source_market_value=round(position.market_value, 2),
                            source_weight=round(holding_weight_pct / 100.0, 6),
                            resolved_via=resolved_symbol or position.symbol,
                        )
                    )
                continue

            uncovered_positions.append(position.symbol)
            constituent_values[position.symbol] += position.market_value
            constituent_names.setdefault(position.symbol, instrument.name if instrument and instrument.name else position.symbol)
            constituent_sources[position.symbol].append(
                LookThroughSource(
                    source_symbol=position.symbol,
                    source_market_value=round(position.market_value, 2),
                    source_weight=1.0,
                    resolved_via=position.symbol,
                )
            )
            continue

        constituent_values[position.symbol] += position.market_value
        constituent_names.setdefault(position.symbol, instrument.name if instrument and instrument.name else position.symbol)
        constituent_sources[position.symbol].append(
            LookThroughSource(
                source_symbol=position.symbol,
                source_market_value=round(position.market_value, 2),
                source_weight=1.0,
                resolved_via=position.symbol,
            )
        )
        covered_market_value += position.market_value

    constituents = [
        LookThroughConstituent(
            symbol=symbol,
            name=constituent_names.get(symbol, symbol),
            effective_market_value=round(market_value, 2),
            portfolio_weight=round(market_value / total_market_value, 4) if total_market_value else 0.0,
            sources=sorted(constituent_sources[symbol], key=lambda item: item.source_market_value, reverse=True),
        )
        for symbol, market_value in sorted(constituent_values.items(), key=lambda item: item[1], reverse=True)
    ]
    return constituents, etf_resolution, uncovered_positions, covered_market_value


def build_market_overlap_summary(
    lookthrough_constituents: list[LookThroughConstituent],
    benchmark_symbol: str,
    benchmark_holdings: list[dict],
) -> MarketOverlapSummary:
    """
    Build benchmark-overlap metrics from look-through portfolio weights.

    Overlap methodology when benchmark holdings are available:
    - overlap_weight = sum(min(portfolio_weight_i, benchmark_weight_i)) for shared symbols
    - active_share = 0.5 * sum(abs(portfolio_weight_i - benchmark_weight_i)) over the union of symbols
    - portfolio_in_benchmark_weight = sum(portfolio_weight_i) for shared symbols
    - benchmark_covered_weight = sum(benchmark_weight_i) for benchmark constituents loaded into the comparison set

    Availability rule:
    - if benchmark holdings are unavailable or empty, these overlap fields return None
      instead of zero-like placeholders, because a true zero-overlap conclusion would be misleading
    """
    portfolio_weights = {item.symbol: item.portfolio_weight for item in lookthrough_constituents}
    portfolio_names = {item.symbol: item.name for item in lookthrough_constituents}

    if not portfolio_weights:
        return MarketOverlapSummary(
            benchmark_symbol=benchmark_symbol,
            overlap_weight=None,
            active_share=None,
            portfolio_in_benchmark_weight=None,
            benchmark_covered_weight=None,
            top_overweights=[],
            top_underweights=[],
        )

    benchmark_weights: dict[str, float] = {}
    benchmark_names: dict[str, str] = {}
    for row in benchmark_holdings:
        symbol = str(row.get("asset") or "").strip().upper()
        weight = float(row.get("weightPercentage") or 0.0) / 100.0
        if not symbol or weight <= 0:
            continue
        benchmark_weights[symbol] = weight
        benchmark_names[symbol] = str(row.get("name") or symbol).strip()

    if not benchmark_weights:
        return MarketOverlapSummary(
            benchmark_symbol=benchmark_symbol,
            overlap_weight=None,
            active_share=None,
            portfolio_in_benchmark_weight=None,
            benchmark_covered_weight=None,
            top_overweights=[],
            top_underweights=[],
        )

    shared_symbols = sorted(set(portfolio_weights) & set(benchmark_weights))
    top_shared = [
        MarketOverlapConstituent(
            symbol=symbol,
            name=portfolio_names.get(symbol, benchmark_names.get(symbol, symbol)),
            portfolio_weight=round(portfolio_weights[symbol], 4),
            benchmark_weight=round(benchmark_weights[symbol], 4),
            overlap_weight=round(min(portfolio_weights[symbol], benchmark_weights[symbol]), 4),
        )
        for symbol in sorted(shared_symbols, key=lambda item: min(portfolio_weights[item], benchmark_weights[item]), reverse=True)
    ]

    overlap_weight = sum(min(portfolio_weights[symbol], benchmark_weights[symbol]) for symbol in shared_symbols)
    all_symbols = sorted(set(portfolio_weights) | set(benchmark_weights))
    active_share = 0.5 * sum(abs(portfolio_weights.get(symbol, 0.0) - benchmark_weights.get(symbol, 0.0)) for symbol in all_symbols)
    portfolio_in_benchmark_weight = sum(portfolio_weights.get(symbol, 0.0) for symbol in shared_symbols)
    benchmark_covered_weight = sum(benchmark_weights.values())
    top_overweights, top_underweights = _build_benchmark_positioning_cues(
        lookthrough_constituents=lookthrough_constituents,
        benchmark_weights=benchmark_weights,
        benchmark_names=benchmark_names,
    )

    return MarketOverlapSummary(
        benchmark_symbol=benchmark_symbol,
        overlap_weight=round(overlap_weight, 4),
        active_share=round(active_share, 4),
        portfolio_in_benchmark_weight=round(portfolio_in_benchmark_weight, 4),
        benchmark_covered_weight=round(benchmark_covered_weight, 4),
        top_overweights=top_overweights,
        top_underweights=top_underweights,
    )


def _build_benchmark_positioning_cues(
    lookthrough_constituents: list[LookThroughConstituent],
    benchmark_weights: dict[str, float],
    benchmark_names: dict[str, str],
) -> tuple[list[BenchmarkRelativePositioningCue], list[BenchmarkRelativePositioningCue]]:
    cues: list[BenchmarkRelativePositioningCue] = []
    portfolio_weights = {item.symbol: item.portfolio_weight for item in lookthrough_constituents}
    portfolio_names = {item.symbol: item.name for item in lookthrough_constituents}

    for symbol, benchmark_weight in benchmark_weights.items():
        portfolio_weight = portfolio_weights.get(symbol)
        if portfolio_weight is None:
            continue

        active_weight = portfolio_weight - benchmark_weight
        if active_weight == 0:
            continue

        cues.append(
            BenchmarkRelativePositioningCue(
                symbol=symbol,
                name=portfolio_names.get(symbol, benchmark_names.get(symbol, symbol)),
                portfolio_weight=round(portfolio_weight, 4),
                benchmark_weight=round(benchmark_weight, 4),
                active_weight=round(active_weight, 4),
            )
        )

    overweights = sorted(
        (item for item in cues if item.active_weight > 0),
        key=lambda item: (-item.active_weight, -item.portfolio_weight, -item.benchmark_weight, item.symbol),
    )
    underweights = sorted(
        (item for item in cues if item.active_weight < 0),
        key=lambda item: (item.active_weight, -item.benchmark_weight, -item.portfolio_weight, item.symbol),
    )
    top_overweights = overweights[:5]
    top_underweights = underweights[:5]
    return top_overweights, top_underweights


def build_relative_risk_summary(daily_states: list, benchmark_rows: list[dict], benchmark_symbol: str) -> RelativeRiskSummary:
    paired_returns = _paired_portfolio_and_benchmark_returns(daily_states, benchmark_rows)
    if not paired_returns:
        return RelativeRiskSummary(benchmark_symbol=benchmark_symbol, tracking_error_pct=None, active_return_pct=None, information_ratio=None)

    active_returns = [portfolio - benchmark for _, portfolio, benchmark in paired_returns]
    tracking_error = _calculate_annualized_volatility(active_returns) if len(active_returns) >= 2 else None
    mean_active = (sum(active_returns) / len(active_returns)) if active_returns else None
    information_ratio = None
    if tracking_error is not None and tracking_error != 0 and mean_active is not None:
        tracking_error_value = tracking_error
        information_ratio = (mean_active * sqrt(252)) / tracking_error_value

    compounded_portfolio = 1.0
    compounded_benchmark = 1.0
    for _, portfolio_return, benchmark_return in paired_returns:
        compounded_portfolio *= 1 + portfolio_return
        compounded_benchmark *= 1 + benchmark_return

    return RelativeRiskSummary(
        benchmark_symbol=benchmark_symbol,
        tracking_error_pct=round(tracking_error * 100, 2) if tracking_error is not None else None,
        active_return_pct=round(((compounded_portfolio - compounded_benchmark) * 100), 2),
        information_ratio=round(information_ratio, 2) if information_ratio is not None else None,
    )


def _degrade_status_for_unverified_return_basis(status: str, return_basis_status: str) -> str:
    if return_basis_status != "verified_adjusted_close" and status in {"ok", "partial"}:
        return "degraded_unverified_return_basis"
    return status


def select_history_price_series(rows: list[dict]) -> SelectedHistoryPriceSeries:
    if not rows:
        return SelectedHistoryPriceSeries(points=[], return_basis_status="unavailable", selected_field="unavailable")

    dated_rows = [row for row in rows if row.get("date") is not None]
    adjusted_points = [
        (str(row["date"]), float(row["adjClose"] if row.get("adjClose") is not None else row["adjusted_close"]))
        for row in dated_rows
        if row.get("adjClose") is not None or row.get("adjusted_close") is not None
    ]
    if adjusted_points and len(adjusted_points) == len(dated_rows):
        return SelectedHistoryPriceSeries(
            points=adjusted_points,
            return_basis_status="verified_adjusted_close",
            selected_field="adjusted_close",
        )

    price_points = [
        (str(row["date"]), float(row["price"]))
        for row in dated_rows
        if row.get("price") is not None
    ]
    if price_points:
        return SelectedHistoryPriceSeries(
            points=price_points,
            return_basis_status="unverified_close_only",
            selected_field="price",
        )

    return SelectedHistoryPriceSeries(points=[], return_basis_status="unavailable", selected_field="unavailable")


def _selected_history_return_series(rows: list[dict]) -> dict[str, float]:
    series = select_history_price_series(rows)
    return _series_to_returns(series.points)


def build_volatility_regime_payload(daily_states: list, benchmark_rows: list[dict]) -> VolatilityRegimePayload:
    rolling_series = _build_rolling_volatility_series(daily_states, benchmark_rows)
    snapshot = _build_volatility_snapshot(rolling_series)
    regime = _classify_volatility_regime(snapshot)
    return VolatilityRegimePayload(
        methodology="Rolling volatility metrics computed from cash-flow-neutral daily portfolio returns and aligned benchmark returns; drawdown is computed from a compounded return index.",
        assumptions=VolatilityAssumptions(
            return_basis="time_weighted_daily_return",
            cash_flow_timing="external_cash_flow_applied_before_end_of_day_measurement",
            drawdown_basis="compounded_return_index",
            benchmark_basis="aligned_daily_price_return",
            downside_mar=VOLATILITY_DOWNSIDE_MAR,
            annualization_days=VOLATILITY_ANNUALIZATION_DAYS,
        ),
        rolling_series=rolling_series,
        snapshot=snapshot,
        regime=regime,
    )


def build_factor_shift_diagnostics(
    factor_registry: list[FactorProxyDefinition],
    model: StatisticalFactorModel,
    volatility_regime: VolatilityRegimePayload,
) -> FactorShiftDiagnosticsPayload:
    collinearity_by_window = {item.window_days: item for item in model.collinearity_diagnostics}
    snapshots = [
        _build_factor_shift_snapshot(definition, model, collinearity_by_window, volatility_regime)
        for definition in factor_registry
    ]
    return FactorShiftDiagnosticsPayload(
        methodology="Deterministic factor-shift diagnostics derived from rolling factor loadings across 20d, 60d, and 252d windows.",
        snapshots=snapshots,
        largest_positive_shifts_20d=_rank_factor_shifts(snapshots, mode="positive_20d"),
        largest_negative_shifts_20d=_rank_factor_shifts(snapshots, mode="negative_20d"),
        largest_absolute_shifts_20d=_rank_factor_shifts(snapshots, mode="absolute_20d"),
        largest_absolute_shifts_60d=_rank_factor_shifts(snapshots, mode="absolute_60d"),
    )


def build_risk_contribution_breakdown(
    snapshot: ImportedPortfolioSnapshot,
    daily_states: list,
    price_histories: dict[str, list[dict]],
    factor_histories: dict[str, list[dict]],
    factor_registry: list[FactorProxyDefinition],
    model: StatisticalFactorModel,
) -> RiskContributionBreakdownPayload:
    factor_return_basis_status = detect_histories_return_basis(factor_histories)
    factor_contributions, factor_total_variance, factor_observation_count = _build_factor_risk_contributions(factor_registry, factor_histories, model)
    position_contributions, _, position_observation_count = _build_position_risk_contributions(snapshot, price_histories)
    reliability = build_model_reliability_snapshot(model)
    specific_variance = round((reliability.residual_volatility / 100) ** 2, 8) if reliability.residual_volatility is not None else None
    total_variance_raw = (factor_total_variance if factor_total_variance > 0 else 0.0) + (specific_variance if specific_variance is not None else 0.0)
    total_variance = round(total_variance_raw, 8) if total_variance_raw > 0 else None
    factor_risk_share_total = round((factor_total_variance / total_variance_raw), 4) if factor_total_variance > 0 and total_variance_raw > 0 else None
    specific_risk_share = round((specific_variance / total_variance_raw), 4) if specific_variance is not None and total_variance_raw > 0 else None
    if total_variance_raw > 0:
        factor_contributions = [
            item.model_copy(
                update={
                    "risk_share": round((item.variance_contribution / total_variance_raw), 4)
                    if item.variance_contribution is not None
                    else None
                }
            )
            for item in factor_contributions
        ]
    concentration = RiskConcentrationSnapshot(
        top_1_factor_risk_share=_sum_top_risk_shares([item.risk_share for item in factor_contributions], 1),
        top_3_factor_risk_share=_sum_top_risk_shares([item.risk_share for item in factor_contributions], 3),
        top_1_position_risk_share=_sum_top_risk_shares([item.risk_share for item in position_contributions], 1),
        top_5_position_risk_share=_sum_top_risk_shares([item.risk_share for item in position_contributions], 5),
        factor_hhi=_herfindahl_index([item.risk_share for item in factor_contributions]),
        position_hhi=_herfindahl_index([item.risk_share for item in position_contributions]),
    )
    return RiskContributionBreakdownPayload(
        methodology="Estimated factor and position risk contributions using latest valid 60-day loadings, aligned return covariance, and residual variance.",
        window_days=RISK_CONTRIBUTION_WINDOW_DAYS,
        observation_count=min(count for count in [factor_observation_count, position_observation_count] if count > 0) if any(count > 0 for count in [factor_observation_count, position_observation_count]) else 0,
        status=_degrade_status_for_unverified_return_basis(reliability.status, factor_return_basis_status),
        factor_contributions=factor_contributions,
        factor_total_variance=round(factor_total_variance, 8) if factor_total_variance > 0 else None,
        specific_variance=specific_variance,
        total_variance=total_variance,
        factor_risk_share_total=factor_risk_share_total,
        specific_risk_share=specific_risk_share,
        residual_volatility=reliability.residual_volatility,
        position_contributions=position_contributions,
        concentration=concentration,
    )


def build_model_reliability_snapshot(model: StatisticalFactorModel) -> ModelReliabilitySnapshot:
    window_summary = next((item for item in model.windows if item.window_days == RISK_CONTRIBUTION_WINDOW_DAYS), None)
    latest_point = next(
        (
            point
            for point in reversed(model.rolling_loadings_60d)
            if point.r_squared is not None or point.residual_vol is not None or any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)
        ),
        None,
    )
    current_window_collinearity = next((item for item in model.collinearity_diagnostics if item.window_days == RISK_CONTRIBUTION_WINDOW_DAYS), None)
    collinearity_pairs = current_window_collinearity.high_collinearity_pairs if current_window_collinearity else []
    max_abs_factor_correlation = max((abs(item.correlation) for item in collinearity_pairs), default=None)
    factor_count_used = sum(1 for definition in DEFAULT_FACTOR_DEFINITIONS if latest_point is not None and getattr(latest_point, definition.key) is not None)
    missing_factor_count = len(DEFAULT_FACTOR_DEFINITIONS) - factor_count_used
    stability_score = _calculate_stability_score(model)
    status = window_summary.status if window_summary else model.status
    confidence = _model_reliability_confidence(status, latest_point.r_squared if latest_point else None, len(collinearity_pairs), missing_factor_count)

    return ModelReliabilitySnapshot(
        window_days=RISK_CONTRIBUTION_WINDOW_DAYS,
        observation_count=window_summary.observations if window_summary else 0,
        r_squared=round(latest_point.r_squared, 4) if latest_point and latest_point.r_squared is not None else None,
        residual_volatility=round(latest_point.residual_vol, 2) if latest_point and latest_point.residual_vol is not None else None,
        collinearity_pair_count=len(collinearity_pairs),
        max_abs_factor_correlation=round(max_abs_factor_correlation, 4) if max_abs_factor_correlation is not None else None,
        factor_count_used=factor_count_used,
        missing_factor_count=missing_factor_count,
        status=status,
        confidence=confidence,
        stability_score=stability_score,
    )


def apply_return_basis_status_to_model_reliability(
    reliability: ModelReliabilitySnapshot,
    *,
    benchmark_rows: list[dict],
    factor_histories: dict[str, list[dict]],
) -> ModelReliabilitySnapshot:
    benchmark_return_basis_status = detect_history_return_basis(benchmark_rows)
    factor_return_basis_status = detect_histories_return_basis(factor_histories)
    if benchmark_return_basis_status == "verified_adjusted_close" and factor_return_basis_status == "verified_adjusted_close":
        return reliability
    degraded_status = _degrade_status_for_unverified_return_basis(reliability.status, "unverified_close_only")
    return reliability.model_copy(update={"status": degraded_status, "confidence": "low"})


def apply_return_basis_status_to_factor_model(
    model: StatisticalFactorModel,
    *,
    benchmark_rows: list[dict],
    factor_histories: dict[str, list[dict]],
) -> StatisticalFactorModel:
    benchmark_return_basis_status = detect_history_return_basis(benchmark_rows)
    factor_return_basis_status = detect_histories_return_basis(factor_histories)
    if benchmark_return_basis_status == "verified_adjusted_close" and factor_return_basis_status == "verified_adjusted_close":
        return model
    degraded_status = _degrade_status_for_unverified_return_basis(model.status, "unverified_close_only")
    degraded_windows = [
        item.model_copy(update={"status": _degrade_status_for_unverified_return_basis(item.status, "unverified_close_only")})
        for item in model.windows
    ]
    return model.model_copy(update={"status": degraded_status, "windows": degraded_windows})


def build_lookthrough_sector_exposure(lookthrough_constituents: list[LookThroughConstituent]) -> list[LookThroughSectorExposure]:
    registry = InstrumentRegistry()
    total_market_value = sum(item.effective_market_value for item in lookthrough_constituents)
    sector_totals: defaultdict[str, float] = defaultdict(float)

    for constituent in lookthrough_constituents:
        instrument = registry.get_instrument(constituent.symbol)
        default_sector = instrument.sector if instrument and instrument.sector else _infer_sector_from_sources(constituent.sources) or "Other"
        sourced_value_total = 0.0

        for source in constituent.sources:
            source_instrument = registry.get_instrument(source.source_symbol)
            source_value = source.source_market_value * source.source_weight
            source_sector: str = default_sector
            if source_instrument and source_instrument.asset_class == "etf" and source_instrument.category in {
                "Thematic UCITS ETF",
                "Thematic ETF",
                "Sector UCITS ETF",
                "Sector ETF",
                "Bond UCITS ETF",
                "Bond ETF",
                "Commodity UCITS ETF",
                "Commodity ETF",
            } and source_instrument.sector:
                source_sector = source_instrument.sector

            sector_totals[source_sector] += source_value
            sourced_value_total += source_value

        remainder = constituent.effective_market_value - sourced_value_total
        if abs(remainder) > 0.01:
            sector_totals[default_sector] += remainder

    # Suppress sectors below 0.05% weight — these round to "0.0%" in the UI
    # and typically represent futures residuals (Equity Index) or tiny ETF tail
    # constituents that would appear as phantom zero-weight entries.
    MIN_SECTOR_WEIGHT = 0.0005
    return [
        LookThroughSectorExposure(
            sector=sector,
            market_value=round(market_value, 2),
            weight=round(market_value / total_market_value, 4) if total_market_value else 0.0,
        )
        for sector, market_value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
        if total_market_value and market_value / total_market_value >= MIN_SECTOR_WEIGHT
    ]


def build_factor_exposures(
    risk_summary: PortfolioRiskSummary,
    market_overlap: MarketOverlapSummary,
    lookthrough_sector_exposure: list[LookThroughSectorExposure],
) -> list[FactorExposurePoint]:
    sector_weights = {item.sector: item.weight for item in lookthrough_sector_exposure}
    growth_tilt = sector_weights.get("Technology", 0.0) + sector_weights.get("Communication Services", 0.0) + sector_weights.get("Consumer Discretionary", 0.0)

    return [
        FactorExposurePoint(factor="Market", exposure=round(risk_summary.portfolio_beta, 4) if risk_summary.portfolio_beta is not None else None, description="Historical broad-market beta versus SPY.", basis="historical_benchmark_relative"),
        FactorExposurePoint(factor="SPY Overlap", exposure=round(market_overlap.portfolio_in_benchmark_weight, 4) if market_overlap.portfolio_in_benchmark_weight is not None else None, description="Look-through share of the portfolio that overlaps SPY constituents when benchmark holdings are available.", basis="benchmark_holdings_required"),
        FactorExposurePoint(factor="Growth Tilt", exposure=round(growth_tilt, 4), description="Technology, communication services, and consumer discretionary sleeve weight.", basis="current_state"),
        FactorExposurePoint(factor="Technology Tilt", exposure=round(sector_weights.get("Technology", 0.0), 4), description="Look-through allocation to technology equity and technology ETF exposure.", basis="current_state"),
        FactorExposurePoint(factor="Consumer Discretionary Tilt", exposure=round(sector_weights.get("Consumer Discretionary", 0.0), 4), description="Look-through allocation to consumer discretionary equity and retail-cyclical exposure.", basis="current_state"),
        FactorExposurePoint(factor="Consumer Staples Tilt", exposure=round(sector_weights.get("Consumer Staples", 0.0), 4), description="Look-through allocation to defensive consumer staples exposure.", basis="current_state"),
        FactorExposurePoint(factor="Health Care Tilt", exposure=round(sector_weights.get("Health Care", 0.0), 4), description="Look-through allocation to health care and biotechnology exposure.", basis="current_state"),
        FactorExposurePoint(factor="Utilities Tilt", exposure=round(sector_weights.get("Utilities", 0.0), 4), description="Look-through allocation to utilities and regulated-infrastructure exposure.", basis="current_state"),
        FactorExposurePoint(factor="Defense Tilt", exposure=round(sector_weights.get("Defense", 0.0), 4), description="Look-through allocation to defense and aerospace exposure.", basis="current_state"),
        FactorExposurePoint(factor="Commodities Hedge", exposure=round(sector_weights.get("Commodities", 0.0), 4), description="Look-through allocation to commodity-linked holdings.", basis="current_state"),
        FactorExposurePoint(factor="Fixed Income Ballast", exposure=round(sector_weights.get("Fixed Income", 0.0), 4), description="Look-through allocation to treasury and short-duration bond sleeves.", basis="current_state"),
    ]


def _mapping_quality_score(mapping_quality: str) -> float | None:
    if mapping_quality == "high":
        return 0.95
    if mapping_quality == "medium-high":
        return 0.82
    if mapping_quality == "medium":
        return 0.68
    if mapping_quality == "low":
        return 0.50
    return None


def _build_factor_registry_payload() -> list[FactorProxyDefinition]:
    return [
        FactorProxyDefinition(
            key=item.key,
            label=item.label,
            category=item.category,
            us_proxy=item.us_proxy,
            target_exposure=item.target_exposure,
            primary_mapping=_to_ucits_mapping(item.primary_mapping),
            alternative_mappings=_compact_ucits_mappings(item.alternative_mappings),
            ucits_examples=list(item.ucits_examples),
            mapping_quality=item.mapping_quality,
            default_enabled=item.default_enabled,
            orthogonalization_order=item.orthogonalization_order,
            description=item.description,
        )
        for item in DEFAULT_FACTOR_DEFINITIONS
    ]


def _build_window_summaries(
    common_dates: list[str],
    rolling_loadings_20d: list[RollingFactorLoadingPoint],
    rolling_loadings_60d: list[RollingFactorLoadingPoint],
    rolling_loadings_252d: list[RollingFactorLoadingPoint],
) -> list[WindowSummary]:
    series_by_window = {
        20: rolling_loadings_20d,
        60: rolling_loadings_60d,
        252: rolling_loadings_252d,
    }
    summaries: list[WindowSummary] = []
    for window in ROLLING_WINDOWS:
        series = series_by_window[window]
        valid_points = [point for point in series if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)]
        summaries.append(
            WindowSummary(
                window_days=window,
                observations=len(common_dates),
                start_date=common_dates[0] if common_dates else None,
                end_date=common_dates[-1] if common_dates else None,
                status="ok" if len(common_dates) >= WINDOW_MIN_OBSERVATIONS[window] else ("partial" if valid_points else "insufficient_history"),
            )
        )
    return summaries


def _build_insufficient_history(common_dates: list[str], active_factors: list[tuple[str, str]]) -> list[InsufficientHistoryPoint]:
    available_observations = len(common_dates)
    missing_factors = [definition.key for definition in DEFAULT_FACTOR_DEFINITIONS if definition.label not in {factor for factor, _ in active_factors}]
    points: list[InsufficientHistoryPoint] = []
    for window in ROLLING_WINDOWS:
        required = WINDOW_MIN_OBSERVATIONS[window]
        if available_observations < required or missing_factors:
            points.append(
                InsufficientHistoryPoint(
                    window_days=window,
                    required_observations=required,
                    available_observations=available_observations,
                    missing_factors=missing_factors,
                )
            )
    return points


def _build_collinearity_diagnostics(common_dates: list[str], factor_series: dict[str, list[float]]) -> list[FactorCollinearityDiagnostics]:
    diagnostics: list[FactorCollinearityDiagnostics] = []
    for window in ROLLING_WINDOWS:
        pairs = _build_factor_collinearity_warnings(common_dates, factor_series, window)
        diagnostics.append(
            FactorCollinearityDiagnostics(
                window_days=window,
                threshold=COLLINEARITY_WARNING_THRESHOLD,
                high_collinearity_pairs=pairs,
                note="Some factors are highly overlapping in the selected window, so smaller residual loadings may be unstable." if pairs else "No high-collinearity pairs detected.",
            )
        )
    return diagnostics


def _build_rolling_volatility_series(daily_states: list, benchmark_rows: list[dict]) -> list[RollingVolatilityPoint]:
    portfolio_returns = _portfolio_time_weighted_return_series(daily_states)
    if not portfolio_returns:
        return []

    benchmark_returns = _benchmark_return_series(benchmark_rows)
    aligned_returns = _aligned_active_return_series(portfolio_returns, benchmark_returns)
    aligned_by_date = {item[0]: (item[1], item[2], item[3]) for item in aligned_returns}
    wealth_index_map = _build_wealth_index(portfolio_returns)
    drawdown_map = _build_drawdown_from_return_index(wealth_index_map)
    points: list[RollingVolatilityPoint] = []
    for index, (date, portfolio_return) in enumerate(portfolio_returns):
        benchmark_return = benchmark_returns.get(date)
        active_return = aligned_by_date.get(date, (None, None, None))[2]
        values: dict[str, float | None] = {
            "portfolio_return": round(portfolio_return, 6),
            "benchmark_return": round(benchmark_return, 6) if benchmark_return is not None else None,
            "active_return": round(active_return, 6) if active_return is not None else None,
            "drawdown_pct": drawdown_map.get(date),
            "wealth_index": wealth_index_map.get(date),
        }
        for window in ROLLING_WINDOWS:
            samples = portfolio_returns[max(0, index - window + 1) : index + 1]
            portfolio_window = [item[1] for item in samples]
            aligned_window = [aligned_by_date[sample_date] for sample_date, _ in samples if sample_date in aligned_by_date]
            benchmark_window = [item[1] for item in aligned_window]
            active_window = [item[2] for item in aligned_window]
            if len(samples) >= window:
                values[f"realized_vol_{window}d"] = round(_calculate_annualized_volatility(portfolio_window) * 100, 2)
                values[f"downside_vol_{window}d"] = round(_calculate_downside_deviation(portfolio_window) * 100, 2)
                values[f"benchmark_vol_{window}d"] = round(_calculate_annualized_volatility(benchmark_window) * 100, 2) if len(benchmark_window) >= window else None
                values[f"tracking_error_{window}d"] = round(_calculate_annualized_volatility(active_window) * 100, 2) if len(active_window) >= window else None
            else:
                values[f"realized_vol_{window}d"] = None
                values[f"downside_vol_{window}d"] = None
                values[f"benchmark_vol_{window}d"] = None
                values[f"tracking_error_{window}d"] = None
        points.append(RollingVolatilityPoint(date=date, **values))
    return points


def _calculate_downside_deviation(values: list[float], mar: float = VOLATILITY_DOWNSIDE_MAR) -> float:
    if len(values) < 2:
        return 0.0
    downside = [min(value - mar, 0.0) for value in values]
    return _sample_standard_deviation(downside) * sqrt(VOLATILITY_ANNUALIZATION_DAYS)


def _build_wealth_index(portfolio_returns: list[tuple[str, float]]) -> dict[str, float]:
    wealth = 100.0
    wealth_by_date: dict[str, float] = {}
    for date, daily_return in portfolio_returns:
        wealth *= 1 + daily_return
        wealth_by_date[date] = round(wealth, 4)
    return wealth_by_date


def _build_drawdown_from_return_index(wealth_index: dict[str, float]) -> dict[str, float]:
    drawdown_by_date: dict[str, float] = {}
    peak = 0.0
    for date in sorted(wealth_index):
        value = wealth_index[date]
        peak = max(peak, value)
        drawdown_by_date[date] = round(((value / peak) - 1) * 100, 2) if peak > 0 else 0.0
    return drawdown_by_date


def _calculate_percentile_rank(series: list[float], value: float | None) -> float | None:
    if value is None or not series:
        return None
    less_than = sum(1 for item in series if item < value)
    equal_to = sum(1 for item in series if item == value)
    return (less_than + (0.5 * equal_to)) / len(series)


def _build_volatility_snapshot(rolling_series: list[RollingVolatilityPoint]) -> VolatilitySnapshot:
    if not rolling_series:
        return VolatilitySnapshot()
    latest = rolling_series[-1]
    realized_20 = latest.realized_vol_20d
    realized_60 = latest.realized_vol_60d
    realized_252 = latest.realized_vol_252d
    drawdowns = [point.drawdown_pct for point in rolling_series if point.drawdown_pct is not None]
    realized_20_history = [point.realized_vol_20d for point in rolling_series if point.realized_vol_20d is not None]
    vol_ratio_20_60 = None
    if realized_20 is not None and realized_60 is not None and realized_60 != 0:
        vol_ratio_20_60 = round(realized_20 / realized_60, 2)
    vol_ratio_20_252 = None
    if realized_20 is not None and realized_252 is not None and realized_252 != 0:
        vol_ratio_20_252 = round(realized_20 / realized_252, 2)
    return VolatilitySnapshot(
        realized_vol_20d=realized_20,
        realized_vol_60d=realized_60,
        realized_vol_252d=realized_252,
        downside_vol_20d=latest.downside_vol_20d,
        downside_vol_60d=latest.downside_vol_60d,
        downside_vol_252d=latest.downside_vol_252d,
        benchmark_vol_20d=latest.benchmark_vol_20d,
        benchmark_vol_60d=latest.benchmark_vol_60d,
        benchmark_vol_252d=latest.benchmark_vol_252d,
        tracking_error_20d=latest.tracking_error_20d,
        tracking_error_60d=latest.tracking_error_60d,
        tracking_error_252d=latest.tracking_error_252d,
        current_drawdown_pct=latest.drawdown_pct,
        max_drawdown_pct=min(drawdowns) if drawdowns else None,
        vol_ratio_20_60=vol_ratio_20_60,
        vol_ratio_20_252=vol_ratio_20_252,
        current_20d_vol_percentile=round(_calculate_percentile_rank([float(item) for item in realized_20_history], realized_20) or 0.0, 4) if realized_20 is not None else None,
    )


def _classify_volatility_regime(snapshot: VolatilitySnapshot) -> RegimeAssessment:
    percentile = snapshot.current_20d_vol_percentile
    if percentile is None:
        return RegimeAssessment(label="normal", confidence="low")
    if percentile < 0.30:
        label = "calm"
    elif percentile <= 0.80:
        label = "normal"
    else:
        label = "stressed"
    confidence = "high" if snapshot.realized_vol_20d is not None and snapshot.realized_vol_60d is not None else "medium" if snapshot.realized_vol_20d is not None else "low"
    return RegimeAssessment(label=label, confidence=confidence)


def _build_factor_collinearity_warnings(
    dates: list[str],
    factor_series: dict[str, list[float]],
    window: int,
) -> list[FactorCollinearityWarning]:
    warnings: list[FactorCollinearityWarning] = []
    labels = [item.label for item in DEFAULT_FACTOR_DEFINITIONS if item.label in factor_series]
    if len(dates) < 2:
        return warnings

    for index, left_label in enumerate(labels):
        left_values = factor_series[left_label]
        for right_label in labels[index + 1 :]:
            right_values = factor_series[right_label]
            latest_window_left = left_values[-window:] if len(left_values) >= window else left_values
            latest_window_right = right_values[-window:] if len(right_values) >= window else right_values
            latest_correlation = _calculate_correlation(latest_window_left, latest_window_right)
            if latest_correlation is None or abs(latest_correlation) < COLLINEARITY_WARNING_THRESHOLD:
                continue

            left_factor = FACTOR_BY_LABEL[left_label]
            right_factor = FACTOR_BY_LABEL[right_label]
            warnings.append(
                FactorCollinearityWarning(
                    left_key=left_factor.key,
                    right_key=right_factor.key,
                    left_proxy=left_factor.us_proxy,
                    right_proxy=right_factor.us_proxy,
                    correlation=round(latest_correlation, 4),
                )
            )

    return sorted(warnings, key=lambda item: abs(item.correlation), reverse=True)


def _max_abs_rolling_correlation(left: list[float], right: list[float], window: int) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    if len(left) < window:
        correlation = _calculate_correlation(left, right)
        return abs(correlation) if correlation is not None else 0.0

    max_correlation = 0.0
    for end_index in range(window, len(left) + 1):
        correlation = _calculate_correlation(left[end_index - window : end_index], right[end_index - window : end_index])
        if correlation is not None:
            max_correlation = max(max_correlation, abs(correlation))
    return max_correlation


def build_statistical_factor_model(daily_states: list, factor_histories: dict[str, list[dict]], benchmark_symbol: str) -> StatisticalFactorModel:
    portfolio_returns = dict((date, value) for date, value in [(item[0], item[1]) for item in _paired_portfolio_and_benchmark_returns(daily_states, factor_histories.get(benchmark_symbol, []))])
    factor_returns = {
        factor: _selected_history_return_series(rows)
        for factor, rows in factor_histories.items()
    }
    common_dates = sorted(set(portfolio_returns).intersection(*[set(values) for values in factor_returns.values() if values]))
    active_factors = [(factor, proxy) for factor, proxy in FACTOR_PROXY_MAP.items() if factor_returns.get(proxy)]

    if len(common_dates) < 10 or not active_factors:
        empty_snapshot: list[SnapshotItem] = []
        return StatisticalFactorModel(
            status="insufficient_history",
            benchmark_symbol=benchmark_symbol,
            windows=_build_window_summaries(common_dates, [], [], []),
            rolling_loadings_20d=[],
            rolling_loadings_60d=[],
            rolling_loadings_252d=[],
            current_factor_snapshot=empty_snapshot,
            collinearity_diagnostics=[
                FactorCollinearityDiagnostics(window_days=60, threshold=COLLINEARITY_WARNING_THRESHOLD, high_collinearity_pairs=[], note="Not enough shared history for collinearity diagnostics."),
            ],
            insufficient_history=_build_insufficient_history(common_dates, active_factors),
        )

    y = [portfolio_returns[date] for date in common_dates]
    factor_series = {factor: [factor_returns[proxy][date] for date in common_dates] for factor, proxy in active_factors}
    # Global orthogonalization is used only for the full-period model (alpha, specific risk,
    # current snapshot). Rolling windows re-orthogonalize per-window so that factors are
    # uncorrelated within each estimation window (see docs/finance/financial-methodology.md).
    orthogonalized_factors = _orthogonalize_factor_series(active_factors, factor_series)
    coefficients, residuals, r_squared = _fit_factor_model(y, orthogonalized_factors)
    alpha_annualized = coefficients[0] * 252 * 100
    specific_risk = _calculate_annualized_volatility(residuals) * 100 if len(residuals) >= 2 else None
    collinearity_warnings = _build_factor_collinearity_warnings(common_dates, factor_series, window=60)
    # Pass raw (non-orthogonalized) factor series to the rolling functions — orthogonalization
    # is performed inside _build_rolling_factor_loadings on each window slice.
    raw_factor_data = [(factor, proxy, factor_series[factor]) for factor, proxy in active_factors]
    rolling_loadings = _build_rolling_factor_loadings(common_dates, y, raw_factor_data, window=20)
    rolling_loadings_60d = _build_rolling_factor_loadings(common_dates, y, raw_factor_data, window=60)
    rolling_loadings_252d = _build_rolling_factor_loadings(common_dates, y, raw_factor_data, window=252)
    current_factor_snapshot = _build_current_factor_snapshot(rolling_loadings, rolling_loadings_60d, rolling_loadings_252d)
    collinearity_diagnostics = _build_collinearity_diagnostics(common_dates, factor_series)
    insufficient_history = _build_insufficient_history(common_dates, active_factors)

    return StatisticalFactorModel(
        status="partial" if insufficient_history else "ok",
        benchmark_symbol=benchmark_symbol,
        windows=_build_window_summaries(common_dates, rolling_loadings, rolling_loadings_60d, rolling_loadings_252d),
        rolling_loadings_20d=rolling_loadings,
        rolling_loadings_60d=rolling_loadings_60d,
        rolling_loadings_252d=rolling_loadings_252d,
        current_factor_snapshot=current_factor_snapshot,
        collinearity_diagnostics=collinearity_diagnostics,
        insufficient_history=insufficient_history,
    )


def build_factor_registry() -> list[FactorProxyDefinition]:
    return _build_factor_registry_payload()


def factor_model_methodology() -> str:
    return "Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples."
def build_stress_scenarios(model: StatisticalFactorModel) -> list[StressScenarioResult]:
    latest_snapshot = {item.label: item.latest_loading for item in model.current_factor_snapshot}
    scenarios: list[StressScenarioResult] = []
    for name, shocks, description in STRESS_SCENARIOS:
        estimated = sum((latest_snapshot.get(factor) or 0.0) * shock for factor, shock in shocks.items()) * 100
        scenarios.append(StressScenarioResult(name=name, estimated_return_pct=round(estimated, 2), description=description))
    return scenarios


def build_etf_overlap_pairs(snapshot: ImportedPortfolioSnapshot, market_data: HoldingsMarketData, symbol_overrides: dict[str, list[str]] | None = None) -> list[EtfOverlapPair]:
    registry = InstrumentRegistry()
    metadata = registry.attach_snapshot_metadata(snapshot)
    etf_positions = [position for position in snapshot.positions if metadata.get(position.symbol) and metadata[position.symbol].asset_class == "etf"]
    holdings_cache: dict[str, tuple[str, dict[str, tuple[str, float]]]] = {}
    sector_cache: dict[str, str] = {}

    def load_holdings(symbol: str) -> tuple[str, dict[str, tuple[str, float]]]:
        cached = holdings_cache.get(symbol)
        if cached is not None:
            return cached
        resolved_symbol, rows = market_data.get_etf_holdings(symbol, symbol_overrides)
        holdings = {
            str(row.get("asset") or "").strip().upper(): (str(row.get("name") or row.get("asset") or "").strip(), float(row.get("weightPercentage") or 0.0) / 100.0)
            for row in rows
            if str(row.get("asset") or "").strip() and float(row.get("weightPercentage") or 0.0) > 0
        }
        payload = (resolved_symbol or symbol, holdings)
        holdings_cache[symbol] = payload
        return payload

    pairs: list[EtfOverlapPair] = []
    for index, left in enumerate(etf_positions):
        left_resolved, left_holdings = load_holdings(left.symbol)
        if not left_holdings:
            continue
        for right in etf_positions[index + 1 :]:
            right_resolved, right_holdings = load_holdings(right.symbol)
            if not right_holdings:
                continue
            shared = sorted(set(left_holdings) & set(right_holdings))
            top_shared = [
                EtfOverlapConstituent(
                    symbol=symbol,
                    name=left_holdings[symbol][0] or right_holdings[symbol][0] or symbol,
                    left_weight=round(left_holdings[symbol][1], 4),
                    right_weight=round(right_holdings[symbol][1], 4),
                    overlap_weight=round(min(left_holdings[symbol][1], right_holdings[symbol][1]), 4),
                )
                for symbol in sorted(shared, key=lambda item: min(left_holdings[item][1], right_holdings[item][1]), reverse=True)
            ]
            pairs.append(
                EtfOverlapPair(
                    left_symbol=left.symbol,
                    right_symbol=right.symbol,
                    left_resolved=left_resolved,
                    right_resolved=right_resolved,
                    overlap_weight=round(sum(min(left_holdings[symbol][1], right_holdings[symbol][1]) for symbol in shared), 4),
                    shared_constituent_count=len(shared),
                    top_shared_constituents=top_shared[:15],
                    sector_overlap=_build_shared_sector_overlap(shared, left_holdings, right_holdings, left_resolved, right_resolved, market_data, sector_cache),
                )
            )

    return sorted(pairs, key=lambda item: item.overlap_weight, reverse=True)


def _paired_portfolio_and_benchmark_returns(daily_states: list, benchmark_rows: list[dict]) -> list[tuple[str, float, float]]:
    portfolio_returns = _portfolio_time_weighted_return_series(daily_states)
    benchmark_returns = _benchmark_return_series(benchmark_rows)
    return [(date, portfolio_return, benchmark_returns[date]) for date, portfolio_return in portfolio_returns if date in benchmark_returns]


def _portfolio_time_weighted_return_series(daily_states: list) -> list[tuple[str, float]]:
    ordered_states = sorted(daily_states, key=lambda item: item.date)
    returns: list[tuple[str, float]] = []
    previous_state = None
    for state in ordered_states:
        if previous_state is None:
            previous_state = state
            continue
        previous_value = previous_state.total_portfolio_value
        if previous_value == 0:
            previous_state = state
            continue
        daily_return = ((state.total_portfolio_value - state.external_cash_flow) / previous_value) - 1
        returns.append((state.date, daily_return))
        previous_state = state
    return returns


def _benchmark_return_series(benchmark_rows: list[dict]) -> dict[str, float]:
    return _selected_history_return_series(benchmark_rows)


def _aligned_active_return_series(portfolio_returns: list[tuple[str, float]], benchmark_returns: dict[str, float]) -> list[tuple[str, float, float, float]]:
    return [
        (date, portfolio_return, benchmark_returns[date], portfolio_return - benchmark_returns[date])
        for date, portfolio_return in portfolio_returns
        if date in benchmark_returns
    ]


def _infer_sector_from_sources(sources: list[LookThroughSource]) -> str:
    resolved = " ".join(source.resolved_via.upper() for source in sources)
    if any(token in resolved for token in ["XLF"]):
        return "Financials"
    if any(token in resolved for token in ["XLV", "IBB"]):
        return "Health Care"
    if any(token in resolved for token in ["ITA", "PPA"]):
        return "Defense"
    if any(token in resolved for token in ["BIL", "VGSH"]):
        return "Fixed Income"
    if any(token in resolved for token in ["ICOM", "SGLD", "ISLN", "SLV"]):
        return "Commodities"
    if any(token in resolved for token in ["SPY", "VUAA"]):
        return "Broad Market"
    return "Other"


def _build_shared_sector_overlap(
    shared_symbols: list[str],
    left_holdings: dict[str, tuple[str, float]],
    right_holdings: dict[str, tuple[str, float]],
    left_resolved: str,
    right_resolved: str,
    market_data: HoldingsMarketData,
    sector_cache: dict[str, str],
) -> list[LookThroughSectorExposure]:
    registry = InstrumentRegistry()
    sector_totals: defaultdict[str, float] = defaultdict(float)
    total_overlap = 0.0
    proxy_sector = _infer_sector_from_resolved_pair(left_resolved, right_resolved)
    for symbol in shared_symbols:
        overlap_weight = min(left_holdings[symbol][1], right_holdings[symbol][1])
        if symbol in sector_cache:
            sector = sector_cache[symbol]
        else:
            instrument = registry.get_instrument(symbol)
            if instrument and instrument.sector:
                sector = instrument.sector
            elif proxy_sector is not None:
                sector = proxy_sector
            else:
                profile = market_data.get_company_profile(symbol)
                sector = str((profile or {}).get("sector") or "Other")
            sector_cache[symbol] = sector
        sector_totals[sector] += overlap_weight
        total_overlap += overlap_weight
    return [
        LookThroughSectorExposure(sector=sector, market_value=round(weight, 4), weight=round(weight / total_overlap, 4) if total_overlap else 0.0)
        for sector, weight in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    ]


def _infer_sector_from_resolved_pair(left_resolved: str, right_resolved: str) -> str | None:
    resolved = f"{left_resolved} {right_resolved}".upper()
    if any(token in resolved for token in ["ITA", "PPA"]):
        return "Defense"
    if any(token in resolved for token in ["XLF"]):
        return "Financials"
    if any(token in resolved for token in ["XLV", "IBB"]):
        return "Health Care"
    if any(token in resolved for token in ["BIL", "VGSH", "IEF"]):
        return "Fixed Income"
    if any(token in resolved for token in ["DBC", "ICOM", "SGLD", "ISLN", "SLV"]):
        return "Commodities"
    return None


def _orthogonalize_factor_series(active_factors: list[tuple[str, str]], factor_series: dict[str, list[float]]) -> list[tuple[str, str, list[float]]]:
    orthogonalized_factors: list[tuple[str, str, list[float]]] = []
    for factor, proxy in active_factors:
        values = factor_series[factor]
        if not orthogonalized_factors:
            orthogonalized_factors.append((factor, proxy, values))
            continue

        design_matrix = [[1.0] + [prior_values[index] for _, _, prior_values in orthogonalized_factors] for index in range(len(values))]
        coefficients = _least_squares(design_matrix, values, ridge_lambda=1e-5)
        fitted = [_dot(row, coefficients) for row in design_matrix]
        residualized = [actual - expected for actual, expected in zip(values, fitted, strict=False)]
        if not any(abs(value) > 1e-12 for value in residualized):
            orthogonalized_factors.append((factor, proxy, values))
            continue
        orthogonalized_factors.append((factor, proxy, residualized))
    return orthogonalized_factors




def _orthogonalize_factors_window(raw_factors: list[tuple[str, str, list[float]]]) -> list[tuple[str, str, list[float]]]:
    """Gram-Schmidt orthogonalization over a single pre-sliced window.

    Unlike _orthogonalize_factor_series (which works from a full-series dict),
    this helper operates on already-windowed (factor, proxy, values) tuples.
    Calling this inside every rolling-window iteration guarantees that the
    resulting factors are mutually uncorrelated *within that window*, which is
    the correctness requirement for per-window ridge OLS.
    """
    orthogonalized: list[tuple[str, str, list[float]]] = []
    for factor, proxy, values in raw_factors:
        if not orthogonalized:
            orthogonalized.append((factor, proxy, values))
            continue
        design_matrix = [[1.0] + [prior_values[i] for _, _, prior_values in orthogonalized] for i in range(len(values))]
        proj_coefficients = _least_squares(design_matrix, values, ridge_lambda=1e-5)
        fitted = [_dot(row, proj_coefficients) for row in design_matrix]
        residualized = [actual - expected for actual, expected in zip(values, fitted, strict=False)]
        if not any(abs(v) > 1e-12 for v in residualized):
            # Factor is collinear with earlier ones in this window — keep raw to
            # preserve its label for coefficient mapping, but coefficient is unreliable.
            orthogonalized.append((factor, proxy, values))
            continue
        orthogonalized.append((factor, proxy, residualized))
    return orthogonalized


def _fit_factor_model(y: list[float], orthogonalized_factors: list[tuple[str, str, list[float]]], ridge_lambda: float = 1e-5) -> tuple[list[float], list[float], float | None]:
    x = [[1.0] + [values[index] for _, _, values in orthogonalized_factors] for index in range(len(y))]
    coefficients = _least_squares(x, y, ridge_lambda=ridge_lambda)
    fitted = [_dot(row, coefficients) for row in x]
    residuals = [actual - expected for actual, expected in zip(y, fitted, strict=False)]
    mean_y = sum(y) / len(y)
    ss_total = sum((value - mean_y) ** 2 for value in y)
    ss_resid = sum(residual**2 for residual in residuals)
    r_squared = None if ss_total == 0 else max(0.0, 1 - (ss_resid / ss_total))
    return coefficients, residuals, r_squared


def _build_rolling_factor_loadings(dates: list[str], y: list[float], raw_factors: list[tuple[str, str, list[float]]], window: int = 20) -> list[RollingFactorLoadingPoint]:
    """Build rolling OLS factor loadings with per-window orthogonalization.

    For each date t the function:
      1. Slices the raw factor return series to the rolling window [t-w+1, t].
      2. Gram-Schmidt orthogonalizes the sliced factors so they are uncorrelated
         *within this window* (not just over the full history).
      3. Fits ridge OLS with a window-proportional floor (see ROLLING_RIDGE_FLOOR)
         to prevent coefficient blowup in short, near-singular windows.

    raw_factors must be the unorthogonalized series; the caller (build_statistical_factor_model)
    is responsible for passing raw_factor_data, not the globally-orthogonalized series.
    """
    points: list[RollingFactorLoadingPoint] = []
    factor_keys = {definition.label: definition.key for definition in DEFAULT_FACTOR_DEFINITIONS}
    min_observations = WINDOW_MIN_OBSERVATIONS.get(window, window)
    ridge_floor = ROLLING_RIDGE_FLOOR.get(window, 1e-5)
    for index, date in enumerate(dates):
        if index + 1 < min_observations:
            points.append(RollingFactorLoadingPoint(date=date))
            continue
        start = index - window + 1
        y_window = y[start : index + 1]
        raw_window = [(factor, proxy, values[start : index + 1]) for factor, proxy, values in raw_factors]
        # Per-window Gram-Schmidt: orthogonalize within this window so that each
        # coefficient is a clean partial loading after controlling for higher-priority factors.
        orthogonalized_window = _orthogonalize_factors_window(raw_window)
        coefficients, residuals, r_squared = _fit_factor_model(y_window, orthogonalized_window, ridge_lambda=ridge_floor)
        values_map = {factor_keys[factor]: round(coefficients[position + 1], 4) for position, (factor, _, _) in enumerate(orthogonalized_window) if factor in factor_keys}
        points.append(
            RollingFactorLoadingPoint(
                date=date,
                r_squared=round(r_squared, 4) if r_squared is not None else None,
                residual_vol=round(_calculate_annualized_volatility(residuals) * 100, 2) if len(residuals) >= 2 else None,
                **values_map,
            )
        )
    return points


def _latest_loading(points: list[RollingFactorLoadingPoint], key: str) -> float | None:
    for point in reversed(points):
        value = getattr(point, key, None)
        if value is not None:
            return float(value)
    return None


def _factor_availability(points: list[RollingFactorLoadingPoint], key: str) -> str:
    return "available" if _latest_loading(points, key) is not None else "insufficient"


def _interpret_loading(value: float | None) -> str:
    if value is None:
        return "Insufficient data"
    if value > 0.30:
        return "Meaningful positive exposure"
    if value > 0.10:
        return "Mild positive exposure"
    if value >= -0.10:
        return "Neutral / little exposure"
    if value >= -0.30:
        return "Mild negative exposure"
    return "Meaningful negative exposure"


def _build_current_factor_snapshot(
    rolling_loadings_20d: list[RollingFactorLoadingPoint],
    rolling_loadings_60d: list[RollingFactorLoadingPoint],
    rolling_loadings_252d: list[RollingFactorLoadingPoint],
) -> list[SnapshotItem]:
    factors: list[SnapshotItem] = []
    latest_date = next((point.date for point in reversed(rolling_loadings_60d) if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)), None)
    _ = latest_date
    for definition in DEFAULT_FACTOR_DEFINITIONS:
        latest_60d = _latest_loading(rolling_loadings_60d, definition.key)
        latest_20d = _latest_loading(rolling_loadings_20d, definition.key)
        latest_252d = _latest_loading(rolling_loadings_252d, definition.key)
        latest_loading = latest_60d if latest_60d is not None else latest_20d if latest_20d is not None else latest_252d
        factors.append(
            SnapshotItem(
                key=definition.key,
                label=definition.label,
                category=definition.category,
                us_proxy=definition.us_proxy,
                latest_loading=round(latest_loading, 4) if latest_loading is not None else None,
                target_exposure=definition.target_exposure,
                primary_mapping=_to_ucits_mapping(definition.primary_mapping),
                alternative_mappings=_compact_ucits_mappings(definition.alternative_mappings),
                ucits_examples=list(definition.ucits_examples),
                mapping_quality=definition.mapping_quality,
                description=definition.description,
            )
        )
    return factors


def _to_ucits_mapping(mapping: UcitsCandidateMapping | None):
    if mapping is None:
        return None

    from app.schemas.reconciliation import UcitsMapping

    definition = next((item for item in DEFAULT_FACTOR_DEFINITIONS if item.primary_mapping == mapping or mapping in item.alternative_mappings), None)

    return UcitsMapping(
        provider=mapping.provider,
        fund_name=mapping.fund_name,
        isin=mapping.isin,
        example_tickers=list(mapping.example_tickers),
        asset_exposure=mapping.asset_exposure,
        domicile=mapping.domicile,
        trading_currency=mapping.trading_currency,
        base_currency=mapping.base_currency,
        currency_hedged=mapping.currency_hedged,
        distribution_policy=mapping.distribution_policy,
        mapping_quality=mapping.mapping_quality,
        notes=mapping.notes,
        match_summary=_compute_mapping_match_summary_for_definition(mapping, definition),
    )


def _loading_n_periods_ago(points: list[RollingFactorLoadingPoint], key: str, periods: int) -> float | None:
    values = [float(getattr(point, key)) for point in points if getattr(point, key) is not None]
    if len(values) <= periods:
        return None
    return values[-(periods + 1)]


def _build_factor_shift_snapshot(
    definition: FactorProxyDefinition,
    model: StatisticalFactorModel,
    collinearity_by_window: dict[int, FactorCollinearityDiagnostics],
    volatility_regime: VolatilityRegimePayload,
) -> FactorShiftSnapshot:
    current_loading_20d = _latest_loading(model.rolling_loadings_20d, definition.key)
    current_loading_60d = _latest_loading(model.rolling_loadings_60d, definition.key)
    current_loading_252d = _latest_loading(model.rolling_loadings_252d, definition.key)

    prior_loading_20d = _loading_n_periods_ago(model.rolling_loadings_20d, definition.key, 20)
    prior_loading_60d = _loading_n_periods_ago(model.rolling_loadings_60d, definition.key, 60)

    change_20d = round(current_loading_20d - prior_loading_20d, 4) if current_loading_20d is not None and prior_loading_20d is not None else None
    change_60d = round(current_loading_60d - prior_loading_60d, 4) if current_loading_60d is not None and prior_loading_60d is not None else None
    abs_change_20d = round(abs(change_20d), 4) if change_20d is not None else None
    abs_change_60d = round(abs(change_60d), 4) if change_60d is not None else None
    stability_gap_20d_60d = round(abs(current_loading_20d - current_loading_60d), 4) if current_loading_20d is not None and current_loading_60d is not None else None
    stability_gap_60d_252d = round(abs(current_loading_60d - current_loading_252d), 4) if current_loading_60d is not None and current_loading_252d is not None else None

    collinearity_pairs = collinearity_by_window.get(60)
    collinearity_flag = any(
        definition.key in {pair.left_key, pair.right_key}
        for pair in (collinearity_pairs.high_collinearity_pairs if collinearity_pairs else [])
    )
    vol_ratio = volatility_regime.snapshot.vol_ratio_20_60
    volatility_flag = volatility_regime.regime.label == "stressed" or (vol_ratio is not None and vol_ratio > VOLATILITY_RATIO_FLAG_THRESHOLD)
    available_windows_count = sum(value is not None for value in [current_loading_20d, current_loading_60d, current_loading_252d])

    return FactorShiftSnapshot(
        key=definition.key,
        label=definition.label,
        us_proxy=definition.us_proxy,
        category=definition.category,
        current_loading_20d=round(current_loading_20d, 4) if current_loading_20d is not None else None,
        current_loading_60d=round(current_loading_60d, 4) if current_loading_60d is not None else None,
        current_loading_252d=round(current_loading_252d, 4) if current_loading_252d is not None else None,
        change_20d=change_20d,
        change_60d=change_60d,
        abs_change_20d=abs_change_20d,
        abs_change_60d=abs_change_60d,
        stability_gap_20d_60d=stability_gap_20d_60d,
        stability_gap_60d_252d=stability_gap_60d_252d,
        available_windows_count=available_windows_count,
        shift_flag_20d=abs_change_20d is not None and abs_change_20d >= SHIFT_FLAG_20D_THRESHOLD,
        shift_flag_60d=abs_change_60d is not None and abs_change_60d >= SHIFT_FLAG_60D_THRESHOLD,
        stability_flag=(stability_gap_20d_60d is not None and stability_gap_20d_60d >= STABILITY_GAP_THRESHOLD) or (stability_gap_60d_252d is not None and stability_gap_60d_252d >= STABILITY_GAP_THRESHOLD),
        collinearity_flag=collinearity_flag,
        volatility_flag=volatility_flag,
        confidence=_factor_shift_confidence(available_windows_count, collinearity_flag),
    )


def _factor_shift_confidence(available_windows_count: int, collinearity_flag: bool) -> str:
    if available_windows_count >= 3 and not collinearity_flag:
        return "high"
    if available_windows_count >= 2:
        return "medium"
    return "low"


def _rank_factor_shifts(snapshots: list[FactorShiftSnapshot], mode: str, limit: int = 5) -> list[RankedFactorShiftItem]:
    if mode == "positive_20d":
        ranked = sorted((item for item in snapshots if item.change_20d is not None and item.change_20d > 0), key=lambda item: item.change_20d or 0.0, reverse=True)
        return [_to_ranked_shift_item(item, item.current_loading_20d, item.change_20d, item.abs_change_20d) for item in ranked[:limit]]
    if mode == "negative_20d":
        ranked = sorted((item for item in snapshots if item.change_20d is not None and item.change_20d < 0), key=lambda item: item.change_20d or 0.0)
        return [_to_ranked_shift_item(item, item.current_loading_20d, item.change_20d, item.abs_change_20d) for item in ranked[:limit]]
    if mode == "absolute_60d":
        ranked = sorted((item for item in snapshots if item.abs_change_60d is not None), key=lambda item: item.abs_change_60d or 0.0, reverse=True)
        return [_to_ranked_shift_item(item, item.current_loading_60d, item.change_60d, item.abs_change_60d) for item in ranked[:limit]]
    ranked = sorted((item for item in snapshots if item.abs_change_20d is not None), key=lambda item: item.abs_change_20d or 0.0, reverse=True)
    return [_to_ranked_shift_item(item, item.current_loading_20d, item.change_20d, item.abs_change_20d) for item in ranked[:limit]]


def _to_ranked_shift_item(
    snapshot: FactorShiftSnapshot,
    current_loading: float | None,
    change_value: float | None,
    absolute_change: float | None,
) -> RankedFactorShiftItem:
    return RankedFactorShiftItem(
        key=snapshot.key,
        label=snapshot.label,
        us_proxy=snapshot.us_proxy,
        current_loading=current_loading,
        change_value=change_value,
        absolute_change=absolute_change,
    )


def _build_factor_risk_contributions(
    factor_registry: list[FactorProxyDefinition],
    factor_histories: dict[str, list[dict]],
    model: StatisticalFactorModel,
) -> tuple[list[FactorRiskContributionItem], float, int]:
    latest_loadings = _latest_valid_60d_loadings(model)
    eligible_definitions = [definition for definition in factor_registry if latest_loadings.get(definition.key) is not None]
    factor_returns = {
        definition.key: _selected_history_return_series(factor_histories.get(definition.us_proxy, []))
        for definition in eligible_definitions
    }
    common_dates = sorted(set.intersection(*[set(values.keys()) for values in factor_returns.values() if values])) if any(factor_returns.values()) else []
    window_dates = common_dates[-RISK_CONTRIBUTION_WINDOW_DAYS:]
    covariance_matrix = _compute_covariance_matrix([definition.key for definition in eligible_definitions], factor_returns, window_dates)
    factor_total_variance = _portfolio_variance_from_covariance(
        [definition.key for definition in eligible_definitions],
        latest_loadings,
        covariance_matrix,
    )

    def _rounded_optional(value: float | None, digits: int) -> float | None:
        return round(float(value), digits) if value is not None else None

    contributions: list[FactorRiskContributionItem] = []
    for definition in factor_registry:
        loading = latest_loadings.get(definition.key)
        returns_map = factor_returns.get(definition.key, {})
        returns = [returns_map[date] for date in window_dates if date in returns_map]
        volatility = _calculate_annualized_volatility(returns) if len(returns) >= 2 else None
        variance_contribution = None
        if loading is not None and factor_total_variance > 0:
            marginal_variance = sum((covariance_matrix.get((definition.key, other.key)) or 0.0) * latest_loadings.get(other.key, 0.0) for other in eligible_definitions)
            variance_contribution = loading * marginal_variance

        contributions.append(
            FactorRiskContributionItem(
                key=definition.key,
                label=definition.label,
                us_proxy=definition.us_proxy,
                loading=_rounded_optional(loading, 4),
                factor_volatility=round((volatility or 0.0) * 100, 2) if volatility is not None else None,
                variance_contribution=round(variance_contribution, 8) if variance_contribution is not None else None,
                risk_share=round((variance_contribution / factor_total_variance), 4) if variance_contribution is not None and factor_total_variance > 0 else None,
            )
        )
    contributions.sort(key=lambda item: item.risk_share if item.risk_share is not None else -1.0, reverse=True)
    return contributions, factor_total_variance, len(window_dates)


def _build_position_risk_contributions(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
) -> tuple[list[PositionRiskContributionItem], float, int]:
    total_market_value = sum(position.market_value for position in snapshot.positions)
    position_returns = {
        position.symbol: _selected_history_return_series(price_histories.get(position.symbol, []))
        for position in snapshot.positions
    }
    common_dates = sorted(set.intersection(*[set(values.keys()) for values in position_returns.values() if values])) if any(position_returns.values()) else []
    window_dates = common_dates[-RISK_CONTRIBUTION_WINDOW_DAYS:]
    symbols = [position.symbol for position in snapshot.positions]
    weights = {position.symbol: (position.market_value / total_market_value) if total_market_value else 0.0 for position in snapshot.positions}
    covariance_matrix = _compute_covariance_matrix(symbols, position_returns, window_dates)
    component_contributions, portfolio_variance = _component_risk_contributions(symbols, weights, covariance_matrix)

    contributions: list[PositionRiskContributionItem] = []
    for symbol in symbols:
        returns = [position_returns[symbol][date] for date in window_dates if date in position_returns[symbol]]
        variance = covariance_matrix.get((symbol, symbol))
        weight = weights[symbol]
        marginal = None
        if portfolio_variance > 0 and variance is not None:
            cov_with_portfolio = sum(weights[other] * (covariance_matrix.get((symbol, other)) or 0.0) for other in symbols)
            portfolio_vol = sqrt(portfolio_variance)
            marginal = cov_with_portfolio / portfolio_vol if portfolio_vol > 0 else None
        component = component_contributions.get(symbol)
        contributions.append(
            PositionRiskContributionItem(
                symbol=symbol,
                weight=round(weight, 4),
                volatility=round(_calculate_annualized_volatility(returns) * 100, 2) if len(returns) >= 2 else None,
                marginal_contribution=round(marginal, 8) if marginal is not None else None,
                component_contribution=round(component, 8) if component is not None else None,
                risk_share=round((component / sqrt(portfolio_variance)), 4) if component is not None and portfolio_variance > 0 else None,
            )
        )

    contributions.sort(key=lambda item: item.risk_share if item.risk_share is not None else -1.0, reverse=True)
    return contributions, portfolio_variance, len(window_dates)


def _compute_covariance_matrix(
    symbols: list[str],
    returns_by_symbol: dict[str, dict[str, float]],
    dates: list[str],
) -> dict[tuple[str, str], float | None]:
    matrix: dict[tuple[str, str], float | None] = {}
    for left_symbol in symbols:
        left_values = [returns_by_symbol[left_symbol][date] for date in dates if date in returns_by_symbol[left_symbol]]
        for right_symbol in symbols:
            right_values = [returns_by_symbol[right_symbol][date] for date in dates if date in returns_by_symbol[right_symbol]]
            if len(left_values) < 2 or len(right_values) < 2 or len(left_values) != len(right_values):
                matrix[(left_symbol, right_symbol)] = None
            else:
                matrix[(left_symbol, right_symbol)] = _sample_covariance(left_values, right_values)
    return matrix


def _portfolio_variance_from_covariance(
    symbols: list[str],
    weights: dict[str, float],
    covariance_matrix: dict[tuple[str, str], float | None],
) -> float:
    portfolio_variance = 0.0
    for left_symbol in symbols:
        for right_symbol in symbols:
            covariance = covariance_matrix.get((left_symbol, right_symbol))
            if covariance is not None:
                portfolio_variance += weights.get(left_symbol, 0.0) * weights.get(right_symbol, 0.0) * covariance
    return portfolio_variance if portfolio_variance > 0 else 0.0


def _component_risk_contributions(
    symbols: list[str],
    weights: dict[str, float],
    covariance_matrix: dict[tuple[str, str], float | None],
) -> tuple[dict[str, float | None], float]:
    portfolio_variance = _portfolio_variance_from_covariance(symbols, weights, covariance_matrix)
    if portfolio_variance <= 0:
        return {symbol: None for symbol in symbols}, 0.0

    portfolio_vol = sqrt(portfolio_variance)
    contributions: dict[str, float | None] = {}
    for symbol in symbols:
        cov_with_portfolio = sum(weights[other] * (covariance_matrix.get((symbol, other)) or 0.0) for other in symbols)
        marginal = cov_with_portfolio / portfolio_vol if portfolio_vol > 0 else None
        contributions[symbol] = weights[symbol] * marginal if marginal is not None else None
    return contributions, portfolio_variance


def _sum_top_risk_shares(values: list[float | None], limit: int) -> float | None:
    valid = sorted((value for value in values if value is not None), reverse=True)
    if not valid:
        return None
    return round(sum(valid[:limit]), 4)


def _herfindahl_index(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return round(sum(value * value for value in valid), 4)


def _latest_valid_60d_loadings(model: StatisticalFactorModel) -> dict[str, float]:
    latest_point = next(
        (
            point
            for point in reversed(model.rolling_loadings_60d)
            if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)
        ),
        None,
    )
    if latest_point is None:
        return {}
    return {
        definition.key: float(getattr(latest_point, definition.key))
        for definition in DEFAULT_FACTOR_DEFINITIONS
        if getattr(latest_point, definition.key) is not None
    }


def _calculate_stability_score(model: StatisticalFactorModel) -> float | None:
    latest_20d = next((point for point in reversed(model.rolling_loadings_20d) if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)), None)
    latest_60d = next((point for point in reversed(model.rolling_loadings_60d) if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)), None)
    latest_252d = next((point for point in reversed(model.rolling_loadings_252d) if any(getattr(point, definition.key) is not None for definition in DEFAULT_FACTOR_DEFINITIONS)), None)

    gaps: list[float] = []
    for definition in DEFAULT_FACTOR_DEFINITIONS:
        loading_20d = float(getattr(latest_20d, definition.key)) if latest_20d and getattr(latest_20d, definition.key) is not None else None
        loading_60d = float(getattr(latest_60d, definition.key)) if latest_60d and getattr(latest_60d, definition.key) is not None else None
        loading_252d = float(getattr(latest_252d, definition.key)) if latest_252d and getattr(latest_252d, definition.key) is not None else None
        if loading_20d is not None and loading_60d is not None:
            gaps.append(abs(loading_20d - loading_60d))
        if loading_60d is not None and loading_252d is not None:
            gaps.append(abs(loading_60d - loading_252d))

    if not gaps:
        return None
    average_gap = sum(gaps) / len(gaps)
    return round(max(0.0, min(1.0, 1 - average_gap)), 4)


def _model_reliability_confidence(status: str, r_squared: float | None, collinearity_pair_count: int, missing_factor_count: int) -> str:
    if status == "insufficient_history":
        return "low"
    if r_squared is not None and r_squared >= 0.65 and collinearity_pair_count <= 1 and missing_factor_count <= 2:
        return "high"
    if r_squared is not None and r_squared >= 0.4:
        return "medium"
    return "low"


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


def _series_to_returns(series: list[tuple[str, float]]) -> dict[str, float]:
    ordered = sorted(series, key=lambda item: item[0])
    returns: dict[str, float] = {}
    previous_value: float | None = None
    for date, value in ordered:
        if previous_value is not None and previous_value != 0:
            returns[date] = (value / previous_value) - 1
        previous_value = value
    return returns


def _calculate_beta(values: list[float], benchmark: list[float]) -> float | None:
    if len(values) < 2 or len(benchmark) < 2 or len(values) != len(benchmark):
        return None
    benchmark_variance = _sample_variance(benchmark)
    if benchmark_variance == 0:
        return None
    return _sample_covariance(values, benchmark) / benchmark_variance


def _calculate_correlation(values: list[float], benchmark: list[float]) -> float | None:
    if len(values) < 2 or len(benchmark) < 2 or len(values) != len(benchmark):
        return None
    values_std = _sample_standard_deviation(values)
    benchmark_std = _sample_standard_deviation(benchmark)
    if values_std == 0 or benchmark_std == 0:
        return None
    return _sample_covariance(values, benchmark) / (values_std * benchmark_std)


def _calculate_annualized_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return _sample_standard_deviation(values) * sqrt(252)


def _sample_covariance(left: list[float], right: list[float]) -> float:
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    return sum((l - mean_left) * (r - mean_right) for l, r in zip(left, right, strict=False)) / (len(left) - 1)


def _sample_variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _sample_standard_deviation(values: list[float]) -> float:
    return sqrt(_sample_variance(values))
