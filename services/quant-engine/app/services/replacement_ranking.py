from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from math import log, sqrt
from statistics import median

from app.instruments.registry import InstrumentRegistry
from app.schemas.research import (
    BarRecord,
    IntentBoundEtfReplacementCandidateRow,
    IntentBoundEtfReplacementNormalizedRequest,
    IntentBoundEtfReplacementNormalizedScores,
    IntentBoundEtfReplacementRankingRequest,
    IntentBoundEtfReplacementRankingResponse,
    IntentBoundEtfReplacementRankingRunMetadata,
    IntentBoundEtfReplacementRawFactors,
)
from app.services.market_data import MarketDataService
from app.services.strategy_lab import _max_drawdown

RANKING_ID = "intent_bound_etf_replacement_ranking_v1"
METHODOLOGY_ID = "intent_bound_etf_replacement_ranking_methodology_v1"
FACTOR_WEIGHTS = {
    "momentum": 0.40,
    "realized_volatility": 0.20,
    "max_drawdown": 0.20,
    "liquidity": 0.20,
}
TIE_BREAK_ORDER = [
    "higher composite score",
    "higher normalized momentum",
    "lower raw max_drawdown_252d",
    "higher raw liquidity_60d",
    "lexicographically smaller symbol",
]


@dataclass(frozen=True)
class _EligibleCandidate:
    symbol: str
    raw_factors: IntentBoundEtfReplacementRawFactors


def build_intent_bound_etf_replacement_ranking(request: IntentBoundEtfReplacementRankingRequest) -> IntentBoundEtfReplacementRankingResponse:
    normalized_request = _normalize_request(request)
    request_hash = _build_request_hash(request, normalized_request)
    source_status: set[str] = set()
    warnings: list[str] = []

    unavailable_reason = _validate_seed_context(request, normalized_request)
    if unavailable_reason is not None:
        return _build_unavailable_response(request, normalized_request, request_hash, unavailable_reason, [], warnings, "sample")

    registry = InstrumentRegistry()
    base_instrument = registry.get_instrument(normalized_request.base_symbol)
    if base_instrument is None or base_instrument.asset_class != "etf":
        return _build_unavailable_response(request, normalized_request, request_hash, "replacement intent base symbol is unresolved or not etf", [], warnings, "sample")
    if (base_instrument.category or "").strip().lower() != normalized_request.peer_group.strip().lower():
        return _build_unavailable_response(request, normalized_request, request_hash, "replacement intent base symbol does not match the seeded peer group", [], warnings, "sample")

    market_data = MarketDataService()
    raw_histories = _load_raw_histories(market_data, normalized_request.seeded_symbols, normalized_request.ranking_basis_date)
    histories = {symbol: _normalize_history_rows(raw_histories.get(symbol, []), normalized_request.ranking_basis_date) for symbol in normalized_request.seeded_symbols}
    for symbol in normalized_request.seeded_symbols:
        resolved = market_data.get_last_fetch_meta(symbol)
        if resolved is None:
            source_status.add("sample")
        else:
            source_status.add("live")

    excluded: list[IntentBoundEtfReplacementCandidateRow] = []
    eligible: list[_EligibleCandidate] = []
    for symbol in normalized_request.seeded_symbols:
        exclusion_reason = _candidate_exclusion_reason(symbol, request, normalized_request, registry, raw_histories, histories)
        if exclusion_reason is not None:
            excluded.append(_build_excluded_row(symbol, request, normalized_request.ranking_basis_date, exclusion_reason))
            continue
        eligible.append(_EligibleCandidate(symbol=symbol, raw_factors=_compute_raw_factors(histories[symbol], normalized_request.ranking_basis_date)))

    if not eligible:
        warnings.append("All seeded ETF candidates were excluded under the V1 intent-bound replacement ranking rules.")
        return _build_unavailable_response(request, normalized_request, request_hash, "no eligible seeded ETF candidates remain after exclusions", excluded, warnings, _collapse_source_status(source_status))

    ranked = _rank_candidates(eligible, request, normalized_request.ranking_basis_date)
    return IntentBoundEtfReplacementRankingResponse(
        ranking_id=RANKING_ID,
        methodology_id=METHODOLOGY_ID,
        basis_date=normalized_request.ranking_basis_date,
        status="ok",
        request=request,
        normalized_request=normalized_request,
        request_hash=request_hash,
        run_metadata=IntentBoundEtfReplacementRankingRunMetadata(
            ranking_id=RANKING_ID,
            methodology_id=METHODOLOGY_ID,
            basis_date=normalized_request.ranking_basis_date,
            request_hash=request_hash,
            source_status=_collapse_source_status(source_status),
            tie_break_order=TIE_BREAK_ORDER,
            factor_weights=FACTOR_WEIGHTS,
        ),
        eligible_count=len(ranked),
        excluded_count=len(excluded),
        ranked_candidates=ranked,
        excluded_candidates=excluded,
        warnings=warnings,
        unavailable_reason=None,
    )


def _normalize_request(request: IntentBoundEtfReplacementRankingRequest) -> IntentBoundEtfReplacementNormalizedRequest:
    return IntentBoundEtfReplacementNormalizedRequest(
        base_symbol=request.replacement_intent.base_symbol.upper(),
        candidate_symbol=request.replacement_intent.candidate_symbol.upper(),
        seeded_symbols=sorted({symbol.upper() for symbol in request.seed_context.seeded_symbols if symbol}),
        peer_group=request.seed_context.peer_group.strip(),
        ranking_basis_date=request.seed_context.ranking_basis_date,
    )


def _build_request_hash(request: IntentBoundEtfReplacementRankingRequest, normalized_request: IntentBoundEtfReplacementNormalizedRequest) -> str:
    payload = {
        "ranking_id": RANKING_ID,
        "methodology_id": METHODOLOGY_ID,
        "workspace_id": request.replacement_intent.workspace_id,
        "draft_id": request.replacement_intent.draft_id,
        "base_node_id": request.replacement_intent.base_node_id,
        "base_symbol": normalized_request.base_symbol,
        "candidate_symbol": normalized_request.candidate_symbol,
        "peer_group": normalized_request.peer_group,
        "ranking_basis_date": normalized_request.ranking_basis_date,
        "seeded_symbols": normalized_request.seeded_symbols,
        "factor_weights": FACTOR_WEIGHTS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_seed_context(request: IntentBoundEtfReplacementRankingRequest, normalized_request: IntentBoundEtfReplacementNormalizedRequest) -> str | None:
    if not normalized_request.seeded_symbols:
        raise ValueError("seed_context.seeded_symbols must include at least one symbol")
    if request.replacement_intent.seed_ranking_id != request.seed_context.ranking_id:
        return "replacement intent seed ranking id does not match the seed context"
    if request.replacement_intent.seed_methodology_id != request.seed_context.methodology_id:
        return "replacement intent seed methodology id does not match the seed context"
    if request.replacement_intent.seed_ranking_basis_date != request.seed_context.ranking_basis_date:
        return "replacement intent seed ranking basis date does not match the seed context"
    if request.replacement_intent.peer_group.strip().lower() != request.seed_context.peer_group.strip().lower():
        return "replacement intent peer group does not match the seed context"
    if normalized_request.candidate_symbol not in normalized_request.seeded_symbols:
        return "replacement intent candidate symbol is not present in the seeded candidate set"
    return None


def _load_raw_histories(market_data: MarketDataService, symbols: list[str], basis_date_text: str) -> dict[str, list[dict]]:
    basis_date = date.fromisoformat(basis_date_text)
    from_date = (basis_date - timedelta(days=500)).isoformat()
    return market_data.get_historical_prices_for_symbols(symbols, from_date, basis_date.isoformat())


def _normalize_history_rows(rows: list[dict], basis_date_text: str) -> list[BarRecord]:
    normalized: list[BarRecord] = []
    for row in rows:
        row_date = row.get("date")
        if not isinstance(row_date, str) or row_date > basis_date_text:
            continue
        close = row.get("adjClose")
        if close is None:
            close = row.get("adjusted_close")
        if close is None:
            close = row.get("close")
        raw_close = row.get("close")
        if close is None or raw_close is None:
            continue
        normalized.append(
            BarRecord(
                date=row_date,
                open=float(raw_close),
                high=float(raw_close),
                low=float(raw_close),
                close=float(close),
                volume=float(row.get("volume")) if row.get("volume") is not None else None,
            )
        )
    normalized.sort(key=lambda item: item.date)
    return normalized


def _candidate_exclusion_reason(
    symbol: str,
    request: IntentBoundEtfReplacementRankingRequest,
    normalized_request: IntentBoundEtfReplacementNormalizedRequest,
    registry: InstrumentRegistry,
    raw_histories: dict[str, list[dict]],
    histories: dict[str, list[BarRecord]],
) -> str | None:
    if symbol not in normalized_request.seeded_symbols:
        return "symbol is not present in the seeded candidate set"
    if symbol == normalized_request.base_symbol:
        return "symbol matches the incumbent base symbol"
    instrument = registry.get_instrument(symbol)
    if instrument is None:
        return "instrument metadata is unresolved"
    if instrument.asset_class != "etf":
        return f"instrument metadata marks {symbol} as {instrument.asset_class}, not etf"
    if (instrument.category or "").strip().lower() != normalized_request.peer_group.strip().lower():
        return f"replacement compatibility failed: instrument category {instrument.category or 'unknown'} does not match seeded peer group {normalized_request.peer_group}"
    adjusted_rows = [row for row in raw_histories.get(symbol, []) if isinstance(row.get("date"), str) and row["date"] <= normalized_request.ranking_basis_date and (row.get("adjClose") is not None or row.get("adjusted_close") is not None)]
    if len(adjusted_rows) < 252:
        return "candidate lacks required 252d adjusted-price history"
    if len(adjusted_rows) < 126:
        return "candidate lacks required 126d adjusted-price history"
    bars = histories.get(symbol, [])
    if len([bar for bar in bars[-60:] if bar.volume is not None and bar.close > 0]) < 60:
        return "candidate lacks required 60d close-volume history"
    return None


def _compute_raw_factors(bars: list[BarRecord], basis_date_text: str) -> IntentBoundEtfReplacementRawFactors:
    basis_bars = [bar for bar in bars if bar.date <= basis_date_text]
    one_month_ago = basis_bars[-21].close
    twelve_month_anchor = basis_bars[-252].close
    six_month_anchor = basis_bars[-126].close
    momentum_12_1 = (one_month_ago / twelve_month_anchor) - 1
    momentum_6_1 = (one_month_ago / six_month_anchor) - 1
    recent_126 = basis_bars[-126:]
    daily_returns = [(recent_126[index].close / recent_126[index - 1].close) - 1 for index in range(1, len(recent_126))]
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((value - mean) ** 2 for value in daily_returns) / len(daily_returns)
    liquidity_window = basis_bars[-60:]
    liquidity_values = [bar.close * float(bar.volume) for bar in liquidity_window if bar.volume is not None and bar.close > 0]
    return IntentBoundEtfReplacementRawFactors(
        momentum_12_1=round(momentum_12_1, 8),
        momentum_6_1=round(momentum_6_1, 8),
        momentum_blended=round((0.6 * momentum_12_1) + (0.4 * momentum_6_1), 8),
        realized_volatility_126d=round(sqrt(variance) * sqrt(252), 8),
        max_drawdown_252d=round(abs(_max_drawdown(basis_bars[-252:])), 8),
        liquidity_60d=round(log(1 + median(liquidity_values)), 8),
    )


def _percentile_rank(values: list[float], value: float, *, higher_is_better: bool) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return 1.0
    if higher_is_better:
        count = sum(1 for candidate in ordered if candidate < value)
    else:
        count = sum(1 for candidate in ordered if candidate > value)
    return round(count / (len(ordered) - 1), 8)


def _rank_candidates(candidates: list[_EligibleCandidate], request: IntentBoundEtfReplacementRankingRequest, basis_date_text: str) -> list[IntentBoundEtfReplacementCandidateRow]:
    momentum_values = [candidate.raw_factors.momentum_blended for candidate in candidates]
    vol_values = [candidate.raw_factors.realized_volatility_126d for candidate in candidates]
    drawdown_values = [candidate.raw_factors.max_drawdown_252d for candidate in candidates]
    liquidity_values = [candidate.raw_factors.liquidity_60d for candidate in candidates]
    rows: list[IntentBoundEtfReplacementCandidateRow] = []
    for candidate in candidates:
        normalized_scores = IntentBoundEtfReplacementNormalizedScores(
            momentum=_percentile_rank(momentum_values, candidate.raw_factors.momentum_blended, higher_is_better=True),
            realized_volatility=_percentile_rank(vol_values, candidate.raw_factors.realized_volatility_126d, higher_is_better=False),
            max_drawdown=_percentile_rank(drawdown_values, candidate.raw_factors.max_drawdown_252d, higher_is_better=False),
            liquidity=_percentile_rank(liquidity_values, candidate.raw_factors.liquidity_60d, higher_is_better=True),
        )
        composite_score = round(
            (FACTOR_WEIGHTS["momentum"] * normalized_scores.momentum)
            + (FACTOR_WEIGHTS["realized_volatility"] * normalized_scores.realized_volatility)
            + (FACTOR_WEIGHTS["max_drawdown"] * normalized_scores.max_drawdown)
            + (FACTOR_WEIGHTS["liquidity"] * normalized_scores.liquidity),
            8,
        )
        rows.append(
            IntentBoundEtfReplacementCandidateRow(
                symbol=candidate.symbol,
                rank=None,
                composite_score=composite_score,
                raw_factors=candidate.raw_factors,
                normalized_scores=normalized_scores,
                eligibility_status="eligible",
                exclusion_reason=None,
                basis_date=basis_date_text,
                draft_id=request.replacement_intent.draft_id,
                base_node_id=request.replacement_intent.base_node_id,
                base_symbol=request.replacement_intent.base_symbol.upper(),
                seed_ranking_id=request.replacement_intent.seed_ranking_id,
                seed_methodology_id=request.replacement_intent.seed_methodology_id,
            )
        )

    rows.sort(
        key=lambda row: (
            -(row.composite_score or 0.0),
            -(row.normalized_scores.momentum if row.normalized_scores else 0.0),
            row.raw_factors.max_drawdown_252d if row.raw_factors else 0.0,
            -(row.raw_factors.liquidity_60d if row.raw_factors else 0.0),
            row.symbol,
        )
    )
    for index, row in enumerate(rows, start=1):
        row.rank = index
    return rows


def _build_excluded_row(symbol: str, request: IntentBoundEtfReplacementRankingRequest, basis_date_text: str, exclusion_reason: str) -> IntentBoundEtfReplacementCandidateRow:
    return IntentBoundEtfReplacementCandidateRow(
        symbol=symbol,
        rank=None,
        composite_score=None,
        raw_factors=None,
        normalized_scores=None,
        eligibility_status="excluded",
        exclusion_reason=exclusion_reason,
        basis_date=basis_date_text,
        draft_id=request.replacement_intent.draft_id,
        base_node_id=request.replacement_intent.base_node_id,
        base_symbol=request.replacement_intent.base_symbol.upper(),
        seed_ranking_id=request.replacement_intent.seed_ranking_id,
        seed_methodology_id=request.replacement_intent.seed_methodology_id,
    )


def _build_unavailable_response(
    request: IntentBoundEtfReplacementRankingRequest,
    normalized_request: IntentBoundEtfReplacementNormalizedRequest,
    request_hash: str,
    unavailable_reason: str,
    excluded: list[IntentBoundEtfReplacementCandidateRow],
    warnings: list[str],
    source_status: str,
) -> IntentBoundEtfReplacementRankingResponse:
    return IntentBoundEtfReplacementRankingResponse(
        ranking_id=RANKING_ID,
        methodology_id=METHODOLOGY_ID,
        basis_date=normalized_request.ranking_basis_date,
        status="unavailable",
        request=request,
        normalized_request=normalized_request,
        request_hash=request_hash,
        run_metadata=IntentBoundEtfReplacementRankingRunMetadata(
            ranking_id=RANKING_ID,
            methodology_id=METHODOLOGY_ID,
            basis_date=normalized_request.ranking_basis_date,
            request_hash=request_hash,
            source_status=source_status,
            tie_break_order=TIE_BREAK_ORDER,
            factor_weights=FACTOR_WEIGHTS,
        ),
        eligible_count=0,
        excluded_count=len(excluded),
        ranked_candidates=[],
        excluded_candidates=excluded,
        warnings=warnings,
        unavailable_reason=unavailable_reason,
    )


def _collapse_source_status(statuses: set[str]) -> str:
    if not statuses:
        return "sample"
    if len(statuses) == 1:
        return next(iter(statuses))
    return "mixed"
