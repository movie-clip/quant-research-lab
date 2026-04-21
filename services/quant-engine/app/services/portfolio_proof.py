from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Literal

from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.return_basis import (
    PortfolioProofBucketEvidence,
    PortfolioProofEvidenceBundle,
    PortfolioProofMetadata,
    PortfolioProofWitness,
)


PortfolioProofHistorySource = Literal["imported_replay", "synthetic_snapshot_history", "unavailable"]

VALUATION_BROKER_PROVEN = "broker_proven_mark_to_market_inputs"
VALUATION_RAW_VENDOR = "raw_vendor_price"
VALUATION_FORWARD_FILL = "forward_fill"
VALUATION_SNAPSHOT_FALLBACK = "snapshot_fallback"
VALUATION_OTHER_FALLBACK = "other_fallback_construction"
VALUATION_MIXED = "mixed_basis_construction"


def _bucket(
    *,
    positive_evidence: list[str],
    negative_evidence: list[str],
    disqualifiers: list[str],
    witnesses: list[PortfolioProofWitness] | None = None,
) -> PortfolioProofBucketEvidence:
    if disqualifiers:
        status = "disqualified"
    elif positive_evidence:
        status = "supported"
    else:
        status = "unavailable"
    return PortfolioProofBucketEvidence(
        status=status,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        disqualifiers=disqualifiers,
        witnesses=witnesses or [],
    )


def _witness(
    *,
    label: str,
    status: str,
    evidence: list[str],
    counts: dict[str, int] | None = None,
) -> PortfolioProofWitness:
    return PortfolioProofWitness(
        label=label,
        status=status,
        evidence=evidence,
        counts=counts or {},
    )


def _valuation_policy_witness() -> PortfolioProofWitness:
    return _witness(
        label="valuation_input_policy",
        status="explicit_withholding_contract",
        evidence=[
            f"proof_eligible:{VALUATION_BROKER_PROVEN}",
            f"replay_only:{VALUATION_RAW_VENDOR}",
            f"replay_only:{VALUATION_FORWARD_FILL}",
            "replay_only:synthetic_snapshot_history",
            f"replay_only:{VALUATION_SNAPSHOT_FALLBACK}",
            f"replay_only:{VALUATION_OTHER_FALLBACK}",
            f"replay_only:{VALUATION_MIXED}",
            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
        ],
        counts={"proof_eligible_input_types": 1, "replay_only_input_types": 6},
    )


def _observed_currencies(snapshot: ImportedPortfolioSnapshot) -> set[str]:
    currencies = {
        position.currency
        for position in snapshot.positions
        if position.currency
    }
    currencies.update(
        balance.currency
        for balance in snapshot.cash_balances
        if balance.currency
    )
    currencies.update(
        entry.currency
        for entry in snapshot.ledger_entries
        if entry.currency
    )
    return currencies


def _inferred_opening_symbols(snapshot: ImportedPortfolioSnapshot) -> list[str]:
    ending_positions = {position.symbol: position.quantity for position in snapshot.positions}
    buy_totals: defaultdict[str, float] = defaultdict(float)
    sell_totals: defaultdict[str, float] = defaultdict(float)
    for entry in snapshot.ledger_entries:
        if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
            buy_totals[entry.symbol] += entry.quantity
        elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
            sell_totals[entry.symbol] += entry.quantity

    starting_nav = snapshot.statement_totals.starting_nav if snapshot.statement_totals is not None else None
    if len(snapshot.statements) > 1 and (starting_nav is None or abs(starting_nav) <= 1e-9):
        return []

    inferred_symbols: list[str] = []
    for symbol in sorted(set(ending_positions) | set(buy_totals) | set(sell_totals)):
        opening_quantity = ending_positions.get(symbol, 0.0) + sell_totals[symbol] - buy_totals[symbol]
        if abs(opening_quantity) > 1e-9:
            inferred_symbols.append(symbol)
    return inferred_symbols


def _opening_state_witnesses(
    *,
    snapshot: ImportedPortfolioSnapshot,
    history_source: PortfolioProofHistorySource,
    inferred_opening_symbols: list[str],
) -> list[PortfolioProofWitness]:
    broker_starting_cash_balances = [balance for balance in snapshot.cash_balances if balance.starting_cash is not None]
    if broker_starting_cash_balances:
        cash_witness = _witness(
            label="opening_cash_state",
            status="broker_proven",
            evidence=["broker_cash_report_starting_cash_present"],
            counts={"currency_count": len(broker_starting_cash_balances)},
        )
    elif history_source == "synthetic_snapshot_history":
        cash_witness = _witness(
            label="opening_cash_state",
            status="unknown_inferred",
            evidence=["synthetic_snapshot_history_has_no_broker_opening_cash_state"],
        )
    else:
        cash_witness = _witness(
            label="opening_cash_state",
            status="unknown_inferred",
            evidence=["broker_opening_cash_state_not_present"],
        )

    if history_source == "synthetic_snapshot_history":
        position_witness = _witness(
            label="opening_positions_state",
            status="unknown_inferred",
            evidence=["opening_positions_derived_from_current_snapshot"],
        )
    elif inferred_opening_symbols:
        position_witness = _witness(
            label="opening_positions_state",
            status="unknown_inferred",
            evidence=["opening_positions_require_inference_from_ending_positions_and_trades"],
            counts={"inferred_symbol_count": len(inferred_opening_symbols)},
        )
    else:
        covered_symbol_count = len({position.symbol for position in snapshot.positions})
        position_witness = _witness(
            label="opening_positions_state",
            status="trade_window_covered",
            evidence=["opening_positions_covered_by_observed_trade_window"],
            counts={"covered_symbol_count": covered_symbol_count},
        )

    return [cash_witness, position_witness]


def _cash_flow_witnesses(snapshot: ImportedPortfolioSnapshot) -> tuple[list[PortfolioProofWitness], Counter[str]]:
    ledger = snapshot_to_ledger(snapshot)
    counts: Counter[str] = Counter(entry.cash_movement_classification for entry in ledger)
    explicit_income_and_expense_count = sum(
        counts[key]
        for key in (
            "broker_explicit_dividend",
            "broker_explicit_interest",
            "broker_explicit_fee",
            "broker_explicit_tax",
        )
    )
    unknown_entry_types = sorted(
        {
            entry.entry_type.lower()
            for entry in ledger
            if entry.cash_movement_classification == "unknown"
        }
    )
    witnesses = [
        _witness(
            label="cash_flow_classification",
            status="broker_proven" if counts["external_capital_flow"] else "not_observed",
            evidence=["broker_transfer_section_line"] if counts["external_capital_flow"] else ["no_broker_proven_external_capital_flow_entries_observed"],
            counts={"external_capital_flow": counts["external_capital_flow"]},
        ),
        _witness(
            label="internal_trading_flow_classification",
            status="broker_proven" if counts["internal_trading_flow"] else "not_observed",
            evidence=["broker_trade_ledger_line"] if counts["internal_trading_flow"] else ["no_internal_trading_cash_flows_observed"],
            counts={"internal_trading_flow": counts["internal_trading_flow"]},
        ),
        _witness(
            label="broker_explicit_income_expense_classification",
            status="broker_proven" if explicit_income_and_expense_count else "not_observed",
            evidence=(
                ["broker_explicit_income_or_expense_section_line"]
                if explicit_income_and_expense_count
                else ["no_broker_explicit_income_or_expense_cash_flows_observed"]
            ),
            counts={
                "broker_explicit_dividend": counts["broker_explicit_dividend"],
                "broker_explicit_interest": counts["broker_explicit_interest"],
                "broker_explicit_fee": counts["broker_explicit_fee"],
                "broker_explicit_tax": counts["broker_explicit_tax"],
            },
        ),
        _witness(
            label="unknown_cash_flow_classification",
            status="unknown_inferred" if counts["unknown"] else "none_observed",
            evidence=(
                ["unknown_cash_flow_entry_types:" + ",".join(unknown_entry_types)]
                if unknown_entry_types
                else ["no_unknown_cash_flow_entries_observed"]
            ),
            counts={"unknown": counts["unknown"]},
        ),
    ]
    return witnesses, counts


def _forward_filled_symbols(price_histories: dict[str, list[dict]], valuation_dates: list[str]) -> list[str]:
    if not valuation_dates:
        return []

    forward_filled: list[str] = []
    for symbol, rows in price_histories.items():
        observed_dates = {row["date"] for row in rows if isinstance(row.get("date"), str)}
        if not observed_dates:
            continue
        first_observed = min(observed_dates)
        if any(date >= first_observed and date not in observed_dates for date in valuation_dates):
            forward_filled.append(symbol)
    return sorted(forward_filled)


def _fallback_price_symbols(snapshot: ImportedPortfolioSnapshot, price_histories: dict[str, list[dict]]) -> list[str]:
    symbols: list[str] = []
    for position in snapshot.positions:
        if not price_histories.get(position.symbol) and position.close_price is not None:
            symbols.append(position.symbol)
    return sorted(set(symbols))


def _ordered_trade_entries(snapshot: ImportedPortfolioSnapshot):
    canonical_ledger = snapshot_to_ledger(snapshot)
    return sorted(
        canonical_ledger,
        key=lambda item: (item.date, item.symbol or "", item.entry_type),
    )


def _valued_symbols_by_date(snapshot: ImportedPortfolioSnapshot, valuation_dates: list[str]) -> dict[str, list[str]]:
    if not valuation_dates:
        return {}

    trade_entries = _ordered_trade_entries(snapshot)
    ending_positions = {position.symbol: position.quantity for position in snapshot.positions}
    buy_totals: defaultdict[str, float] = defaultdict(float)
    sell_totals: defaultdict[str, float] = defaultdict(float)
    for entry in trade_entries:
        if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
            buy_totals[entry.symbol] += entry.quantity
        elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
            sell_totals[entry.symbol] += entry.quantity

    opening_positions: defaultdict[str, float] = defaultdict(float)
    initial_portfolio_value = (
        snapshot.statement_totals.starting_nav
        if snapshot.statement_totals is not None and snapshot.statement_totals.starting_nav is not None
        else 0.0
    )
    if len(snapshot.statements) > 1 and abs(initial_portfolio_value) <= 1e-9:
        opening_positions = defaultdict(float)
    else:
        for symbol in set(ending_positions) | set(buy_totals) | set(sell_totals):
            opening_positions[symbol] = ending_positions.get(symbol, 0.0) + sell_totals[symbol] - buy_totals[symbol]

    valued_symbols: dict[str, list[str]] = {}
    entry_index = 0
    running_positions = defaultdict(float, opening_positions)
    for day_str in valuation_dates:
        day = date.fromisoformat(day_str)
        while entry_index < len(trade_entries) and trade_entries[entry_index].date <= day:
            entry = trade_entries[entry_index]
            if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
                running_positions[entry.symbol] += entry.quantity
            elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
                running_positions[entry.symbol] -= entry.quantity
            entry_index += 1

        valued_symbols[day_str] = sorted(
            symbol for symbol, quantity in running_positions.items() if abs(quantity) > 1e-9
        )

    return valued_symbols


def _classify_row_source(row: dict) -> str:
    markers = {
        row.get("basis"),
        row.get("valuation_basis"),
        row.get("valuation_source"),
        row.get("source"),
        row.get("origin"),
    }
    if {marker for marker in markers if isinstance(marker, str)} & {
        "broker_mark_to_market",
        "broker_proven_mark_to_market",
        "broker_statement_mark",
    }:
        return VALUATION_BROKER_PROVEN
    return VALUATION_RAW_VENDOR


def _classify_symbol_valuation_source(
    *,
    symbol: str,
    valuation_date: str,
    price_histories: dict[str, list[dict]],
    fallback_prices: dict[str, float | None],
) -> str:
    rows = sorted(
        [row for row in price_histories.get(symbol, []) if isinstance(row.get("date"), str)],
        key=lambda row: row["date"],
    )
    row_lookup = {row["date"]: row for row in rows}
    if valuation_date in row_lookup:
        return _classify_row_source(row_lookup[valuation_date])

    observed_dates = sorted(row_lookup)
    if observed_dates and any(observed_date < valuation_date for observed_date in observed_dates):
        return VALUATION_FORWARD_FILL
    if observed_dates:
        return VALUATION_OTHER_FALLBACK
    if fallback_prices.get(symbol) is not None:
        return VALUATION_SNAPSHOT_FALLBACK
    return VALUATION_OTHER_FALLBACK


def _build_valuation_witnesses(
    *,
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    history_source: PortfolioProofHistorySource,
) -> tuple[list[PortfolioProofWitness], set[str], set[str]]:
    witnesses = [
        _valuation_policy_witness(),
        _witness(
            label="valuation_history_construction",
            status=history_source,
            evidence=(
                ["valuation_states_replayed_from_imported_broker_activity"]
                if history_source == "imported_replay"
                else ["valuation_states_constructed_from_synthetic_snapshot_history"]
            ),
            counts={"valuation_date_count": len(valuation_dates)},
        ),
    ]
    if not valuation_dates:
        return witnesses, set(), set()

    valued_symbols_by_date = _valued_symbols_by_date(snapshot, valuation_dates)
    fallback_prices = {position.symbol: position.close_price for position in snapshot.positions}
    observed_sources: set[str] = set()
    observed_date_bases: set[str] = set()

    window_start: str | None = None
    window_end: str | None = None
    window_basis: str | None = None
    window_counts: Counter[str] = Counter()
    window_valuation_date_count = 0
    window_valued_symbol_count = 0

    def flush_window() -> None:
        nonlocal window_start, window_end, window_basis, window_counts, window_valuation_date_count, window_valued_symbol_count
        if window_start is None or window_end is None or window_basis is None:
            return
        window_label = (
            f"valuation_window_basis:{window_start}"
            if window_start == window_end
            else f"valuation_window_basis:{window_start}:{window_end}"
        )
        evidence = [
            (
                f"valuation_date:{window_start}"
                if window_start == window_end
                else f"valuation_window_dates:{window_start}->{window_end}"
            )
        ]
        if window_basis == VALUATION_MIXED:
            evidence.append(
                "mixed_basis_inputs:" + ",".join(sorted(source for source, count in window_counts.items() if count > 0))
            )
        else:
            evidence.append(f"valuation_window_uses:{window_basis}")
        witnesses.append(
            _witness(
                label=window_label,
                status=window_basis,
                evidence=evidence,
                counts={
                    "valuation_date_count": window_valuation_date_count,
                    "valued_symbol_count": window_valued_symbol_count,
                    **{key: value for key, value in sorted(window_counts.items())},
                },
            )
        )
        window_start = None
        window_end = None
        window_basis = None
        window_counts = Counter()
        window_valuation_date_count = 0
        window_valued_symbol_count = 0

    for day_str in valuation_dates:
        valued_symbols = valued_symbols_by_date.get(day_str, [])
        if not valued_symbols:
            flush_window()
            continue

        source_counts = Counter(
            _classify_symbol_valuation_source(
                symbol=symbol,
                valuation_date=day_str,
                price_histories=price_histories,
                fallback_prices=fallback_prices,
            )
            for symbol in valued_symbols
        )
        observed_sources.update(source_counts)
        date_basis = next(iter(source_counts)) if len(source_counts) == 1 else VALUATION_MIXED
        observed_date_bases.add(date_basis)

        if window_basis == date_basis:
            window_end = day_str
            window_counts.update(source_counts)
            window_valuation_date_count += 1
            window_valued_symbol_count += len(valued_symbols)
            continue

        flush_window()
        window_start = day_str
        window_end = day_str
        window_basis = date_basis
        window_counts = Counter(source_counts)
        window_valuation_date_count = 1
        window_valued_symbol_count = len(valued_symbols)

    flush_window()
    return witnesses, observed_sources, observed_date_bases


def build_portfolio_proof_metadata(
    *,
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
    history_source: PortfolioProofHistorySource,
) -> PortfolioProofMetadata:
    if history_source == "unavailable":
        evidence = PortfolioProofEvidenceBundle(
            opening_state_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            valuation_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            cash_flow_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            fx_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            corporate_action_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            terminal_reconciliation_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            calendar_coverage_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
        )
        return PortfolioProofMetadata(
            proof_system="portfolio_verified_total_return_v1",
            portfolio_path="unavailable",
            verification_status="unavailable",
            output_status="unavailable",
            verified_total_return_emitted=False,
            benchmark_proof_independent=True,
            disqualifiers=["portfolio_history_unavailable"],
            evidence=evidence,
        )

    observed_currencies = _observed_currencies(snapshot)
    base_currency = snapshot.statement.base_currency or "USD"
    non_base_currencies = sorted(currency for currency in observed_currencies if currency != base_currency)
    inferred_opening_symbols = _inferred_opening_symbols(snapshot)
    opening_witnesses = _opening_state_witnesses(
        snapshot=snapshot,
        history_source=history_source,
        inferred_opening_symbols=inferred_opening_symbols,
    )
    forward_filled_symbols = _forward_filled_symbols(price_histories, valuation_dates)
    fallback_symbols = _fallback_price_symbols(snapshot, price_histories)
    cash_flow_witnesses, cash_flow_counts = _cash_flow_witnesses(snapshot)
    valuation_witnesses, valuation_sources, valuation_date_bases = _build_valuation_witnesses(
        snapshot=snapshot,
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        history_source=history_source,
    )
    terminal_force_reconciliation_present = bool(
        snapshot.statement_totals is not None
        and (
            snapshot.statement_totals.ending_nav is not None
            or snapshot.statement_totals.cash_total is not None
        )
    )

    opening_positive = [
        "broker_ledger_entries_available" if snapshot.ledger_entries else "no_broker_ledger_entries_available",
    ]
    opening_negative: list[str] = []
    opening_disqualifiers: list[str] = []
    if history_source == "synthetic_snapshot_history":
        opening_negative.append("opening_state_derived_from_current_snapshot")
        opening_disqualifiers.append("synthetic_snapshot_opening_state")
    elif inferred_opening_symbols:
        opening_negative.append("opening_state_inferred_from_ending_positions_and_trades")
        opening_disqualifiers.append("inferred_opening_state")
    else:
        opening_positive.append("opening_state_covered_by_observed_trade_window")
    if any(balance.starting_cash is not None for balance in snapshot.cash_balances):
        opening_positive.append("broker_proven_opening_cash_state_available")

    valuation_positive = [
        "valuation_dates_available" if valuation_dates else "valuation_dates_missing",
        "position_price_histories_loaded" if price_histories else "position_price_histories_missing",
    ]
    if VALUATION_BROKER_PROVEN in valuation_sources:
        valuation_positive.append("broker_proven_mark_to_market_inputs_observed")

    valuation_negative: list[str] = []
    valuation_disqualifiers: list[str] = []
    if VALUATION_RAW_VENDOR in valuation_sources:
        valuation_negative.append("vendor_raw_price_used_for_valuation")
        valuation_disqualifiers.append("raw_price_used_for_valuation")
    if history_source == "synthetic_snapshot_history":
        valuation_negative.append("valuation_path_is_synthetic_snapshot_history")
        valuation_disqualifiers.append("synthetic_snapshot_history")
    if VALUATION_FORWARD_FILL in valuation_sources or forward_filled_symbols:
        valuation_negative.append("position_prices_forward_filled")
        valuation_disqualifiers.append("forward_filled_prices")
    if VALUATION_SNAPSHOT_FALLBACK in valuation_sources or fallback_symbols:
        valuation_negative.append("snapshot_close_price_fallback_used")
        valuation_disqualifiers.append("snapshot_close_price_fallback")
    if VALUATION_OTHER_FALLBACK in valuation_sources:
        valuation_negative.append("other_fallback_valuation_construction_used")
        valuation_disqualifiers.append("other_fallback_valuation_construction")
    if VALUATION_MIXED in valuation_date_bases:
        valuation_negative.append("mixed_basis_valuation_construction_used")
        valuation_disqualifiers.append("mixed_basis_valuation")

    cash_flow_positive = [
        "broker_ledger_entries_available" if snapshot.ledger_entries else "no_broker_ledger_entries_available",
    ]
    cash_flow_negative: list[str] = []
    cash_flow_disqualifiers: list[str] = []
    if history_source == "synthetic_snapshot_history":
        cash_flow_negative.append("synthetic_snapshot_history_has_no_external_flow_replay")
        cash_flow_disqualifiers.append("synthetic_snapshot_history")
    elif not snapshot.ledger_entries:
        cash_flow_negative.append("broker_cash_movement_ledger_not_available")
        cash_flow_disqualifiers.append("cash_flow_broker_evidence_missing")
    elif cash_flow_counts["unknown"] > 0:
        cash_flow_negative.append("unknown_cash_movement_types_present")
        cash_flow_disqualifiers.append("unknown_cash_movements")
    else:
        cash_flow_positive.append("cash_movement_entries_classified_with_broker_native_evidence")

    fx_positive: list[str] = []
    fx_negative: list[str] = []
    fx_disqualifiers: list[str] = []
    if non_base_currencies:
        fx_positive.append("non_base_currency_exposure_observed")
        if not fx_history:
            fx_negative.append("historical_fx_series_missing")
            fx_disqualifiers.append("missing_fx_history")
    else:
        fx_positive.append("all_observed_statement_currencies_match_base_currency")

    corporate_action_positive = ["broker_ledger_entries_available" if snapshot.ledger_entries else "no_broker_ledger_entries_available"]
    corporate_action_negative = ["corporate_action_proof_not_available"]
    corporate_action_disqualifiers = ["corporate_action_proof_missing"]

    terminal_positive: list[str] = []
    terminal_negative: list[str] = []
    terminal_disqualifiers: list[str] = []
    if terminal_force_reconciliation_present:
        terminal_negative.append("terminal_state_can_be_force_reconciled_to_statement_totals")
        terminal_disqualifiers.append("terminal_force_reconciliation_present")
    else:
        terminal_positive.append("terminal_force_reconciliation_not_present")

    calendar_positive: list[str] = []
    calendar_negative = []
    calendar_disqualifiers = []
    if valuation_dates:
        calendar_positive.append("valuation_window_dates_available")
    if valuation_dates == sorted(set(valuation_dates)) and valuation_dates:
        calendar_positive.append("valuation_dates_are_sorted_and_unique")
    calendar_negative.append("valuation_calendar_is_derived_from_benchmark_history")
    calendar_disqualifiers.append("calendar_coverage_not_broker_proven")
    if forward_filled_symbols:
        calendar_negative.append("calendar_coverage_requires_forward_fill")
        calendar_disqualifiers.append("calendar_coverage_has_gaps")

    evidence = PortfolioProofEvidenceBundle(
        opening_state_basis=_bucket(
            positive_evidence=opening_positive,
            negative_evidence=opening_negative,
            disqualifiers=sorted(set(opening_disqualifiers)),
            witnesses=opening_witnesses,
        ),
        valuation_basis=_bucket(
            positive_evidence=valuation_positive,
            negative_evidence=valuation_negative,
            disqualifiers=sorted(set(valuation_disqualifiers)),
            witnesses=valuation_witnesses,
        ),
        cash_flow_basis=_bucket(
            positive_evidence=cash_flow_positive,
            negative_evidence=cash_flow_negative,
            disqualifiers=sorted(set(cash_flow_disqualifiers)),
            witnesses=cash_flow_witnesses,
        ),
        fx_basis=_bucket(
            positive_evidence=fx_positive,
            negative_evidence=fx_negative,
            disqualifiers=sorted(set(fx_disqualifiers)),
        ),
        corporate_action_basis=_bucket(
            positive_evidence=corporate_action_positive,
            negative_evidence=corporate_action_negative,
            disqualifiers=sorted(set(corporate_action_disqualifiers)),
        ),
        terminal_reconciliation_basis=_bucket(
            positive_evidence=terminal_positive,
            negative_evidence=terminal_negative,
            disqualifiers=sorted(set(terminal_disqualifiers)),
        ),
        calendar_coverage_basis=_bucket(
            positive_evidence=calendar_positive,
            negative_evidence=calendar_negative,
            disqualifiers=sorted(set(calendar_disqualifiers)),
        ),
    )
    disqualifiers = sorted(
        {
            *evidence.opening_state_basis.disqualifiers,
            *evidence.valuation_basis.disqualifiers,
            *evidence.cash_flow_basis.disqualifiers,
            *evidence.fx_basis.disqualifiers,
            *evidence.corporate_action_basis.disqualifiers,
            *evidence.terminal_reconciliation_basis.disqualifiers,
            *evidence.calendar_coverage_basis.disqualifiers,
            "portfolio_verified_total_return_withheld",
        }
    )
    return PortfolioProofMetadata(
        proof_system="portfolio_verified_total_return_v1",
        portfolio_path="withheld",
        verification_status="unverified",
        output_status="withheld",
        verified_total_return_emitted=False,
        benchmark_proof_independent=True,
        disqualifiers=disqualifiers,
        evidence=evidence,
    )


def build_unavailable_portfolio_proof_metadata(reason: str = "portfolio_history_unavailable") -> PortfolioProofMetadata:
    evidence = PortfolioProofEvidenceBundle(
        opening_state_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        valuation_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        cash_flow_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        fx_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        corporate_action_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        terminal_reconciliation_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
        calendar_coverage_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], witnesses=[]),
    )
    return PortfolioProofMetadata(
        proof_system="portfolio_verified_total_return_v1",
        portfolio_path="unavailable",
        verification_status="unavailable",
        output_status="unavailable",
        verified_total_return_emitted=False,
        benchmark_proof_independent=True,
        disqualifiers=[reason],
        evidence=evidence,
    )
