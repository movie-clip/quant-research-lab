from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from math import log, sqrt
from statistics import median

from app.datasets import DatasetCatalog
from app.schemas.generic_ranking import (
    CompositeScoreTrace,
    EligibilityRecord,
    FactorConfig,
    GenericRankingComponentScore,
    GenericRankingExcludedInstrument,
    GenericRankingRequest,
    GenericRankingResponse,
    GenericRankingRow,
    GenericRankingRunMetadata,
    ScoreConfigRef,
)
from app.schemas.research import BarRecord
from app.services.universe_resolver import UniverseResolver

logger = logging.getLogger(__name__)

GENERIC_RANKING_METHODOLOGY_ID = "generic_ranking_methodology_v1"

# ── Factor ID set supported in Phase 1 ───────────────────────────────────────

SUPPORTED_FACTOR_IDS = frozenset(
    [
        "momentum_1m",
        "momentum_3m",
        "momentum_6m",
        "momentum_12m",
        "momentum_blended",
        "realized_volatility_126d",
        "realized_volatility_252d",
        "downside_volatility_126d",
        "max_drawdown_126d",
        "max_drawdown_252d",
        "liquidity_60d",
    ]
)

# How many monthly bars each factor needs:
FACTOR_LOOKBACK_MONTHS: dict[str, int] = {
    "momentum_1m": 2,
    "momentum_3m": 4,
    "momentum_6m": 7,
    "momentum_12m": 13,
    "momentum_blended": 13,
    "realized_volatility_126d": 7,   # ~6 months of monthly returns
    "realized_volatility_252d": 13,  # ~12 months
    "downside_volatility_126d": 7,
    "max_drawdown_126d": 7,
    "max_drawdown_252d": 13,
    "liquidity_60d": 4,              # ~3 months (60 trading days ≈ 3 months of monthly bars)
}


# ── Math helpers (reimplement locally so we don't modify strategy_lab) ────────

def _window_returns(bars: list[BarRecord]) -> list[float]:
    return [(bars[i].close / bars[i - 1].close) - 1 for i in range(1, len(bars))]


def _annualized_volatility(returns: list[float]) -> float:
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((v - mean) ** 2 for v in returns) / len(returns)
    return sqrt(variance) * sqrt(12)


def _annualized_downside_volatility(returns: list[float]) -> float:
    if not returns:
        return 0.0
    downside = [min(v, 0.0) for v in returns]
    variance = sum(v ** 2 for v in downside) / len(downside)
    return sqrt(variance) * sqrt(12)


def _max_drawdown(bars: list[BarRecord]) -> float:
    peak = 0.0
    max_dd = 0.0
    for bar in bars:
        peak = max(peak, bar.close)
        if peak <= 0:
            continue
        dd = (bar.close / peak) - 1
        max_dd = min(max_dd, dd)
    return max_dd


def _blended_momentum(bars: list[BarRecord]) -> float:
    if len(bars) < 2:
        return 0.0
    latest_close = bars[-1].close
    one_month_ago = bars[-2].close
    if one_month_ago <= 0:
        return 0.0
    if len(bars) >= 13:
        m12_1 = (one_month_ago / bars[-13].close) - 1 if bars[-13].close > 0 else 0.0
        m6_1 = (one_month_ago / bars[-7].close) - 1 if bars[-7].close > 0 else 0.0
        return (0.6 * m12_1) + (0.4 * m6_1)
    if len(bars) >= 7:
        return (one_month_ago / bars[-7].close) - 1 if bars[-7].close > 0 else 0.0
    return (latest_close / bars[0].close) - 1 if bars[0].close > 0 else 0.0


def _median_dollar_volume(bars: list[BarRecord]) -> float:
    dollar_vols = [
        bar.close * float(bar.volume)
        for bar in bars
        if bar.volume is not None and bar.close > 0
    ]
    if not dollar_vols:
        return 0.0
    return log(1 + median(dollar_vols))


# ── Factor computation ────────────────────────────────────────────────────────

def _compute_raw_value(factor_id: str, bars: list[BarRecord]) -> float | None:
    """Return raw factor value for the given sorted monthly bars. Returns None on insufficient data."""
    required = FACTOR_LOOKBACK_MONTHS.get(factor_id, 2)
    if len(bars) < required:
        return None

    window = bars[-required:]
    returns = _window_returns(window)

    if factor_id == "momentum_1m":
        return (window[-1].close / window[-2].close) - 1 if window[-2].close > 0 else None
    if factor_id == "momentum_3m":
        return (window[-1].close / window[0].close) - 1 if window[0].close > 0 else None
    if factor_id == "momentum_6m":
        return (window[-1].close / window[0].close) - 1 if window[0].close > 0 else None
    if factor_id == "momentum_12m":
        return (window[-1].close / window[0].close) - 1 if window[0].close > 0 else None
    if factor_id == "momentum_blended":
        return _blended_momentum(bars[-13:] if len(bars) >= 13 else bars)
    if factor_id == "realized_volatility_126d":
        return _annualized_volatility(returns)
    if factor_id == "realized_volatility_252d":
        return _annualized_volatility(returns)
    if factor_id == "downside_volatility_126d":
        return _annualized_downside_volatility(returns)
    if factor_id == "max_drawdown_126d":
        return abs(_max_drawdown(window))
    if factor_id == "max_drawdown_252d":
        return abs(_max_drawdown(window))
    if factor_id == "liquidity_60d":
        return _median_dollar_volume(bars[-4:] if len(bars) >= 4 else bars)

    return None


# ── Cross-sectional normalization ─────────────────────────────────────────────

def _winsorize(values: list[float], pct: float) -> list[float]:
    if pct <= 0 or len(values) < 2:
        return list(values)
    sorted_v = sorted(values)
    n = len(sorted_v)
    lo_idx = max(0, int(n * pct) - 1)
    hi_idx = min(n - 1, n - int(n * pct))
    lo = sorted_v[lo_idx]
    hi = sorted_v[hi_idx]
    return [max(lo, min(hi, v)) for v in values]


def _zscore_normalize(values: list[float], direction: str) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = sqrt(variance) if variance > 0 else 1.0
    scores = [(v - mean) / std for v in values]
    if direction == "lower_is_better":
        scores = [-s for s in scores]
    return scores


def _percentile_rank_normalize(values: list[float], direction: str) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    sorted_v = sorted(values, reverse=(direction == "higher_is_better"))
    # handle ties: average rank
    positions: dict[float, list[int]] = defaultdict(list)
    for i, v in enumerate(sorted_v):
        positions[v].append(i + 1)
    avg_rank: dict[float, float] = {v: sum(idxs) / len(idxs) / n for v, idxs in positions.items()}
    return [avg_rank[v] for v in values]


def _minmax_normalize(values: list[float], direction: str) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    if direction == "lower_is_better":
        return [(hi - v) / (hi - lo) for v in values]
    return [(v - lo) / (hi - lo) for v in values]


def _normalize_factor_scores(
    raw_values: list[float],
    direction: str,
    method: str,
    winsorize_pct: float,
) -> tuple[list[float], float, float]:
    """Return (normalized_scores, mean_of_raw, std_of_raw)."""
    winsorized = _winsorize(raw_values, winsorize_pct)
    mean_val = sum(winsorized) / len(winsorized) if winsorized else 0.0
    variance = sum((v - mean_val) ** 2 for v in winsorized) / len(winsorized) if winsorized else 0.0
    std_val = sqrt(variance)

    if method == "cross_sectional_zscore":
        scores = _zscore_normalize(winsorized, direction)
    elif method == "percentile_rank":
        scores = _percentile_rank_normalize(winsorized, direction)
    elif method == "minmax":
        scores = _minmax_normalize(winsorized, direction)
    else:
        scores = _zscore_normalize(winsorized, direction)

    return scores, mean_val, std_val


# ── Main service entry point ──────────────────────────────────────────────────

def build_generic_ranking(request: GenericRankingRequest) -> GenericRankingResponse:
    warnings: list[str] = []
    score_config = request.score_config
    universe_spec = request.universe_spec

    # ── Resolve universe ──────────────────────────────────────────────────────
    resolver = UniverseResolver(fmp_client=None)  # No live FMP for Phase 1
    # Use sample data path — we pick the as_of_date from available bars below

    dataset_catalog = DatasetCatalog()

    # Determine symbols
    universe_snapshot_temp = resolver.resolve(universe_spec, "pending")
    symbols = list(universe_snapshot_temp.evaluated_members)

    if not symbols:
        raise ValueError("Universe resolved to zero symbols")

    # ── Load price bars ───────────────────────────────────────────────────────
    bars_by_symbol: dict[str, list[BarRecord]] = {}
    for sym in symbols:
        bars = dataset_catalog.get_daily_bars(sym)
        if bars:
            bars_by_symbol[sym] = sorted(bars, key=lambda b: b.date)

    # Determine as_of_date from the latest common date across symbols with data
    all_dates: list[set[str]] = [
        {b.date for b in bars}
        for bars in bars_by_symbol.values()
        if bars
    ]
    if not all_dates:
        raise ValueError("No price data available for any symbol in the universe")

    # as_of_date = latest date present in any loaded series
    latest_dates = [max(dates) for dates in all_dates]
    as_of_date = max(latest_dates)

    # Re-resolve universe snapshot with the real as_of_date
    universe_snapshot = resolver.resolve(universe_spec, as_of_date)

    # ── Validate factor config ────────────────────────────────────────────────
    valid_factors: list[FactorConfig] = []
    for fc in score_config.factors:
        if fc.factor_id not in SUPPORTED_FACTOR_IDS:
            warnings.append(
                f"factor_id={fc.factor_id!r} is not supported in Phase 1 and will be skipped"
            )
        else:
            valid_factors.append(fc)

    if not valid_factors:
        raise ValueError("No supported factors remain after filtering unsupported factor_ids")

    # ── Compute raw values per symbol per factor ──────────────────────────────
    # symbol → {factor_id → raw_value | None}
    raw_by_symbol: dict[str, dict[str, float | None]] = {}
    excluded_instruments: list[GenericRankingExcludedInstrument] = []

    for sym in symbols:
        bars = bars_by_symbol.get(sym)
        if not bars:
            excluded_instruments.append(
                GenericRankingExcludedInstrument(
                    symbol=sym,
                    eligibility=EligibilityRecord(
                        eligibility_status="excluded",
                        hard_filter_failures=["no_price_data"],
                    ),
                )
            )
            continue
        raw_by_symbol[sym] = {fc.factor_id: _compute_raw_value(fc.factor_id, bars) for fc in valid_factors}

    eligible_symbols = list(raw_by_symbol.keys())
    if not eligible_symbols:
        raise ValueError("No symbols had sufficient price history for ranking")

    # Additional exclusion: if ALL factors have None raw value for a symbol
    final_eligible: list[str] = []
    for sym in eligible_symbols:
        factor_vals = raw_by_symbol[sym]
        if all(v is None for v in factor_vals.values()):
            excluded_instruments.append(
                GenericRankingExcludedInstrument(
                    symbol=sym,
                    eligibility=EligibilityRecord(
                        eligibility_status="excluded",
                        hard_filter_failures=["insufficient_history_all_factors"],
                    ),
                )
            )
        else:
            final_eligible.append(sym)

    if not final_eligible:
        raise ValueError("No symbols had computable scores for any factor")

    # ── Normalize cross-sectionally per factor ────────────────────────────────
    norm_method = score_config.normalization
    winsorize_pct = score_config.winsorize_pct
    norm_weights = score_config.normalized_weights()

    # Build per-factor arrays (only over final_eligible, substituting None with mean)
    factor_raw_arrays: dict[str, list[float]] = {}
    factor_has_data: dict[str, list[bool]] = {}

    for fc in valid_factors:
        raws: list[float] = []
        has_data: list[bool] = []
        for sym in final_eligible:
            v = raw_by_symbol[sym][fc.factor_id]
            has_data.append(v is not None)
            raws.append(v if v is not None else float("nan"))
        factor_raw_arrays[fc.factor_id] = raws
        factor_has_data[fc.factor_id] = has_data

    # Replace NaN with cross-sectional mean of available values for normalization
    factor_norm_scores: dict[str, list[float]] = {}
    factor_means: dict[str, float] = {}
    factor_stds: dict[str, float] = {}

    for fc in valid_factors:
        raws = factor_raw_arrays[fc.factor_id]
        available = [v for v, hd in zip(raws, factor_has_data[fc.factor_id]) if hd]
        fill = sum(available) / len(available) if available else 0.0
        filled = [v if factor_has_data[fc.factor_id][i] else fill for i, v in enumerate(raws)]

        scores, mean_v, std_v = _normalize_factor_scores(
            filled, fc.direction, norm_method, winsorize_pct
        )
        factor_norm_scores[fc.factor_id] = scores
        factor_means[fc.factor_id] = round(mean_v, 6)
        factor_stds[fc.factor_id] = round(std_v, 6)

    # ── Build ranked rows ─────────────────────────────────────────────────────
    rows: list[GenericRankingRow] = []
    for idx, sym in enumerate(final_eligible):
        composite = 0.0
        component_scores: dict[str, GenericRankingComponentScore] = {}
        for fc in valid_factors:
            raw_v = raw_by_symbol[sym][fc.factor_id]
            norm_score = factor_norm_scores[fc.factor_id][idx]
            weight = norm_weights.get(fc.factor_id, 0.0)
            weighted = norm_score * weight if norm_score is not None else None
            composite += weighted if weighted is not None else 0.0
            component_scores[fc.factor_id] = GenericRankingComponentScore(
                label=fc.factor_id.replace("_", " ").title(),
                family=fc.family,
                direction=fc.direction,
                raw_value=round(raw_v, 6) if raw_v is not None else None,
                raw_unit=fc.raw_unit,
                normalized_score=round(norm_score, 6) if norm_score is not None else None,
                normalization_method=norm_method,
                weight=round(weight, 6),
                weighted_score=round(weighted, 6) if weighted is not None else None,
            )
        rows.append(
            GenericRankingRow(
                rank=0,  # assigned after sort
                symbol=sym,
                composite_score=round(composite, 6),
                component_scores=component_scores,
                eligibility=EligibilityRecord(eligibility_status="eligible"),
            )
        )

    rows.sort(key=lambda r: r.composite_score, reverse=True)
    for i, row in enumerate(rows, start=1):
        row.rank = i

    # ── Composite score trace ─────────────────────────────────────────────────
    composite_score_trace = CompositeScoreTrace(
        normalization_method=norm_method,
        winsorize_pct=winsorize_pct,
        universe_size_at_normalization=len(final_eligible),
        cross_sectional_mean=factor_means,
        cross_sectional_std=factor_stds,
    )

    # ── Score config ref ──────────────────────────────────────────────────────
    score_config_digest = hashlib.sha256(
        json.dumps(score_config.model_dump(), sort_keys=True, default=str).encode()
    ).hexdigest()

    score_config_ref = ScoreConfigRef(
        score_config_id=score_config.score_config_id,
        score_config_version=score_config.score_config_version,
        score_config_digest=score_config_digest,
        factor_ids=[fc.factor_id for fc in valid_factors],
        normalization=norm_method,
        winsorize_pct=winsorize_pct,
    )

    # ── Confidence ────────────────────────────────────────────────────────────
    all_have_all_factors = all(
        all(raw_by_symbol[sym].get(fc.factor_id) is not None for fc in valid_factors)
        for sym in final_eligible
    )
    confidence: str
    if excluded_instruments:
        confidence = "partial"
    elif not all_have_all_factors:
        confidence = "partial"
    else:
        confidence = "full"

    # ── Run metadata ──────────────────────────────────────────────────────────
    run_metadata = GenericRankingRunMetadata(
        ranking_id="generic_ranking_engine_v1",
        methodology_id=GENERIC_RANKING_METHODOLOGY_ID,
        as_of_date=as_of_date,
        ranking_basis_date=as_of_date,
        price_basis="close",
        confidence=confidence,  # type: ignore[arg-type]
        score_config_ref=score_config_ref,
        composite_score_trace=composite_score_trace,
    )

    return GenericRankingResponse(
        ranking_id="generic_ranking_engine_v1",
        methodology_id=GENERIC_RANKING_METHODOLOGY_ID,
        title=f"Generic Ranking: {universe_spec.universe_id}",
        as_of_date=as_of_date,
        benchmark_symbol=request.benchmark_symbol,
        lookback_months=request.lookback_months,
        universe_spec_snapshot=universe_snapshot,
        run_metadata=run_metadata,
        ranked_universe=rows,
        excluded_instruments=excluded_instruments,
        warnings=warnings,
    )
