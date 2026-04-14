from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from app.datasets import DatasetCatalog
from app.schemas.research import BarRecord
from app.schemas.research import EtfConstituentInternalsObservation, EtfLeaderConstituent, EtfLeaderInternalsObservation, EtfMomentumMetrics, EtfMomentumObservation, EtfMomentumPoint, EtfMomentumSourceStatus, EtfMomentumStrategyResponse, EtfMomentumWeight
from app.services.market_data import MarketDataService

DEFAULT_ETF_ROTATION_UNIVERSE = ["XLK", "XLF", "XLV", "XLE", "XLI", "QQQ", "IWM"]
DEFAULT_ETF_ROTATION_BENCHMARK = "SPY"
LIVE_HISTORY_BUFFER_MONTHS = 84
LIVE_LEADER_CONSTITUENT_LIMIT = 12


@dataclass(frozen=True)
class _NormalizedHoldingsSnapshot:
    snapshot_date: str
    holdings: list[dict[str, str | float]]


@dataclass(frozen=True)
class _RankedAsset:
    symbol: str
    score: float
    trailing_return_pct: float
    average_volume: float | None


@dataclass(frozen=True)
class _StrategyBaseData:
    bars_by_symbol: dict[str, list[BarRecord]]
    price_source_label: str
    internals_mode: str
    price_history_status: str


@dataclass(frozen=True)
class _LeaderInternalsBuildResult:
    observations: list[EtfLeaderInternalsObservation]
    etf_internals_history: dict[str, list[EtfConstituentInternalsObservation]]
    status: EtfMomentumSourceStatus


def build_etf_momentum_strategy_analysis(
    universe: list[str] | None = None,
    benchmark_symbol: str = DEFAULT_ETF_ROTATION_BENCHMARK,
    lookback_months: int = 3,
    top_n: int = 3,
    prefer_live_data: bool = False,
) -> EtfMomentumStrategyResponse:
    symbols = [symbol.upper() for symbol in (universe or DEFAULT_ETF_ROTATION_UNIVERSE)]
    benchmark = benchmark_symbol.upper()
    dataset_catalog = DatasetCatalog()

    base_data = _load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog)
    bars_by_symbol = dict(base_data.bars_by_symbol)

    common_dates = sorted(
        set.intersection(*[{bar.date for bar in bars if bar.date} for bars in bars_by_symbol.values() if bars])
    )
    if len(common_dates) <= lookback_months:
        raise ValueError("Not enough ETF history for the selected momentum lookback")

    by_symbol_and_date = {
        symbol: {bar.date: bar for bar in bars}
        for symbol, bars in bars_by_symbol.items()
    }

    observations: list[EtfMomentumObservation] = []
    strategy_equity = 100.0
    benchmark_equity = 100.0
    equity_curve: list[EtfMomentumPoint] = []
    strategy_returns: list[float] = []
    benchmark_returns: list[float] = []
    turnover_values: list[float] = []
    participation_values: list[float] = []
    previous_weights: dict[str, float] = {}

    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        ranked = _rank_assets(symbols, by_symbol_and_date, common_dates, index, lookback_months)
        selected = ranked[:top_n]
        target_weight = 1 / len(selected) if selected else 0.0
        holdings = [
            EtfMomentumWeight(
                symbol=item.symbol,
                target_weight=target_weight,
                score=item.score,
                trailing_return_pct=item.trailing_return_pct,
                average_volume=item.average_volume,
            )
            for item in selected
        ]

        current_weights = {item.symbol: target_weight for item in selected}
        turnover_values.append(_turnover(previous_weights, current_weights))
        previous_weights = current_weights
        average_participation = _participation_ratio(selected, ranked)
        participation_values.append(average_participation)

        strategy_return = sum(_monthly_return(by_symbol_and_date[item.symbol], current_date) for item in selected) / len(selected) if selected else 0.0
        benchmark_return = _monthly_return(by_symbol_and_date[benchmark], current_date)
        strategy_returns.append(strategy_return)
        benchmark_returns.append(benchmark_return)
        strategy_equity *= 1 + strategy_return
        benchmark_equity *= 1 + benchmark_return

        observations.append(
            EtfMomentumObservation(
                date=current_date,
                rankings=[
                    EtfMomentumWeight(
                        symbol=item.symbol,
                        target_weight=target_weight if position < top_n else 0.0,
                        score=item.score,
                        trailing_return_pct=item.trailing_return_pct,
                        average_volume=item.average_volume,
                    )
                    for position, item in enumerate(ranked)
                ],
                holdings=holdings,
                leader=selected[0].symbol if selected else None,
                leader_score=selected[0].score if selected else None,
                benchmark_return_pct=benchmark_return * 100,
                strategy_return_pct=strategy_return * 100,
                average_volume_ratio=average_participation,
            )
        )

        equity_curve.append(
            EtfMomentumPoint(
                date=current_date,
                strategy_equity=round(strategy_equity, 4),
                benchmark_equity=round(benchmark_equity, 4),
            )
        )

    leader_internals_result = _build_leader_internals_series(
        observations=observations,
        universe=symbols,
        base_by_symbol_and_date=by_symbol_and_date,
        common_dates=common_dates,
        lookback_months=lookback_months,
        benchmark=benchmark,
        dataset_catalog=dataset_catalog,
        prefer_live_data=prefer_live_data and base_data.internals_mode == "live",
    )
    source_status = leader_internals_result.status.model_copy(update={"price_history": base_data.price_history_status})

    _apply_drawdowns(equity_curve)
    latest_holdings = observations[-1].holdings if observations else []
    latest_rankings = _rank_assets(symbols, by_symbol_and_date, common_dates, len(common_dates) - 1, lookback_months)
    current_target_weight = 1 / top_n if top_n else 0.0

    return EtfMomentumStrategyResponse(
        strategy_id="book_etf_cross_sectional_momentum",
        title="ETF Cross-Sectional Momentum",
        benchmark_symbol=benchmark,
        universe=symbols,
        start_date=common_dates[0],
        end_date=common_dates[-1],
        lookback_months=lookback_months,
        top_n=top_n,
        methodology=_build_methodology(base_data.price_source_label, base_data.internals_mode),
        current_rankings=[
            EtfMomentumWeight(
                symbol=item.symbol,
                target_weight=current_target_weight if position < top_n else 0.0,
                score=item.score,
                trailing_return_pct=item.trailing_return_pct,
                average_volume=item.average_volume,
            )
            for position, item in enumerate(latest_rankings)
        ],
        latest_holdings=latest_holdings,
        observations=observations,
        leader_internals=leader_internals_result.observations,
        etf_internals_history=leader_internals_result.etf_internals_history,
        source_status=source_status,
        equity_curve=equity_curve,
        metrics=_build_metrics(strategy_returns, benchmark_returns, turnover_values, participation_values, strategy_equity, benchmark_equity, equity_curve),
    )


def _load_base_data(
    symbols: list[str],
    benchmark: str,
    lookback_months: int,
    prefer_live_data: bool,
    dataset_catalog: DatasetCatalog,
) -> _StrategyBaseData:
    requested_symbols = [*symbols, benchmark]
    if prefer_live_data:
        live_bars_by_symbol = _load_live_monthly_bars(requested_symbols, lookback_months)
        if _has_sufficient_history(live_bars_by_symbol, requested_symbols, lookback_months):
            return _StrategyBaseData(
                bars_by_symbol=live_bars_by_symbol,
                price_source_label="live FMP monthly history with local file-cache fallback",
                internals_mode="live",
                price_history_status="live",
            )

    sample_bars_by_symbol = {symbol: dataset_catalog.get_daily_bars(symbol) for symbol in requested_symbols}
    return _StrategyBaseData(
        bars_by_symbol=sample_bars_by_symbol,
        price_source_label="local sample monthly history",
        internals_mode="sample",
        price_history_status="sample",
    )


def _load_live_monthly_bars(symbols: list[str], lookback_months: int) -> dict[str, list[BarRecord]]:
    market_data = MarketDataService()
    to_date = date.today()
    history_months = max(lookback_months + 24, LIVE_HISTORY_BUFFER_MONTHS)
    from_date = to_date - timedelta(days=history_months * 31)
    bars_by_symbol: dict[str, list[BarRecord]] = {}
    for symbol in symbols:
        rows = market_data.get_historical_prices(symbol, from_date.isoformat(), to_date.isoformat())
        bars_by_symbol[symbol] = _rows_to_monthly_bars(rows)
    return bars_by_symbol


def _has_sufficient_history(bars_by_symbol: Mapping[str, list[BarRecord]], symbols: list[str], lookback_months: int) -> bool:
    if any(not bars_by_symbol.get(symbol) for symbol in symbols):
        return False
    common_dates = sorted(
        set.intersection(*[{bar.date for bar in bars_by_symbol[symbol] if bar.date} for symbol in symbols])
    )
    return len(common_dates) > lookback_months


def _rows_to_monthly_bars(rows: list[dict[str, Any]]) -> list[BarRecord]:
    if not rows:
        return []

    latest_by_month: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_date = str(row.get("date") or "")
        if len(raw_date) < 7:
            continue
        month_key = raw_date[:7]
        existing = latest_by_month.get(month_key)
        if existing is None or raw_date > str(existing.get("date") or ""):
            latest_by_month[month_key] = row

    monthly_rows: list[BarRecord] = []
    for month_key in sorted(latest_by_month):
        row = latest_by_month[month_key]
        price_value = row.get("price", row.get("close"))
        if price_value is None:
            continue
        close = float(price_value)
        volume_value = row.get("volume")
        monthly_rows.append(
            BarRecord(
                date=str(row.get("date")),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=float(volume_value) if volume_value is not None else None,
            )
        )
    return monthly_rows


def _build_sample_etf_internals_history(
    universe: list[str],
    observations: list[EtfMomentumObservation],
    by_symbol_and_date: Mapping[str, Mapping[str, BarRecord]],
    common_dates: list[str],
    lookback_months: int,
    dataset_catalog: DatasetCatalog,
) -> dict[str, list[EtfConstituentInternalsObservation]]:
    history: dict[str, list[EtfConstituentInternalsObservation]] = {symbol: [] for symbol in universe}
    observation_dates = {observation.date for observation in observations}
    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        if current_date not in observation_dates:
            continue
        lookback_date = common_dates[index - lookback_months]
        for etf_symbol in universe:
            row = _build_leader_internals_from_holdings(
                holdings=dataset_catalog.get_etf_holdings_for_date(etf_symbol, current_date),
                by_symbol_and_date=by_symbol_and_date,
                current_date=current_date,
                lookback_date=lookback_date,
                leader_symbol=etf_symbol,
            )
            history[etf_symbol].append(
                EtfConstituentInternalsObservation(
                    date=current_date,
                    etf_symbol=etf_symbol,
                    source_mode="sample",
                    snapshot_date=current_date,
                    constituents=row.constituents,
                )
            )
    return history


def _build_live_etf_internals_history(
    universe: list[str],
    observations: list[EtfMomentumObservation],
    by_symbol_and_date: Mapping[str, Mapping[str, BarRecord]],
    common_dates: list[str],
    lookback_months: int,
    dataset_catalog: DatasetCatalog,
) -> dict[str, list[EtfConstituentInternalsObservation]]:
    market_data = MarketDataService()
    series_by_symbol_and_date = {symbol: dict(rows) for symbol, rows in by_symbol_and_date.items()}
    history: dict[str, list[EtfConstituentInternalsObservation]] = {symbol: [] for symbol in universe}
    observation_dates = {observation.date for observation in observations}
    constituent_symbols: set[str] = set()
    holdings_cache: dict[tuple[str, str], tuple[str, str, list[dict[str, str | float]]]] = {}

    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        if current_date not in observation_dates:
            continue
        for etf_symbol in universe:
            _, dated_holdings_rows = market_data.get_etf_holdings_for_date(etf_symbol, current_date)
            normalized_snapshot = _normalize_fmp_holdings_snapshot(dated_holdings_rows)
            source_mode = "live-dated"
            snapshot_date = normalized_snapshot.snapshot_date if normalized_snapshot is not None else current_date
            holdings = normalized_snapshot.holdings[:LIVE_LEADER_CONSTITUENT_LIMIT] if normalized_snapshot is not None else dataset_catalog.get_etf_holdings_for_date(etf_symbol, current_date)[:LIVE_LEADER_CONSTITUENT_LIMIT]
            if normalized_snapshot is None:
                source_mode = "sample"
            holdings_cache[(etf_symbol, current_date)] = (source_mode, snapshot_date, holdings)
            constituent_symbols.update(str(row["symbol"]).upper() for row in holdings)

    if constituent_symbols:
        start_date = common_dates[0]
        end_date = common_dates[-1]
        for symbol, monthly_bars in _load_live_constituent_bars(sorted(constituent_symbols), start_date, end_date, dataset_catalog).items():
            if monthly_bars:
                series_by_symbol_and_date[symbol] = {bar.date: bar for bar in monthly_bars}

    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        if current_date not in observation_dates:
            continue
        lookback_date = common_dates[index - lookback_months]
        for etf_symbol in universe:
            source_mode, snapshot_date, holdings = holdings_cache[(etf_symbol, current_date)]
            row = _build_leader_internals_from_holdings(
                holdings=holdings,
                by_symbol_and_date=series_by_symbol_and_date,
                current_date=current_date,
                lookback_date=lookback_date,
                leader_symbol=etf_symbol,
            )
            history[etf_symbol].append(
                EtfConstituentInternalsObservation(
                    date=current_date,
                    etf_symbol=etf_symbol,
                    source_mode=source_mode,
                    snapshot_date=snapshot_date,
                    constituents=row.constituents,
                )
            )
    return history


def _build_leader_internals_series(
    observations: list[EtfMomentumObservation],
    universe: list[str],
    base_by_symbol_and_date: dict[str, dict[str, BarRecord]],
    common_dates: list[str],
    lookback_months: int,
    benchmark: str,
    dataset_catalog: DatasetCatalog,
    prefer_live_data: bool,
) -> _LeaderInternalsBuildResult:
    if not observations:
        return _LeaderInternalsBuildResult(
            observations=[],
            etf_internals_history={},
            status=EtfMomentumSourceStatus(price_history="sample", leader_internals="sample", holdings_snapshot_counts={}, dated_holdings_symbols=[], sample_fallback_symbols=[]),
        )

    if prefer_live_data:
        return _build_live_leader_internals_series(observations, universe, base_by_symbol_and_date, common_dates, lookback_months, dataset_catalog)

    required_symbols = sorted(
        {
            str(row["symbol"]).upper()
            for etf_symbol in {benchmark, *universe}
            for row in dataset_catalog.get_etf_holdings(etf_symbol)
        }
    )
    for symbol in required_symbols:
        if symbol not in base_by_symbol_and_date:
            base_by_symbol_and_date[symbol] = {bar.date: bar for bar in dataset_catalog.get_daily_bars(symbol)}

    by_date = {observation.date: observation for observation in observations}
    leader_internals: list[EtfLeaderInternalsObservation] = []
    etf_internals_history = _build_sample_etf_internals_history(universe, observations, by_symbol_and_date=base_by_symbol_and_date, common_dates=common_dates, lookback_months=lookback_months, dataset_catalog=dataset_catalog)
    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        observation = by_date.get(current_date)
        if observation is None:
            continue
        leader_internals.append(
            _build_leader_internals_from_holdings(
                holdings=dataset_catalog.get_etf_holdings_for_date(observation.leader, current_date) if observation.leader else [],
                by_symbol_and_date=base_by_symbol_and_date,
                current_date=current_date,
                lookback_date=common_dates[index - lookback_months],
                leader_symbol=observation.leader,
            ).model_copy(update={"source_mode": "sample", "snapshot_date": current_date})
        )
    return _LeaderInternalsBuildResult(
        observations=leader_internals,
        etf_internals_history=etf_internals_history,
        status=EtfMomentumSourceStatus(
            price_history="sample",
            leader_internals="sample",
            holdings_snapshot_counts={},
            dated_holdings_symbols=[],
            sample_fallback_symbols=sorted({observation.leader for observation in observations if observation.leader}),
        ),
    )


def _build_live_leader_internals_series(
    observations: list[EtfMomentumObservation],
    universe: list[str],
    base_by_symbol_and_date: dict[str, dict[str, BarRecord]],
    common_dates: list[str],
    lookback_months: int,
    dataset_catalog: DatasetCatalog,
) -> _LeaderInternalsBuildResult:
    market_data = MarketDataService()
    holdings_by_leader_and_date: dict[tuple[str, str], _NormalizedHoldingsSnapshot] = {}
    constituent_symbols: set[str] = set()
    holdings_snapshot_counts: dict[str, int] = {}
    dated_holdings_symbols: set[str] = set()
    sample_fallback_symbols: set[str] = set()

    leader_dates_by_symbol: dict[str, list[str]] = {}
    for observation in observations:
        if observation.leader is None:
            continue
        leader_dates_by_symbol.setdefault(observation.leader, []).append(observation.date)

    for leader_symbol, checkpoint_dates in leader_dates_by_symbol.items():
        holdings_snapshot_counts[leader_symbol] = market_data.holdings_history.get_snapshot_count(leader_symbol)
        for checkpoint_date in sorted(set(checkpoint_dates)):
            _, dated_holdings_rows = market_data.get_etf_holdings_for_date(leader_symbol, checkpoint_date)
            normalized_snapshot = _normalize_fmp_holdings_snapshot(dated_holdings_rows)
            if normalized_snapshot is None:
                fallback_holdings = dataset_catalog.get_etf_holdings_for_date(leader_symbol, checkpoint_date)
                normalized_snapshot = _NormalizedHoldingsSnapshot(
                    snapshot_date=checkpoint_date,
                    holdings=fallback_holdings[:LIVE_LEADER_CONSTITUENT_LIMIT],
                )
                sample_fallback_symbols.add(leader_symbol)
            else:
                normalized_snapshot = _NormalizedHoldingsSnapshot(
                    snapshot_date=normalized_snapshot.snapshot_date,
                    holdings=normalized_snapshot.holdings[:LIVE_LEADER_CONSTITUENT_LIMIT],
                )
                dated_holdings_symbols.add(leader_symbol)
            holdings_by_leader_and_date[(leader_symbol, checkpoint_date)] = normalized_snapshot
            constituent_symbols.update(str(row["symbol"]).upper() for row in normalized_snapshot.holdings)

    if constituent_symbols:
        start_date = common_dates[0]
        end_date = common_dates[-1]
        for symbol, monthly_bars in _load_live_constituent_bars(sorted(constituent_symbols), start_date, end_date, dataset_catalog).items():
            base_by_symbol_and_date[symbol] = {bar.date: bar for bar in monthly_bars}

    leader_internals: list[EtfLeaderInternalsObservation] = []
    observation_by_date = {observation.date: observation for observation in observations}
    for index in range(lookback_months, len(common_dates)):
        current_date = common_dates[index]
        observation = observation_by_date.get(current_date)
        if observation is None:
            continue
        normalized_snapshot = holdings_by_leader_and_date.get((observation.leader or "", current_date))
        holdings = normalized_snapshot.holdings if normalized_snapshot is not None else []
        internals_observation = _build_leader_internals_from_holdings(
            holdings=holdings,
            by_symbol_and_date=base_by_symbol_and_date,
            current_date=current_date,
            lookback_date=common_dates[index - lookback_months],
            leader_symbol=observation.leader,
        )
        if normalized_snapshot is not None:
            source_mode = "sample" if observation.leader in sample_fallback_symbols else "live-dated"
            internals_observation = internals_observation.model_copy(update={"source_mode": source_mode, "snapshot_date": normalized_snapshot.snapshot_date})
        leader_internals.append(internals_observation)
    leader_mode = "live-dated" if dated_holdings_symbols else "sample"
    if sample_fallback_symbols and dated_holdings_symbols:
        leader_mode = "mixed"
    return _LeaderInternalsBuildResult(
        observations=leader_internals,
        etf_internals_history=_build_live_etf_internals_history(universe, observations, by_symbol_and_date=base_by_symbol_and_date, common_dates=common_dates, lookback_months=lookback_months, dataset_catalog=dataset_catalog),
        status=EtfMomentumSourceStatus(
            price_history="live" if observations else "sample",
            leader_internals=leader_mode,
            holdings_snapshot_counts=holdings_snapshot_counts,
            dated_holdings_symbols=sorted(dated_holdings_symbols),
            sample_fallback_symbols=sorted(sample_fallback_symbols),
        ),
    )


def _load_live_constituent_bars(
    symbols: list[str],
    start_date: str,
    end_date: str,
    dataset_catalog: DatasetCatalog,
) -> dict[str, list[BarRecord]]:
    market_data = MarketDataService()
    bars_by_symbol: dict[str, list[BarRecord]] = {}
    for symbol in symbols:
        rows = market_data.get_historical_prices(symbol, start_date, end_date)
        monthly_bars = _rows_to_monthly_bars(rows)
        bars_by_symbol[symbol] = monthly_bars if monthly_bars else dataset_catalog.get_daily_bars(symbol)
    return bars_by_symbol


def _normalize_fmp_holdings(rows: list[dict[str, Any]]) -> list[dict[str, str | float]]:
    normalized: list[dict[str, str | float]] = []
    for row in rows:
        symbol = str(row.get("asset") or row.get("symbol") or "").upper()
        name = str(row.get("name") or symbol)
        weight_percentage = row.get("weightPercentage", row.get("weight"))
        if not symbol or weight_percentage is None:
            continue
        normalized.append(
            {
                "symbol": symbol,
                "name": name,
                "weight": float(weight_percentage) / 100,
            }
        )
    normalized.sort(key=lambda item: float(item["weight"]), reverse=True)
    return normalized


def _normalize_fmp_holdings_snapshot(rows: list[dict[str, Any]]) -> _NormalizedHoldingsSnapshot | None:
    normalized = _normalize_fmp_holdings(rows)
    if not normalized:
        return None
    snapshot_dates = sorted({str(row.get("updated") or "")[:10] for row in rows if row.get("updated")})
    snapshot_date = snapshot_dates[-1] if snapshot_dates else ""
    if not snapshot_date:
        return None
    return _NormalizedHoldingsSnapshot(snapshot_date=snapshot_date, holdings=normalized)


def _build_methodology(price_source_label: str, internals_mode: str) -> str:
    internals_description = (
        "Leader internals use dated FMP ETF holdings snapshots when available, trimmed to the top weighted constituents for bounded request volume."
        if internals_mode == "live"
        else "Leader internals use local sample ETF holdings snapshots, including dated sample changes for selected ETFs."
    )
    return (
        "Monthly ETF cross-sectional momentum prototype: rank the sector ETF universe by trailing price return over the selected lookback, "
        "hold the top-ranked sleeves equally, and rebalance monthly. "
        f"Price history source: {price_source_label}. {internals_description} "
        "Volume is surfaced as participation context, not as a core signal."
    )


def _rank_assets(symbols: list[str], by_symbol_and_date: Mapping[str, Mapping[str, BarRecord]], common_dates: list[str], index: int, lookback_months: int) -> list[_RankedAsset]:
    ranked: list[_RankedAsset] = []
    current_date = common_dates[index]
    lookback_date = common_dates[index - lookback_months]
    for symbol in symbols:
        current_bar = by_symbol_and_date[symbol][current_date]
        lookback_bar = by_symbol_and_date[symbol][lookback_date]
        trailing_return = (current_bar.close / lookback_bar.close) - 1
        volume_window = [by_symbol_and_date[symbol][common_dates[offset]].volume for offset in range(index - lookback_months + 1, index + 1)]
        average_volume = None
        finite_volumes = [float(value) for value in volume_window if value is not None]
        if finite_volumes:
            average_volume = sum(finite_volumes) / len(finite_volumes)
        ranked.append(_RankedAsset(symbol=symbol, score=trailing_return, trailing_return_pct=trailing_return * 100, average_volume=average_volume))
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def _build_leader_internals_from_holdings(
    holdings: list[dict[str, str | float]],
    by_symbol_and_date: Mapping[str, Mapping[str, BarRecord]],
    current_date: str,
    lookback_date: str,
    leader_symbol: str | None,
) -> EtfLeaderInternalsObservation:
    if leader_symbol is None:
        return EtfLeaderInternalsObservation(date=current_date, leader_symbol=None, source_mode="sample", snapshot_date=None, constituents=[])

    if not holdings:
        return EtfLeaderInternalsObservation(date=current_date, leader_symbol=leader_symbol, source_mode="sample", snapshot_date=None, constituents=[])

    constituents: list[EtfLeaderConstituent] = []
    for row in holdings:
        symbol = str(row["symbol"]).upper()
        name = str(row["name"])
        weight = float(row["weight"])
        current_bar = by_symbol_and_date.get(symbol, {}).get(current_date)
        lookback_bar = by_symbol_and_date.get(symbol, {}).get(lookback_date)
        trailing_return_pct = None
        weighted_contribution_pct = None
        if current_bar and lookback_bar:
            trailing_return_pct = ((current_bar.close / lookback_bar.close) - 1) * 100
            weighted_contribution_pct = trailing_return_pct * weight
        constituents.append(
            EtfLeaderConstituent(
                symbol=symbol,
                name=name,
                weight=weight,
                trailing_return_pct=round(trailing_return_pct, 2) if trailing_return_pct is not None else None,
                weighted_contribution_pct=round(weighted_contribution_pct, 2) if weighted_contribution_pct is not None else None,
            )
        )

    constituents.sort(key=lambda item: item.weighted_contribution_pct if item.weighted_contribution_pct is not None else float("-inf"), reverse=True)
    return EtfLeaderInternalsObservation(date=current_date, leader_symbol=leader_symbol, source_mode="sample", snapshot_date=None, constituents=constituents)


def _monthly_return(series_by_date: Mapping[str, BarRecord], current_date: str) -> float:
    dates = sorted(series_by_date)
    current_index = dates.index(current_date)
    if current_index == 0:
        return 0.0
    previous_date = dates[current_index - 1]
    current_close = series_by_date[current_date].close
    previous_close = series_by_date[previous_date].close
    return (current_close / previous_close) - 1


def _turnover(previous_weights: dict[str, float], current_weights: dict[str, float]) -> float:
    symbols = set(previous_weights) | set(current_weights)
    return sum(abs(current_weights.get(symbol, 0.0) - previous_weights.get(symbol, 0.0)) for symbol in symbols) / 2


def _participation_ratio(selected: list[_RankedAsset], ranked: list[_RankedAsset]) -> float:
    selected_volumes = [item.average_volume for item in selected if item.average_volume is not None]
    ranked_volumes = [item.average_volume for item in ranked if item.average_volume is not None]
    if not selected_volumes or not ranked_volumes:
        return 1.0
    return (sum(selected_volumes) / len(selected_volumes)) / (sum(ranked_volumes) / len(ranked_volumes))


def _apply_drawdowns(points: list[EtfMomentumPoint]) -> None:
    max_strategy = 0.0
    max_benchmark = 0.0
    for point in points:
        max_strategy = max(max_strategy, point.strategy_equity)
        max_benchmark = max(max_benchmark, point.benchmark_equity)
        point.strategy_drawdown_pct = ((point.strategy_equity / max_strategy) - 1) * 100 if max_strategy else 0.0
        point.benchmark_drawdown_pct = ((point.benchmark_equity / max_benchmark) - 1) * 100 if max_benchmark else 0.0


def _build_metrics(
    strategy_returns: list[float],
    benchmark_returns: list[float],
    turnover_values: list[float],
    participation_values: list[float],
    strategy_equity: float,
    benchmark_equity: float,
    equity_curve: list[EtfMomentumPoint],
) -> EtfMomentumMetrics:
    periods = len(strategy_returns)
    annualization = 12 / periods if periods else 0.0
    strategy_total_return = strategy_equity - 100.0
    benchmark_total_return = benchmark_equity - 100.0
    strategy_growth = (strategy_equity / 100.0) if strategy_equity > 0 else None
    annualized = ((strategy_growth ** annualization) - 1) * 100 if strategy_growth and periods else None
    strategy_drawdown = min((point.strategy_drawdown_pct or 0.0) for point in equity_curve) if equity_curve else None
    benchmark_drawdown = min((point.benchmark_drawdown_pct or 0.0) for point in equity_curve) if equity_curve else None
    win_rate = (sum(1 for value in strategy_returns if value > 0) / periods * 100) if periods else None
    average_turnover = (sum(turnover_values) / len(turnover_values) * 100) if turnover_values else None
    return EtfMomentumMetrics(
        total_return_pct=round(strategy_total_return, 2),
        benchmark_return_pct=round(benchmark_total_return, 2),
        excess_return_pct=round(strategy_total_return - benchmark_total_return, 2),
        annualized_return_pct=round(annualized, 2) if annualized is not None else None,
        max_drawdown_pct=round(strategy_drawdown, 2) if strategy_drawdown is not None else None,
        benchmark_max_drawdown_pct=round(benchmark_drawdown, 2) if benchmark_drawdown is not None else None,
        win_rate_pct=round(win_rate, 2) if win_rate is not None else None,
        average_turnover_pct=round(average_turnover, 2) if average_turnover is not None else None,
        average_volume_participation_ratio=round(sum(participation_values) / len(participation_values), 2) if participation_values else None,
    )
