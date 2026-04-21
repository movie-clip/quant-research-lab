from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Literal, cast

from app.domain.ledger import snapshot_to_ledger
from app.engine.portfolio_state import PortfolioStateEngine
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.return_basis import (
    PortfolioCorporateActionBasisEvidence,
    PortfolioCorporateActionBasisPolicy,
    PortfolioProofAdmissionBlockingReason,
    PortfolioProofAdmissionBucketDecision,
    PortfolioProofAdmissionDecision,
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
PORTFOLIO_ADMISSION_GOVERNOR = "portfolio_proof_admission_governor_v1"


def _bucket(
    *,
    positive_evidence: list[str],
    negative_evidence: list[str],
    disqualifiers: list[str],
    hard_disqualifiers: list[str] | None = None,
    witnesses: list[PortfolioProofWitness] | None = None,
) -> PortfolioProofBucketEvidence:
    resolved_hard_disqualifiers = sorted(set(hard_disqualifiers or []))
    if disqualifiers or resolved_hard_disqualifiers:
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
        hard_disqualifiers=resolved_hard_disqualifiers,
        witnesses=witnesses or [],
    )


def _corporate_action_bucket(
    *,
    policy: PortfolioCorporateActionBasisPolicy,
    positive_evidence: list[str],
    negative_evidence: list[str],
    disqualifiers: list[str],
    hard_disqualifiers: list[str] | None = None,
    witnesses: list[PortfolioProofWitness] | None = None,
) -> PortfolioCorporateActionBasisEvidence:
    resolved_hard_disqualifiers = sorted(set(hard_disqualifiers or []))
    if disqualifiers or resolved_hard_disqualifiers:
        status = "disqualified"
    elif positive_evidence:
        status = "supported"
    else:
        status = "unavailable"
    return PortfolioCorporateActionBasisEvidence(
        status=status,
        policy=policy,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        disqualifiers=disqualifiers,
        hard_disqualifiers=resolved_hard_disqualifiers,
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
    currencies.update(
        statement.base_currency
        for statement in snapshot.statements
        if statement.base_currency
    )
    if snapshot.statement.base_currency:
        currencies.add(snapshot.statement.base_currency)
    return currencies


def _extract_fx_rates(fx_history: Any) -> dict[str, float]:
    rates: dict[str, float] = {}
    if not isinstance(fx_history, dict):
        return rates

    explicit_rates = fx_history.get("rates")
    if isinstance(explicit_rates, dict):
        for key, value in explicit_rates.items():
            if isinstance(key, str) and isinstance(value, (int, float)):
                rates[key] = float(value)
    elif all(isinstance(key, str) and isinstance(value, (int, float)) for key, value in fx_history.items()):
        for key, value in fx_history.items():
            rates[key] = float(value)

    series = fx_history.get("series")
    if isinstance(series, dict):
        for pair, rows in series.items():
            if not isinstance(pair, str) or not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                day = row.get("date")
                rate = row.get("rate", row.get("price", row.get("fx_rate")))
                if isinstance(day, str) and isinstance(rate, (int, float)):
                    rates.setdefault(f"{pair}:{day}", float(rate))

    return rates


def _extract_fx_series(fx_history: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(fx_history, dict):
        return {}
    series = fx_history.get("series")
    if not isinstance(series, dict):
        return {}

    normalized: dict[str, list[dict[str, Any]]] = {}
    for pair, rows in series.items():
        if not isinstance(pair, str) or not isinstance(rows, list):
            continue
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                normalized_rows.append({**row, "pair": row.get("pair") or pair})
        normalized[pair] = normalized_rows
    return normalized


def _first_valuation_date_on_or_after(valuation_dates: list[str], target: str) -> str | None:
    for valuation_date in valuation_dates:
        if valuation_date >= target:
            return valuation_date
    return None


def _required_fx_pairs_by_date(
    *,
    snapshot: ImportedPortfolioSnapshot,
    valuation_dates: list[str],
    base_currency: str,
) -> dict[str, set[str]]:
    if not valuation_dates:
        return {}

    required: defaultdict[str, set[str]] = defaultdict(set)
    valued_symbols_by_date = _valued_symbols_by_date(snapshot, valuation_dates)
    instrument_currency = {position.symbol: position.currency for position in snapshot.positions}
    for day_str, valued_symbols in valued_symbols_by_date.items():
        for symbol in valued_symbols:
            currency = instrument_currency.get(symbol)
            if currency and currency != base_currency:
                required[f"{currency}{base_currency}"].add(day_str)

    for entry in _ordered_trade_entries(snapshot):
        if entry.cash_currency == base_currency:
            continue
        applied_on = _first_valuation_date_on_or_after(valuation_dates, entry.date.isoformat())
        if applied_on is not None:
            required[f"{entry.cash_currency}{base_currency}"].add(applied_on)

    return {pair: dates for pair, dates in required.items() if dates}


def _fx_row_provenance_signature(row: dict[str, Any]) -> str | None:
    if isinstance(row.get("provenance"), str) and row["provenance"].strip():
        return row["provenance"].strip()

    parts = [
        str(row[key]).strip()
        for key in ("vendor", "endpoint", "source", "origin", "provider")
        if isinstance(row.get(key), str) and str(row[key]).strip()
    ]
    if parts:
        return "|".join(parts)
    return None


def _build_fx_witnesses(
    *,
    snapshot: ImportedPortfolioSnapshot,
    valuation_dates: list[str],
    fx_history: Any,
) -> tuple[list[PortfolioProofWitness], list[str], list[str], list[str], list[str]]:
    witnesses: list[PortfolioProofWitness] = []
    fx_positive: list[str] = []
    fx_negative: list[str] = []
    fx_disqualifiers: list[str] = []
    fx_hard_disqualifiers: list[str] = []

    base_currency = snapshot.statement.base_currency
    observed_currencies = _observed_currencies(snapshot)
    cash_currencies = {balance.currency for balance in snapshot.cash_balances if balance.currency}
    ledger_currencies = {entry.currency for entry in snapshot.ledger_entries if entry.currency}
    position_currencies = {position.currency for position in snapshot.positions if position.currency}
    statement_currencies = {statement.base_currency for statement in snapshot.statements if statement.base_currency}
    if snapshot.statement.base_currency:
        statement_currencies.add(snapshot.statement.base_currency)

    if base_currency:
        witnesses.append(
            _witness(
                label="fx_base_currency_state",
                status="broker_proven",
                evidence=[f"accepted_source:broker_statement_base_currency:{base_currency}"],
            )
        )
    else:
        witnesses.append(
            _witness(
                label="fx_base_currency_state",
                status="missing_broker_evidence",
                evidence=["accepted_source_missing:broker_statement_base_currency"],
            )
        )
        fx_negative.append("broker_statement_base_currency_missing")
        fx_disqualifiers.append("missing_base_currency")
        fx_hard_disqualifiers.append("missing_base_currency")
        return (
            witnesses,
            fx_positive,
            fx_negative,
            sorted(set(fx_disqualifiers)),
            sorted(set(fx_hard_disqualifiers)),
        )

    non_base_currencies = sorted(currency for currency in observed_currencies if currency != base_currency)
    witnesses.append(
        _witness(
            label="fx_currency_observation_scope",
            status="observed_currency_scope",
            evidence=[
                f"observed_statement_currencies:{','.join(sorted(statement_currencies)) or 'none'}",
                f"observed_cash_currencies:{','.join(sorted(cash_currencies)) or 'none'}",
                f"observed_ledger_currencies:{','.join(sorted(ledger_currencies)) or 'none'}",
                f"observed_position_currencies:{','.join(sorted(position_currencies)) or 'none'}",
            ],
            counts={
                "statement_currency_count": len(statement_currencies),
                "cash_currency_count": len(cash_currencies),
                "ledger_currency_count": len(ledger_currencies),
                "position_currency_count": len(position_currencies),
                "observed_currency_count": len(observed_currencies),
            },
        )
    )

    if not non_base_currencies:
        fx_positive.append("all_observed_statement_currencies_match_base_currency")
        witnesses.append(
            _witness(
                label="fx_translation_requirement",
                status="identity_case_supported",
                evidence=[f"all_observed_currencies_equal_base:{base_currency}"],
                counts={"observed_currency_count": len(observed_currencies)},
            )
        )
        return witnesses, fx_positive, fx_negative, [], []

    required_fx_pairs_by_date = _required_fx_pairs_by_date(
        snapshot=snapshot,
        valuation_dates=valuation_dates,
        base_currency=base_currency,
    )
    required_pair_dates = sorted(
        f"{pair}@{day_str}"
        for pair, dates in required_fx_pairs_by_date.items()
        for day_str in sorted(dates)
    )
    fx_positive.append("non_base_currency_exposure_observed")
    witnesses.append(
        _witness(
            label="fx_translation_requirement",
            status="dated_fx_series_required",
            evidence=[
                "non_base_currency_conversion_required_for_portfolio_replay",
                f"required_non_base_pairs:{','.join(sorted(required_fx_pairs_by_date)) or 'none'}",
            ],
            counts={
                "required_pair_count": len(required_fx_pairs_by_date),
                "required_pair_date_count": len(required_pair_dates),
            },
        )
    )

    if not required_pair_dates:
        unresolved_pairs = sorted({f"{currency}{base_currency}@unresolved_date" for currency in non_base_currencies})
        fx_negative.append("historical_fx_series_missing_required_pair_dates")
        fx_disqualifiers.append("missing_pair_date_coverage")
        fx_hard_disqualifiers.append("missing_pair_date_coverage")
        witnesses.append(
            _witness(
                label="fx_pair_date_coverage",
                status="missing_pair_date_coverage",
                evidence=["missing_pair_dates:" + ",".join(unresolved_pairs)],
                counts={"missing_pair_date_count": len(unresolved_pairs)},
            )
        )
        return (
            witnesses,
            fx_positive,
            fx_negative,
            sorted(set(fx_disqualifiers)),
            sorted(set(fx_hard_disqualifiers)),
        )

    fx_series = _extract_fx_series(fx_history)
    row_lookup: dict[str, dict[str, dict[str, Any]]] = {}
    provenance_signatures: set[str] = set()
    missing_pair_dates: list[str] = []
    inferred_pair_dates: list[str] = []
    fallback_pair_dates: list[str] = []
    stale_pair_dates: list[str] = []
    forward_filled_pair_dates: list[str] = []
    nearest_date_pair_dates: list[str] = []
    stitched_pair_dates: list[str] = []
    inverse_pair_dates: list[str] = []
    mixed_pair_dates: list[str] = []

    for pair, rows in fx_series.items():
        row_lookup[pair] = {}
        for row in rows:
            day = row.get("date")
            if not isinstance(day, str):
                continue
            row_lookup[pair][day] = row

    for pair, dates in sorted(required_fx_pairs_by_date.items()):
        for day_str in sorted(dates):
            row = row_lookup.get(pair, {}).get(day_str)
            if row is None:
                missing_pair_dates.append(f"{pair}@{day_str}")
                continue

            provenance_signature = _fx_row_provenance_signature(row)
            if provenance_signature is None or bool(row.get("inferred")) or bool(row.get("translation_inferred")):
                inferred_pair_dates.append(f"{pair}@{day_str}")
            else:
                provenance_signatures.add(provenance_signature)

            if bool(row.get("fallback_used")) or bool(row.get("fallback")):
                fallback_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("stale")) or bool(row.get("stale_rate")):
                stale_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("forward_filled")) or bool(row.get("forward_fill")):
                forward_filled_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("nearest_date")) or row.get("construction") == "nearest_date":
                nearest_date_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("stitched_source")) or row.get("construction") == "stitched_source":
                stitched_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("inverse_derived")) or row.get("construction") == "inverse_derived":
                inverse_pair_dates.append(f"{pair}@{day_str}")
            if bool(row.get("mixed_source")):
                mixed_pair_dates.append(f"{pair}@{day_str}")

    if len(provenance_signatures) > 1:
        mixed_pair_dates = sorted(set([*mixed_pair_dates, *required_pair_dates]))

    if missing_pair_dates:
        fx_negative.append("historical_fx_series_missing_required_pair_dates")
        fx_disqualifiers.append("missing_pair_date_coverage")
        fx_hard_disqualifiers.append("missing_pair_date_coverage")
        witnesses.append(
            _witness(
                label="fx_pair_date_coverage",
                status="missing_pair_date_coverage",
                evidence=["missing_pair_dates:" + ",".join(missing_pair_dates)],
                counts={"missing_pair_date_count": len(missing_pair_dates)},
            )
        )
    else:
        fx_positive.append("dated_provenance_backed_fx_series_cover_all_required_conversions")
        witnesses.append(
            _witness(
                label="fx_pair_date_coverage",
                status="full_pair_date_coverage",
                evidence=["covered_pair_dates:" + ",".join(required_pair_dates)],
                counts={"covered_pair_date_count": len(required_pair_dates)},
            )
        )

    if inferred_pair_dates:
        fx_negative.append("inferred_translation_present")
        fx_disqualifiers.append("inferred_translation")
        fx_hard_disqualifiers.append("inferred_translation")
        witnesses.append(
            _witness(
                label="fx_translation_provenance",
                status="inferred_translation",
                evidence=["inferred_pair_dates:" + ",".join(sorted(set(inferred_pair_dates)))],
                counts={"inferred_pair_date_count": len(sorted(set(inferred_pair_dates)))},
            )
        )
    elif required_pair_dates:
        witnesses.append(
            _witness(
                label="fx_translation_provenance",
                status="provenance_backed_series",
                evidence=["fx_series_are_dated_and_provenance_backed"],
                counts={"provenance_signature_count": len(provenance_signatures)},
            )
        )

    for label, pair_dates, negative, disqualifier in (
        ("fx_fallback_policy", fallback_pair_dates, "fallback_fx_used", "fallback_fx_used"),
        ("fx_staleness_policy", stale_pair_dates, "stale_fx_used", "stale_fx_used"),
        ("fx_forward_fill_policy", forward_filled_pair_dates, "forward_filled_fx_used", "forward_filled_fx_used"),
        ("fx_nearest_date_policy", nearest_date_pair_dates, "nearest_date_fx_used", "nearest_date_fx_used"),
        ("fx_stitched_source_policy", stitched_pair_dates, "stitched_source_fx_used", "stitched_source_fx_used"),
        ("fx_inverse_derivation_policy", inverse_pair_dates, "inverse_derived_fx_used", "inverse_derived_fx_used"),
    ):
        if not pair_dates:
            continue
        fx_negative.append(negative)
        fx_disqualifiers.append(disqualifier)
        fx_hard_disqualifiers.append(disqualifier)
        witnesses.append(
            _witness(
                label=label,
                status=disqualifier,
                evidence=[f"affected_pair_dates:{','.join(sorted(set(pair_dates)))}"],
                counts={"affected_pair_date_count": len(sorted(set(pair_dates)))},
            )
        )

    if mixed_pair_dates:
        fx_negative.append("mixed_source_fx_present")
        fx_disqualifiers.append("mixed_source_fx")
        fx_hard_disqualifiers.append("mixed_source_fx")
        witnesses.append(
            _witness(
                label="fx_source_consistency",
                status="mixed_source_fx",
                evidence=["mixed_source_pair_dates:" + ",".join(sorted(set(mixed_pair_dates)))],
                counts={
                    "mixed_pair_date_count": len(sorted(set(mixed_pair_dates))),
                    "provenance_signature_count": len(provenance_signatures),
                },
            )
        )
    elif required_pair_dates:
        witnesses.append(
            _witness(
                label="fx_source_consistency",
                status="single_source_fx",
                evidence=["single_provenance_backed_source_used_for_required_fx_conversions"],
                counts={"provenance_signature_count": len(provenance_signatures)},
            )
        )

    return (
        witnesses,
        fx_positive,
        fx_negative,
        sorted(set(fx_disqualifiers)),
        sorted(set(fx_hard_disqualifiers)),
    )


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
) -> tuple[
    list[PortfolioProofWitness],
    Literal["opening_state_verified", "opening_state_unverified"],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    broker_starting_cash_balances = [balance for balance in snapshot.cash_balances if balance.starting_cash is not None]
    statement_windows = _statement_period_windows(snapshot) if history_source == "imported_replay" else []
    opening_disqualifiers: list[str] = []
    opening_hard_disqualifiers: list[str] = []
    opening_positive: list[str] = []
    opening_negative: list[str] = []

    if snapshot.statement.account_id:
        account_witness = _witness(
            label="opening_account_identity",
            status="broker_proven",
            evidence=["accepted_source:broker_statement_account_id"],
        )
        opening_positive.append("broker_statement_account_id_available")
    else:
        account_witness = _witness(
            label="opening_account_identity",
            status="missing_broker_evidence",
            evidence=["accepted_source_missing:broker_statement_account_id"],
        )
        opening_negative.append("broker_statement_account_id_missing")
        opening_disqualifiers.append("opening_account_identity_missing")
        opening_hard_disqualifiers.append("opening_account_identity_missing")

    if snapshot.statement.base_currency:
        base_currency_witness = _witness(
            label="opening_base_currency_state",
            status="broker_proven",
            evidence=[f"accepted_source:broker_statement_base_currency:{snapshot.statement.base_currency}"],
        )
        opening_positive.append("broker_statement_base_currency_available")
    else:
        base_currency_witness = _witness(
            label="opening_base_currency_state",
            status="missing_broker_evidence",
            evidence=["accepted_source_missing:broker_statement_base_currency"],
        )
        opening_negative.append("broker_statement_base_currency_missing")
        opening_disqualifiers.append("opening_base_currency_missing")
        opening_hard_disqualifiers.append("opening_base_currency_missing")

    if broker_starting_cash_balances:
        cash_witness = _witness(
            label="opening_cash_state",
            status="broker_proven",
            evidence=["accepted_source:broker_cash_report_starting_cash"],
            counts={"currency_count": len(broker_starting_cash_balances)},
        )
        opening_positive.append("broker_proven_opening_cash_state_available")
    elif history_source == "synthetic_snapshot_history":
        cash_witness = _witness(
            label="opening_cash_state",
            status="unknown_inferred",
            evidence=["accepted_source_missing:broker_cash_report_starting_cash", "synthetic_snapshot_history_has_no_broker_opening_cash_state"],
        )
        opening_negative.append("opening_cash_state_missing_broker_evidence")
        opening_disqualifiers.append("opening_cash_state_missing")
        opening_hard_disqualifiers.append("opening_cash_state_missing")
    else:
        cash_witness = _witness(
            label="opening_cash_state",
            status="missing_broker_evidence",
            evidence=["accepted_source_missing:broker_cash_report_starting_cash"],
        )
        opening_negative.append("opening_cash_state_missing_broker_evidence")
        opening_disqualifiers.append("opening_cash_state_missing")
        opening_hard_disqualifiers.append("opening_cash_state_missing")

    if history_source == "synthetic_snapshot_history":
        holdings_witness = _witness(
            label="opening_holdings_state",
            status="unknown_inferred",
            evidence=["accepted_source_missing:broker_trade_window_opening_holdings", "opening_holdings_derived_from_current_snapshot"],
        )
        quantity_witness = _witness(
            label="opening_quantities_state",
            status="unknown_inferred",
            evidence=["accepted_source_missing:broker_trade_window_opening_quantities", "opening_quantities_derived_from_current_snapshot"],
        )
        opening_negative.append("opening_holdings_state_derived_from_current_snapshot")
        opening_negative.append("opening_quantities_state_derived_from_current_snapshot")
        opening_disqualifiers.extend(["synthetic_snapshot_opening_state", "synthetic_snapshot_opening_holdings_quantities"])
        opening_hard_disqualifiers.extend(["synthetic_snapshot_opening_state", "synthetic_snapshot_opening_holdings_quantities"])
    elif inferred_opening_symbols:
        counts = {"inferred_symbol_count": len(inferred_opening_symbols)}
        holdings_witness = _witness(
            label="opening_holdings_state",
            status="unknown_inferred",
            evidence=["accepted_source_missing:broker_trade_window_opening_holdings", "opening_holdings_require_inference_from_ending_positions_and_trades"],
            counts=counts,
        )
        quantity_witness = _witness(
            label="opening_quantities_state",
            status="unknown_inferred",
            evidence=["accepted_source_missing:broker_trade_window_opening_quantities", "opening_quantities_require_inference_from_ending_positions_and_trades"],
            counts=counts,
        )
        opening_negative.append("opening_holdings_inferred_from_ending_positions_and_trades")
        opening_negative.append("opening_quantities_inferred_from_ending_positions_and_trades")
        opening_disqualifiers.extend(["inferred_opening_holdings", "inferred_opening_quantities"])
        opening_hard_disqualifiers.extend(["inferred_opening_holdings", "inferred_opening_quantities"])
    elif snapshot.ledger_entries:
        covered_symbol_count = len({position.symbol for position in snapshot.positions})
        holdings_witness = _witness(
            label="opening_holdings_state",
            status="trade_window_covered",
            evidence=["accepted_source:broker_trade_window_opening_holdings"],
            counts={"covered_symbol_count": covered_symbol_count},
        )
        quantity_witness = _witness(
            label="opening_quantities_state",
            status="trade_window_covered",
            evidence=["accepted_source:broker_trade_window_opening_quantities"],
            counts={"covered_symbol_count": covered_symbol_count},
        )
        opening_positive.append("opening_holdings_covered_by_observed_trade_window")
        opening_positive.append("opening_quantities_covered_by_observed_trade_window")
    else:
        holdings_witness = _witness(
            label="opening_holdings_state",
            status="missing_broker_evidence",
            evidence=["accepted_source_missing:broker_trade_window_opening_holdings"],
        )
        quantity_witness = _witness(
            label="opening_quantities_state",
            status="missing_broker_evidence",
            evidence=["accepted_source_missing:broker_trade_window_opening_quantities"],
        )
        opening_negative.append("opening_holdings_broker_trade_window_missing")
        opening_negative.append("opening_quantities_broker_trade_window_missing")
        opening_disqualifiers.extend(["opening_holdings_broker_evidence_missing", "opening_quantities_broker_evidence_missing"])
        opening_hard_disqualifiers.extend(["opening_holdings_broker_evidence_missing", "opening_quantities_broker_evidence_missing"])

    if statement_windows:
        opening_timestamp_witness = _witness(
            label="opening_timestamp_semantics",
            status="broker_statement_period_boundary",
            evidence=[f"accepted_source:broker_statement_period_boundary:{statement_windows[0][0]}"],
            counts={"statement_window_count": len(statement_windows)},
        )
        opening_positive.append("opening_timestamp_semantics_backed_by_broker_statement_period")
    else:
        replay_boundary_evidence = ["accepted_source_missing:broker_statement_period_boundary"]
        if statement_windows:
            replay_boundary_evidence.append(f"replay_window_first_date:{statement_windows[0][0]}")
        opening_timestamp_witness = _witness(
            label="opening_timestamp_semantics",
            status="replay_boundary_only",
            evidence=replay_boundary_evidence,
        )
        opening_negative.append("opening_timestamp_semantics_not_broker_proven")
        opening_disqualifiers.append("opening_timestamp_semantics_missing")
        opening_hard_disqualifiers.append("opening_timestamp_semantics_missing")

    opening_state_verified = not opening_hard_disqualifiers
    admission_witness = _witness(
        label="opening_state_admission",
        status="opening_state_verified" if opening_state_verified else "opening_state_unverified",
        evidence=[
            "replay_status:replay_usable",
            "proof_eligibility_gate:opening_state"
            if opening_state_verified
            else "proof_eligibility_blocked_until_opening_state_verified",
        ],
    )

    witnesses = [
        account_witness,
        base_currency_witness,
        cash_witness,
        holdings_witness,
        quantity_witness,
        opening_timestamp_witness,
        admission_witness,
    ]
    opening_status: Literal["opening_state_verified", "opening_state_unverified"] = (
        "opening_state_verified" if opening_state_verified else "opening_state_unverified"
    )
    return (
        witnesses,
        opening_status,
        opening_positive,
        opening_negative,
        sorted(set(opening_disqualifiers)),
        sorted(set(opening_hard_disqualifiers)),
    )


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


def _build_corporate_action_basis(
    *,
    snapshot: ImportedPortfolioSnapshot,
    history_source: PortfolioProofHistorySource,
) -> tuple[
    PortfolioCorporateActionBasisPolicy,
    list[PortfolioProofWitness],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    statement_windows = _statement_period_windows(snapshot) if history_source == "imported_replay" else []
    scope_start_date = statement_windows[0][0] if statement_windows else None
    scope_end_date = statement_windows[-1][1] if statement_windows else None
    policy = PortfolioCorporateActionBasisPolicy(
        scope="broker_native_statement_window" if statement_windows else "broker_scope_unproven",
        cash_dividend_coverage_status=(
            "cash_dividend_coverage_proven_by_broker_native_evidence"
            if statement_windows
            else "cash_dividend_coverage_unproven"
        ),
        cash_dividend_observation_status=(
            "cash_dividend_observation_unproven"
            if not statement_windows
            else "no_cash_dividend_observed_within_covered_broker_scope"
        ),
        non_dividend_status="non_dividend_corporate_actions_unproven_and_disqualifying",
        scope_start_date=scope_start_date,
        scope_end_date=scope_end_date,
        statement_window_count=len(statement_windows),
    )

    positive_evidence: list[str] = []
    negative_evidence: list[str] = []
    disqualifiers = ["corporate_action_proof_missing"]
    hard_disqualifiers = ["corporate_action_proof_missing"]
    witnesses = [
        _witness(
            label="corporate_action_basis_policy",
            status="cash_dividend_scope_only",
            evidence=[
                "positive_proof_limited_to:cash_dividend",
                "coverage_and_absence_semantics_require:broker_native_statement_window",
                "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
            ],
            counts={"statement_window_count": len(statement_windows)},
        )
    ]

    if not statement_windows:
        negative_evidence.extend(
            [
                "cash_dividend_coverage_unproven_without_broker_native_statement_window",
                "cash_dividend_observation_unproven_without_covered_broker_scope",
                "non_dividend_corporate_actions_unproven_and_disqualifying",
            ]
        )
        witnesses.extend(
            [
                _witness(
                    label="cash_dividend_coverage_scope",
                    status="cash_dividend_coverage_unproven",
                    evidence=["broker_native_statement_window_missing_for_cash_dividend_scope"],
                    counts={"statement_window_count": 0},
                ),
                _witness(
                    label="cash_dividend_observation_scope",
                    status="cash_dividend_observation_unproven",
                    evidence=["cash_dividend_absence_not_provable_without_covered_broker_scope"],
                    counts={"broker_native_dividend_count": 0},
                ),
                _witness(
                    label="non_dividend_corporate_action_scope",
                    status="non_dividend_corporate_actions_unproven_and_disqualifying",
                    evidence=[
                        "unproven_action_classes:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes"
                    ],
                ),
            ]
        )
        return policy, witnesses, positive_evidence, negative_evidence, disqualifiers, hard_disqualifiers

    covered_window_labels = [f"{start}->{end}" for start, end in statement_windows]
    ledger = snapshot_to_ledger(snapshot)
    covered_broker_native_dividends = [
        entry
        for entry in ledger
        if entry.cash_movement_classification == "broker_explicit_dividend"
        and any(start <= entry.date.isoformat() <= end for start, end in statement_windows)
    ]
    outside_scope_dividends = [
        entry
        for entry in ledger
        if entry.cash_movement_classification == "broker_explicit_dividend"
        and not any(start <= entry.date.isoformat() <= end for start, end in statement_windows)
    ]

    positive_evidence.append("cash_dividend_coverage_proven_by_broker_native_evidence")
    witnesses.append(
        _witness(
            label="cash_dividend_coverage_scope",
            status="cash_dividend_coverage_proven_by_broker_native_evidence",
            evidence=["broker_native_statement_windows:" + ",".join(covered_window_labels)],
            counts={"statement_window_count": len(statement_windows)},
        )
    )

    if covered_broker_native_dividends:
        policy = policy.model_copy(update={"cash_dividend_observation_status": "cash_dividend_observed_by_broker_native_evidence"})
        positive_evidence.append("cash_dividend_observed_by_broker_native_evidence")
        witnesses.append(
            _witness(
                label="cash_dividend_observation_scope",
                status="cash_dividend_observed_by_broker_native_evidence",
                evidence=[
                    "broker_native_dividend_dates:"
                    + ",".join(sorted(entry.date.isoformat() for entry in covered_broker_native_dividends))
                ],
                counts={"broker_native_dividend_count": len(covered_broker_native_dividends)},
            )
        )
    else:
        positive_evidence.append("no_cash_dividend_observed_within_covered_broker_scope")
        witnesses.append(
            _witness(
                label="cash_dividend_observation_scope",
                status="no_cash_dividend_observed_within_covered_broker_scope",
                evidence=["no_broker_native_dividend_rows_observed_within_statement_window_scope"],
                counts={"broker_native_dividend_count": 0},
            )
        )

    if outside_scope_dividends:
        negative_evidence.append("broker_native_dividend_rows_outside_covered_statement_window_ignored_for_scope")
        witnesses.append(
            _witness(
                label="cash_dividend_out_of_scope_rows",
                status="outside_covered_scope_ignored",
                evidence=[
                    "broker_native_dividend_dates_outside_scope:"
                    + ",".join(sorted(entry.date.isoformat() for entry in outside_scope_dividends))
                ],
                counts={"outside_scope_dividend_count": len(outside_scope_dividends)},
            )
        )

    negative_evidence.append("non_dividend_corporate_actions_unproven_and_disqualifying")
    witnesses.append(
        _witness(
            label="non_dividend_corporate_action_scope",
            status="non_dividend_corporate_actions_unproven_and_disqualifying",
            evidence=[
                "unproven_action_classes:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes"
            ],
        )
    )
    return policy, witnesses, positive_evidence, negative_evidence, disqualifiers, hard_disqualifiers


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


def _parse_statement_period_boundary(value: str) -> date | None:
    normalized = value.strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def _statement_period_windows(snapshot: ImportedPortfolioSnapshot) -> list[tuple[str, str]]:
    windows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for statement in snapshot.statements or [snapshot.statement]:
        period = statement.statement_period
        if not period or " - " not in period:
            continue
        start_raw, end_raw = period.split(" - ", 1)
        start = _parse_statement_period_boundary(start_raw)
        end = _parse_statement_period_boundary(end_raw)
        if start is None or end is None:
            continue
        window = (start.isoformat(), end.isoformat())
        if window not in seen:
            windows.append(window)
            seen.add(window)
    return sorted(windows)


def _window_label(prefix: str, start: str, end: str) -> str:
    return f"{prefix}:{start}" if start == end else f"{prefix}:{start}:{end}"


def _segment_valuation_dates_by_coverage(
    valuation_dates: list[str],
    *,
    statement_windows: list[tuple[str, str]],
) -> tuple[list[tuple[str, str, str, int]], list[tuple[str, str, str, int]]]:
    if not valuation_dates:
        return [], []

    broker_segments: list[tuple[str, str, str, int]] = []
    disqualified_segments: list[tuple[str, str, str, int]] = []
    current_status: str | None = None
    segment_start: str | None = None
    segment_end: str | None = None
    segment_count = 0

    def flush_segment() -> None:
        nonlocal current_status, segment_start, segment_end, segment_count
        if current_status is None or segment_start is None or segment_end is None:
            return
        segment = (current_status, segment_start, segment_end, segment_count)
        if current_status == "broker_covered_window":
            broker_segments.append(segment)
        else:
            disqualified_segments.append(segment)
        current_status = None
        segment_start = None
        segment_end = None
        segment_count = 0

    for day_str in valuation_dates:
        covered = any(start <= day_str <= end for start, end in statement_windows)
        status = "broker_covered_window" if covered else "disqualified_window"
        if status == current_status:
            segment_end = day_str
            segment_count += 1
            continue
        flush_segment()
        current_status = status
        segment_start = day_str
        segment_end = day_str
        segment_count = 1

    flush_segment()
    return broker_segments, disqualified_segments


def _build_calendar_boundary_witnesses(
    *,
    snapshot: ImportedPortfolioSnapshot,
    valuation_dates: list[str],
    history_source: PortfolioProofHistorySource,
) -> tuple[list[PortfolioProofWitness], list[str], list[str], list[str], list[str]]:
    witnesses: list[PortfolioProofWitness] = []
    statement_windows = _statement_period_windows(snapshot) if history_source == "imported_replay" else []
    valuation_dates = sorted(set(valuation_dates))
    valuation_start = valuation_dates[0] if valuation_dates else None
    valuation_end = valuation_dates[-1] if valuation_dates else None

    if statement_windows:
        broker_start = statement_windows[0][0]
        broker_end = statement_windows[-1][1]
        first_status = "broker_statement_period_boundary"
        first_evidence = [f"broker_statement_period_first_covered_date:{broker_start}"]
        last_status = "broker_statement_period_boundary"
        last_evidence = [f"broker_statement_period_last_covered_date:{broker_end}"]
    else:
        broker_start = None
        broker_end = None
        first_status = "replay_boundary_only"
        first_evidence = ["broker_statement_period_first_covered_date_missing"]
        last_status = "replay_boundary_only"
        last_evidence = ["broker_statement_period_last_covered_date_missing"]
        if valuation_start is not None:
            first_evidence.append(f"replay_window_first_date:{valuation_start}")
        if valuation_end is not None:
            last_evidence.append(f"replay_window_last_date:{valuation_end}")

    witnesses.append(_witness(label="first_covered_date_basis", status=first_status, evidence=first_evidence))
    witnesses.append(_witness(label="last_covered_date_basis", status=last_status, evidence=last_evidence))

    calendar_positive: list[str] = []
    calendar_negative: list[str] = ["valuation_calendar_is_derived_from_benchmark_history"]
    calendar_disqualifiers: list[str] = ["calendar_coverage_not_broker_proven"]
    calendar_hard_disqualifiers: list[str] = ["calendar_coverage_not_broker_proven"]

    if valuation_dates:
        assert valuation_start is not None and valuation_end is not None
        replay_window_start = valuation_start
        replay_window_end = valuation_end
        witnesses.append(
            _witness(
                label=_window_label("replay_derived_window", replay_window_start, replay_window_end),
                status="replay_derived_window",
                evidence=[f"replay_window_dates:{replay_window_start}->{replay_window_end}"],
                counts={"valuation_date_count": len(valuation_dates)},
            )
        )
        calendar_positive.append("valuation_window_dates_available")
    else:
        calendar_negative.append("valuation_window_dates_missing")

    if valuation_dates == sorted(set(valuation_dates)) and valuation_dates:
        calendar_positive.append("valuation_dates_are_sorted_and_unique")

    if statement_windows:
        calendar_positive.append("broker_statement_period_windows_available")
        gap_ranges: list[str] = []
        for index in range(1, len(statement_windows)):
            previous_end = date.fromisoformat(statement_windows[index - 1][1])
            current_start = date.fromisoformat(statement_windows[index][0])
            if current_start > previous_end + timedelta(days=1):
                gap_start = (previous_end + timedelta(days=1)).isoformat()
                gap_end = (current_start - timedelta(days=1)).isoformat()
                gap_ranges.append(f"{gap_start}->{gap_end}")

        if gap_ranges:
            witnesses.append(
                _witness(
                    label="calendar_continuity_basis",
                    status="broker_statement_period_gapped",
                    evidence=["broker_statement_calendar_gaps:" + ",".join(gap_ranges)],
                    counts={"statement_window_count": len(statement_windows), "gap_count": len(gap_ranges)},
                )
            )
            calendar_negative.append("broker_statement_calendar_has_gaps")
            calendar_disqualifiers.append("broker_statement_calendar_gap")
            calendar_hard_disqualifiers.append("broker_statement_calendar_gap")
        else:
            witnesses.append(
                _witness(
                    label="calendar_continuity_basis",
                    status="broker_statement_period_contiguous",
                    evidence=[f"broker_statement_calendar_window:{broker_start}->{broker_end}"],
                    counts={"statement_window_count": len(statement_windows), "gap_count": 0},
                )
            )
            calendar_positive.append("broker_statement_calendar_continuity_observed")

        broker_segments, disqualified_segments = _segment_valuation_dates_by_coverage(
            valuation_dates,
            statement_windows=statement_windows,
        )
        for _, start, end, count in broker_segments:
            witnesses.append(
                _witness(
                    label=_window_label("broker_covered_window", start, end),
                    status="broker_covered_window",
                    evidence=[f"broker_statement_period_window:{start}->{end}"],
                    counts={"valuation_date_count": count},
                )
            )
        for _, start, end, count in disqualified_segments:
            witnesses.append(
                _witness(
                    label=_window_label("disqualified_window", start, end),
                    status="disqualified_window",
                    evidence=[f"replay_window_outside_broker_statement_coverage:{start}->{end}"],
                    counts={"valuation_date_count": count},
                )
            )
        if disqualified_segments:
            calendar_negative.append("replay_window_extends_outside_broker_statement_coverage")
            calendar_disqualifiers.append("replay_window_outside_broker_coverage")
            calendar_hard_disqualifiers.append("replay_window_outside_broker_coverage")
        else:
            calendar_positive.append("replay_window_within_broker_statement_boundaries")
    else:
        witnesses.append(
            _witness(
                label="calendar_continuity_basis",
                status="broker_statement_period_missing",
                evidence=["broker_statement_period_windows_missing"],
            )
        )
        if valuation_dates:
            assert valuation_start is not None and valuation_end is not None
            replay_window_start = valuation_start
            replay_window_end = valuation_end
            witnesses.append(
                _witness(
                    label=_window_label("disqualified_window", replay_window_start, replay_window_end),
                    status="disqualified_window",
                    evidence=[f"replay_window_not_backed_by_broker_statement_window:{replay_window_start}->{replay_window_end}"],
                    counts={"valuation_date_count": len(valuation_dates)},
                )
            )
        calendar_negative.append("broker_statement_period_windows_missing")
    return (
        witnesses,
        calendar_positive,
        calendar_negative,
        sorted(set(calendar_disqualifiers)),
        sorted(set(calendar_hard_disqualifiers)),
    )


def _terminal_totals_match(actual: float | None, expected: float | None, tolerance: float = 0.01) -> bool:
    if actual is None or expected is None:
        return True
    return abs(actual - expected) <= tolerance


def _build_terminal_reconciliation_evidence(
    *,
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
) -> tuple[list[PortfolioProofWitness], list[str], list[str], list[str], list[str]]:
    if not valuation_dates:
        return (
            [
                _witness(
                    label="terminal_reconciliation_basis",
                    status="terminal_state_unavailable",
                    evidence=["terminal_state_unavailable_without_valuation_dates"],
                )
            ],
            [],
            ["terminal_state_unavailable_without_valuation_dates"],
            ["terminal_state_unavailable"],
            ["terminal_state_unavailable"],
        )

    raw_states = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=snapshot.statement.base_currency or "USD",
        fx_history=fx_history,
    ).build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=False,
    )
    raw_terminal_state = raw_states[-1] if raw_states else None
    if raw_terminal_state is None:
        return (
            [
                _witness(
                    label="terminal_reconciliation_basis",
                    status="terminal_state_unavailable",
                    evidence=["terminal_state_replay_failed"],
                )
            ],
            [],
            ["terminal_state_replay_failed"],
            ["terminal_state_unavailable"],
            ["terminal_state_unavailable"],
        )

    statement_totals = snapshot.statement_totals
    expected_ending_nav = statement_totals.ending_nav if statement_totals is not None else None
    expected_cash_total = statement_totals.cash_total if statement_totals is not None else None
    raw_cash_total = raw_terminal_state.cash.get(snapshot.statement.base_currency or "USD")
    raw_nav_total = raw_terminal_state.total_portfolio_value

    if expected_ending_nav is None and expected_cash_total is None:
        return (
            [
                _witness(
                    label="terminal_reconciliation_basis",
                    status="terminal_statement_totals_missing",
                    evidence=["terminal_statement_totals_not_available_for_comparison"],
                    counts={"compared_field_count": 0},
                )
            ],
            ["terminal_replay_state_available"],
            ["terminal_statement_totals_not_available_for_comparison"],
            [],
            [],
        )

    matches_nav = _terminal_totals_match(raw_nav_total, expected_ending_nav)
    matches_cash = _terminal_totals_match(raw_cash_total, expected_cash_total)
    compared_field_count = int(expected_ending_nav is not None) + int(expected_cash_total is not None)
    evidence = []
    if expected_ending_nav is not None:
        evidence.append(f"terminal_nav_match:{str(matches_nav).lower()}")
    if expected_cash_total is not None:
        evidence.append(f"terminal_cash_match:{str(matches_cash).lower()}")

    if matches_nav and matches_cash:
        return (
            [
                _witness(
                    label="terminal_reconciliation_basis",
                    status="naturally_reconciled_terminal_state",
                    evidence=evidence,
                    counts={"compared_field_count": compared_field_count},
                )
            ],
            ["terminal_state_naturally_reconciles_to_statement_totals"],
            [],
            [],
            [],
        )

    return (
        [
            _witness(
                label="terminal_reconciliation_basis",
                status="force_reconciled_terminal_state",
                evidence=evidence + ["force_matching_statement_totals_do_not_count_as_terminal_proof"],
                counts={"compared_field_count": compared_field_count},
            )
        ],
        [],
        ["terminal_state_requires_force_reconciliation_to_statement_totals"],
        ["terminal_force_reconciliation_present"],
        ["terminal_force_reconciliation_present"],
    )


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
    fallback_prices: dict[str, float | None] = {position.symbol: position.close_price for position in snapshot.positions}
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


def _portfolio_slice_scope(
    *,
    snapshot: ImportedPortfolioSnapshot | None,
    valuation_dates: list[str],
    history_source: PortfolioProofHistorySource,
) -> dict[str, str | bool | int | None]:
    normalized_dates = sorted(set(valuation_dates))
    statement_windows = _statement_period_windows(snapshot) if snapshot is not None and history_source == "imported_replay" else []
    return {
        "account_id": snapshot.statement.account_id if snapshot is not None else None,
        "base_currency": snapshot.statement.base_currency if snapshot is not None else None,
        "history_source": history_source,
        "valuation_window_start": normalized_dates[0] if normalized_dates else None,
        "valuation_window_end": normalized_dates[-1] if normalized_dates else None,
        "valuation_date_count": len(normalized_dates),
        "statement_window_start": statement_windows[0][0] if statement_windows else None,
        "statement_window_end": statement_windows[-1][1] if statement_windows else None,
        "statement_window_count": len(statement_windows),
    }


def _admission_bucket_decision(
    *,
    bucket: str,
    scope: dict[str, str | bool | int | None],
    provenance_buckets: list[str],
    blocking_reasons: list[str],
    status: Literal["withheld", "rejected", "not_applicable"] | None = None,
) -> PortfolioProofAdmissionBucketDecision:
    resolved_reasons = sorted(set(blocking_reasons))
    resolved_status = status or ("rejected" if resolved_reasons else "withheld")
    return PortfolioProofAdmissionBucketDecision(
        bucket=bucket,
        status=resolved_status,
        blocks_admission=bool(resolved_reasons),
        provenance_buckets=sorted(set(provenance_buckets)),
        blocking_reasons=resolved_reasons,
        scope=scope,
    )


def _build_portfolio_admission_decision(
    *,
    snapshot: ImportedPortfolioSnapshot | None,
    valuation_dates: list[str],
    history_source: PortfolioProofHistorySource,
    evidence: PortfolioProofEvidenceBundle,
    disqualifiers: list[str],
) -> PortfolioProofAdmissionDecision:
    scope = _portfolio_slice_scope(
        snapshot=snapshot,
        valuation_dates=valuation_dates,
        history_source=history_source,
    )

    if history_source == "unavailable":
        unavailable_reason = PortfolioProofAdmissionBlockingReason(
            code="portfolio_history_unavailable",
            bucket="portfolio_admission",
            provenance_bucket="portfolio_history",
            reason_type="missing",
        )
        bucket_decisions = [
            _admission_bucket_decision(
                bucket=bucket,
                scope=scope,
                provenance_buckets=[bucket],
                blocking_reasons=["portfolio_history_unavailable"],
                status="not_applicable",
            )
            for bucket in (
                "return_basis_metadata",
                "capital_boundary_proof",
                "valuation_basis_separation",
                "boundary_hardening",
                "opening_state_admission",
                "fx_proof",
                "corporate_action_proof",
                "investor_economics_proof",
            )
        ]
        return PortfolioProofAdmissionDecision(
            status="not_applicable",
            scope=scope,
            blocking_reasons=[unavailable_reason],
            missing_proof_buckets=sorted(bucket.bucket for bucket in bucket_decisions),
            bucket_decisions=bucket_decisions,
        )

    blocking_reasons: list[PortfolioProofAdmissionBlockingReason] = []
    missing_proof_buckets: set[str] = set()

    def add_reasons(
        *,
        bucket: str,
        provenance_bucket: str,
        reason_codes: list[str],
        reason_type: Literal["blocking", "missing", "scope_mismatch", "withheld"] = "blocking",
    ) -> None:
        for code in sorted(set(reason_codes)):
            blocking_reasons.append(
                PortfolioProofAdmissionBlockingReason(
                    code=code,
                    bucket=bucket,
                    provenance_bucket=provenance_bucket,
                    reason_type=reason_type,
                )
            )

    valuation_scope = {
        "base_currency": scope["base_currency"],
        "history_source": scope["history_source"],
        "valuation_window_start": scope["valuation_window_start"],
        "valuation_window_end": scope["valuation_window_end"],
        "valuation_date_count": scope["valuation_date_count"],
    }
    opening_scope = {
        "account_id": scope["account_id"],
        "base_currency": scope["base_currency"],
        "history_source": scope["history_source"],
        "slice_start": scope["valuation_window_start"],
    }
    capital_boundary_scope = {
        "account_id": scope["account_id"],
        "base_currency": scope["base_currency"],
        "history_source": scope["history_source"],
        "valuation_window_start": scope["valuation_window_start"],
        "valuation_window_end": scope["valuation_window_end"],
    }
    boundary_hardening_scope = {
        "account_id": scope["account_id"],
        "base_currency": scope["base_currency"],
        "valuation_window_start": scope["valuation_window_start"],
        "valuation_window_end": scope["valuation_window_end"],
        "statement_window_start": scope["statement_window_start"],
        "statement_window_end": scope["statement_window_end"],
        "statement_window_count": scope["statement_window_count"],
    }
    corporate_action_scope = {
        "base_currency": scope["base_currency"],
        "valuation_window_start": scope["valuation_window_start"],
        "valuation_window_end": scope["valuation_window_end"],
        "statement_window_start": evidence.corporate_action_basis.policy.scope_start_date,
        "statement_window_end": evidence.corporate_action_basis.policy.scope_end_date,
        "statement_window_count": evidence.corporate_action_basis.policy.statement_window_count,
    }
    fx_scope = {
        "base_currency": scope["base_currency"],
        "valuation_window_start": scope["valuation_window_start"],
        "valuation_window_end": scope["valuation_window_end"],
        "valuation_date_count": scope["valuation_date_count"],
    }

    return_basis_reasons = list(evidence.valuation_basis.disqualifiers)
    if return_basis_reasons:
        missing_proof_buckets.add("return_basis_metadata")
        add_reasons(
            bucket="return_basis_metadata",
            provenance_bucket="valuation_basis",
            reason_codes=return_basis_reasons,
        )

    valuation_reasons = list(evidence.valuation_basis.disqualifiers)
    if valuation_reasons:
        missing_proof_buckets.add("valuation_basis_separation")
        add_reasons(
            bucket="valuation_basis_separation",
            provenance_bucket="valuation_basis",
            reason_codes=valuation_reasons,
        )

    capital_boundary_reasons = list(evidence.cash_flow_basis.disqualifiers)
    if capital_boundary_reasons:
        missing_proof_buckets.add("capital_boundary_proof")
        add_reasons(
            bucket="capital_boundary_proof",
            provenance_bucket="cash_flow_basis",
            reason_codes=capital_boundary_reasons,
        )

    opening_reasons = list(evidence.opening_state_basis.disqualifiers)
    if opening_reasons:
        missing_proof_buckets.add("opening_state_admission")
        add_reasons(
            bucket="opening_state_admission",
            provenance_bucket="opening_state_basis",
            reason_codes=opening_reasons,
        )

    fx_reasons = list(evidence.fx_basis.disqualifiers)
    if fx_reasons:
        missing_proof_buckets.add("fx_proof")
        add_reasons(
            bucket="fx_proof",
            provenance_bucket="fx_basis",
            reason_codes=fx_reasons,
        )

    corporate_action_reasons = list(evidence.corporate_action_basis.disqualifiers)
    if corporate_action_reasons:
        missing_proof_buckets.add("corporate_action_proof")
        add_reasons(
            bucket="corporate_action_proof",
            provenance_bucket="corporate_action_basis",
            reason_codes=corporate_action_reasons,
        )

    boundary_hardening_reasons = sorted(
        {
            *evidence.calendar_coverage_basis.disqualifiers,
            *evidence.terminal_reconciliation_basis.disqualifiers,
        }
    )
    if boundary_hardening_reasons:
        missing_proof_buckets.add("boundary_hardening")
        add_reasons(
            bucket="boundary_hardening",
            provenance_bucket="calendar_coverage_basis",
            reason_codes=evidence.calendar_coverage_basis.disqualifiers,
        )
        add_reasons(
            bucket="boundary_hardening",
            provenance_bucket="terminal_reconciliation_basis",
            reason_codes=evidence.terminal_reconciliation_basis.disqualifiers,
        )

    valuation_start = cast(str | None, scope.get("valuation_window_start"))
    valuation_end = cast(str | None, scope.get("valuation_window_end"))
    corporate_start = evidence.corporate_action_basis.policy.scope_start_date
    corporate_end = evidence.corporate_action_basis.policy.scope_end_date
    if valuation_start and valuation_end and (corporate_start is None or corporate_end is None):
        missing_proof_buckets.add("corporate_action_proof")
        add_reasons(
            bucket="corporate_action_proof",
            provenance_bucket="corporate_action_basis",
            reason_codes=["corporate_action_scope_unproven_for_portfolio_slice"],
            reason_type="scope_mismatch",
        )
    elif valuation_start and valuation_end and corporate_start is not None and corporate_end is not None:
        if corporate_start > valuation_start or corporate_end < valuation_end:
            missing_proof_buckets.add("corporate_action_proof")
            add_reasons(
                bucket="corporate_action_proof",
                provenance_bucket="corporate_action_basis",
                reason_codes=["corporate_action_scope_mismatch_for_portfolio_slice"],
                reason_type="scope_mismatch",
            )

    statement_start = cast(str | None, scope.get("statement_window_start"))
    statement_end = cast(str | None, scope.get("statement_window_end"))
    if valuation_start and valuation_end and (statement_start is None or statement_end is None):
        missing_proof_buckets.add("boundary_hardening")
        add_reasons(
            bucket="boundary_hardening",
            provenance_bucket="calendar_coverage_basis",
            reason_codes=["statement_window_scope_unproven_for_portfolio_slice"],
            reason_type="scope_mismatch",
        )
    elif valuation_start and valuation_end and statement_start is not None and statement_end is not None:
        if statement_start > valuation_start or statement_end < valuation_end:
            missing_proof_buckets.add("boundary_hardening")
            add_reasons(
                bucket="boundary_hardening",
                provenance_bucket="calendar_coverage_basis",
                reason_codes=["statement_window_scope_mismatch_for_portfolio_slice"],
                reason_type="scope_mismatch",
            )

    missing_proof_buckets.add("investor_economics_proof")
    add_reasons(
        bucket="investor_economics_proof",
        provenance_bucket=PORTFOLIO_ADMISSION_GOVERNOR,
        reason_codes=["missing_investor_economics_proof_bucket"],
        reason_type="missing",
    )

    governor_reason_codes = ["missing_investor_economics_proof_bucket"]
    if "portfolio_verified_total_return_withheld" in disqualifiers:
        add_reasons(
            bucket="investor_economics_proof",
            provenance_bucket=PORTFOLIO_ADMISSION_GOVERNOR,
            reason_codes=["portfolio_verified_total_return_withheld"],
            reason_type="withheld",
        )
        governor_reason_codes = ["missing_investor_economics_proof_bucket", "portfolio_verified_total_return_withheld"]

    bucket_decisions = [
        _admission_bucket_decision(
            bucket="return_basis_metadata",
            scope=valuation_scope,
            provenance_buckets=["valuation_basis"],
            blocking_reasons=return_basis_reasons,
        ),
        _admission_bucket_decision(
            bucket="capital_boundary_proof",
            scope=capital_boundary_scope,
            provenance_buckets=["cash_flow_basis"],
            blocking_reasons=capital_boundary_reasons,
        ),
        _admission_bucket_decision(
            bucket="valuation_basis_separation",
            scope=valuation_scope,
            provenance_buckets=["valuation_basis"],
            blocking_reasons=valuation_reasons,
        ),
        _admission_bucket_decision(
            bucket="boundary_hardening",
            scope=boundary_hardening_scope,
            provenance_buckets=["calendar_coverage_basis", "terminal_reconciliation_basis"],
            blocking_reasons=sorted(
                {
                    *boundary_hardening_reasons,
                    *[
                        reason.code
                        for reason in blocking_reasons
                        if reason.bucket == "boundary_hardening" and reason.reason_type == "scope_mismatch"
                    ],
                }
            ),
        ),
        _admission_bucket_decision(
            bucket="opening_state_admission",
            scope=opening_scope,
            provenance_buckets=["opening_state_basis"],
            blocking_reasons=opening_reasons,
        ),
        _admission_bucket_decision(
            bucket="fx_proof",
            scope=fx_scope,
            provenance_buckets=["fx_basis"],
            blocking_reasons=fx_reasons,
        ),
        _admission_bucket_decision(
            bucket="corporate_action_proof",
            scope=corporate_action_scope,
            provenance_buckets=["corporate_action_basis"],
            blocking_reasons=sorted(
                {
                    *corporate_action_reasons,
                    *[
                        reason.code
                        for reason in blocking_reasons
                        if reason.bucket == "corporate_action_proof" and reason.reason_type == "scope_mismatch"
                    ],
                }
            ),
        ),
        _admission_bucket_decision(
            bucket="investor_economics_proof",
            scope=scope,
            provenance_buckets=[PORTFOLIO_ADMISSION_GOVERNOR],
            blocking_reasons=governor_reason_codes,
            status="withheld",
        ),
    ]

    non_governor_reasons = [
        reason
        for reason in blocking_reasons
        if reason.code not in {"missing_investor_economics_proof_bucket", "portfolio_verified_total_return_withheld"}
    ]
    admission_status: Literal["withheld", "rejected", "not_applicable"] = (
        "rejected" if non_governor_reasons else "withheld"
    )
    return PortfolioProofAdmissionDecision(
        status=admission_status,
        scope=scope,
        blocking_reasons=sorted(
            blocking_reasons,
            key=lambda reason: (reason.bucket, reason.provenance_bucket, reason.code),
        ),
        missing_proof_buckets=sorted(missing_proof_buckets),
        bucket_decisions=bucket_decisions,
    )


def build_portfolio_proof_metadata(
    *,
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: Any,
    history_source: PortfolioProofHistorySource,
) -> PortfolioProofMetadata:
    if history_source == "unavailable":
        unavailable_corporate_action_policy = PortfolioCorporateActionBasisPolicy(
            scope="broker_scope_unproven",
            cash_dividend_coverage_status="cash_dividend_coverage_unproven",
            cash_dividend_observation_status="cash_dividend_observation_unproven",
            non_dividend_status="non_dividend_corporate_actions_unproven_and_disqualifying",
            scope_start_date=None,
            scope_end_date=None,
            statement_window_count=0,
        )
        evidence = PortfolioProofEvidenceBundle(
            opening_state_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            valuation_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            cash_flow_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            fx_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            corporate_action_basis=_corporate_action_bucket(
                policy=unavailable_corporate_action_policy,
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            terminal_reconciliation_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
            calendar_coverage_basis=_bucket(
                positive_evidence=[],
                negative_evidence=["portfolio_history_unavailable"],
                disqualifiers=["portfolio_history_unavailable"],
                hard_disqualifiers=["portfolio_history_unavailable"],
                witnesses=[],
            ),
        )
        admission = _build_portfolio_admission_decision(
            snapshot=snapshot,
            valuation_dates=valuation_dates,
            history_source=history_source,
            evidence=evidence,
            disqualifiers=["portfolio_history_unavailable"],
        )
        return PortfolioProofMetadata(
            proof_system="portfolio_verified_total_return_v1",
            portfolio_path="unavailable",
            verification_status="unavailable",
            output_status="unavailable",
            replay_status="replay_unavailable",
            opening_state_status="opening_state_unavailable",
            verified_total_return_emitted=False,
            benchmark_proof_independent=True,
            disqualifiers=["portfolio_history_unavailable"],
            hard_disqualifiers=["portfolio_history_unavailable"],
            admission=admission,
            evidence=evidence,
        )

    fx_rates = _extract_fx_rates(fx_history)
    inferred_opening_symbols = _inferred_opening_symbols(snapshot)
    (
        opening_witnesses,
        opening_state_status,
        opening_positive,
        opening_negative,
        opening_disqualifiers,
        opening_hard_disqualifiers,
    ) = _opening_state_witnesses(
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
    calendar_witnesses, calendar_positive, calendar_negative, calendar_disqualifiers, calendar_hard_disqualifiers = (
        _build_calendar_boundary_witnesses(
            snapshot=snapshot,
            valuation_dates=valuation_dates,
            history_source=history_source,
        )
    )
    terminal_witnesses, terminal_positive, terminal_negative, terminal_disqualifiers, terminal_hard_disqualifiers = (
        _build_terminal_reconciliation_evidence(
            snapshot=snapshot,
            price_histories=price_histories,
            valuation_dates=valuation_dates,
            fx_history=fx_rates,
        )
    )

    if snapshot.ledger_entries:
        opening_positive.insert(0, "broker_ledger_entries_available")
    else:
        opening_positive.insert(0, "no_broker_ledger_entries_available")

    valuation_positive = [
        "valuation_dates_available" if valuation_dates else "valuation_dates_missing",
        "position_price_histories_loaded" if price_histories else "position_price_histories_missing",
    ]
    if VALUATION_BROKER_PROVEN in valuation_sources:
        valuation_positive.append("broker_proven_mark_to_market_inputs_observed")

    valuation_negative: list[str] = []
    valuation_disqualifiers: list[str] = []
    valuation_hard_disqualifiers: list[str] = []
    if VALUATION_RAW_VENDOR in valuation_sources:
        valuation_negative.append("vendor_raw_price_used_for_valuation")
        valuation_disqualifiers.append("raw_price_used_for_valuation")
        valuation_hard_disqualifiers.append("raw_price_used_for_valuation")
    if history_source == "synthetic_snapshot_history":
        valuation_negative.append("valuation_path_is_synthetic_snapshot_history")
        valuation_disqualifiers.append("synthetic_snapshot_history")
        valuation_hard_disqualifiers.append("synthetic_snapshot_history")
    if VALUATION_FORWARD_FILL in valuation_sources or forward_filled_symbols:
        valuation_negative.append("position_prices_forward_filled")
        valuation_disqualifiers.append("forward_filled_prices")
        valuation_hard_disqualifiers.append("forward_filled_prices")
    if VALUATION_SNAPSHOT_FALLBACK in valuation_sources or fallback_symbols:
        valuation_negative.append("snapshot_close_price_fallback_used")
        valuation_disqualifiers.append("snapshot_close_price_fallback")
        valuation_hard_disqualifiers.append("snapshot_close_price_fallback")
    if VALUATION_OTHER_FALLBACK in valuation_sources:
        valuation_negative.append("other_fallback_valuation_construction_used")
        valuation_disqualifiers.append("other_fallback_valuation_construction")
        valuation_hard_disqualifiers.append("other_fallback_valuation_construction")
    if VALUATION_MIXED in valuation_date_bases:
        valuation_negative.append("mixed_basis_valuation_construction_used")
        valuation_disqualifiers.append("mixed_basis_valuation")
        valuation_hard_disqualifiers.append("mixed_basis_valuation")

    cash_flow_positive = [
        "broker_ledger_entries_available" if snapshot.ledger_entries else "no_broker_ledger_entries_available",
    ]
    cash_flow_negative: list[str] = []
    cash_flow_disqualifiers: list[str] = []
    cash_flow_hard_disqualifiers: list[str] = []
    if history_source == "synthetic_snapshot_history":
        cash_flow_negative.append("synthetic_snapshot_history_has_no_external_flow_replay")
        cash_flow_disqualifiers.append("synthetic_snapshot_history")
        cash_flow_hard_disqualifiers.append("synthetic_snapshot_history")
    elif not snapshot.ledger_entries:
        cash_flow_negative.append("broker_cash_movement_ledger_not_available")
        cash_flow_disqualifiers.append("cash_flow_broker_evidence_missing")
        cash_flow_hard_disqualifiers.append("cash_flow_broker_evidence_missing")
    elif cash_flow_counts["unknown"] > 0:
        cash_flow_negative.append("unknown_cash_movement_types_present")
        cash_flow_disqualifiers.append("unknown_cash_movements")
        cash_flow_hard_disqualifiers.append("unknown_cash_movements")
    else:
        cash_flow_positive.append("cash_movement_entries_classified_with_broker_native_evidence")

    fx_witnesses, fx_positive, fx_negative, fx_disqualifiers, fx_hard_disqualifiers = _build_fx_witnesses(
        snapshot=snapshot,
        valuation_dates=valuation_dates,
        fx_history=fx_history,
    )

    (
        corporate_action_policy,
        corporate_action_witnesses,
        corporate_action_positive,
        corporate_action_negative,
        corporate_action_disqualifiers,
        corporate_action_hard_disqualifiers,
    ) = _build_corporate_action_basis(snapshot=snapshot, history_source=history_source)

    evidence = PortfolioProofEvidenceBundle(
        opening_state_basis=_bucket(
            positive_evidence=opening_positive,
            negative_evidence=opening_negative,
            disqualifiers=sorted(set(opening_disqualifiers)),
            hard_disqualifiers=sorted(set(opening_hard_disqualifiers)),
            witnesses=opening_witnesses,
        ),
        valuation_basis=_bucket(
            positive_evidence=valuation_positive,
            negative_evidence=valuation_negative,
            disqualifiers=sorted(set(valuation_disqualifiers)),
            hard_disqualifiers=sorted(set(valuation_hard_disqualifiers)),
            witnesses=valuation_witnesses,
        ),
        cash_flow_basis=_bucket(
            positive_evidence=cash_flow_positive,
            negative_evidence=cash_flow_negative,
            disqualifiers=sorted(set(cash_flow_disqualifiers)),
            hard_disqualifiers=sorted(set(cash_flow_hard_disqualifiers)),
            witnesses=cash_flow_witnesses,
        ),
        fx_basis=_bucket(
            positive_evidence=fx_positive,
            negative_evidence=fx_negative,
            disqualifiers=sorted(set(fx_disqualifiers)),
            hard_disqualifiers=sorted(set(fx_hard_disqualifiers)),
            witnesses=fx_witnesses,
        ),
        corporate_action_basis=_corporate_action_bucket(
            policy=corporate_action_policy,
            positive_evidence=corporate_action_positive,
            negative_evidence=corporate_action_negative,
            disqualifiers=sorted(set(corporate_action_disqualifiers)),
            hard_disqualifiers=sorted(set(corporate_action_hard_disqualifiers)),
            witnesses=corporate_action_witnesses,
        ),
        terminal_reconciliation_basis=_bucket(
            positive_evidence=terminal_positive,
            negative_evidence=terminal_negative,
            disqualifiers=sorted(set(terminal_disqualifiers)),
            hard_disqualifiers=sorted(set(terminal_hard_disqualifiers)),
            witnesses=terminal_witnesses,
        ),
        calendar_coverage_basis=_bucket(
            positive_evidence=calendar_positive,
            negative_evidence=calendar_negative,
            disqualifiers=sorted(set(calendar_disqualifiers)),
            hard_disqualifiers=sorted(set(calendar_hard_disqualifiers)),
            witnesses=calendar_witnesses,
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
    hard_disqualifiers = sorted(
        {
            *evidence.opening_state_basis.hard_disqualifiers,
            *evidence.valuation_basis.hard_disqualifiers,
            *evidence.cash_flow_basis.hard_disqualifiers,
            *evidence.fx_basis.hard_disqualifiers,
            *evidence.corporate_action_basis.hard_disqualifiers,
            *evidence.terminal_reconciliation_basis.hard_disqualifiers,
            *evidence.calendar_coverage_basis.hard_disqualifiers,
        }
    )
    admission = _build_portfolio_admission_decision(
        snapshot=snapshot,
        valuation_dates=valuation_dates,
        history_source=history_source,
        evidence=evidence,
        disqualifiers=disqualifiers,
    )
    return PortfolioProofMetadata(
        proof_system="portfolio_verified_total_return_v1",
        portfolio_path="withheld",
        verification_status="unverified",
        output_status="withheld",
        replay_status="replay_usable",
        opening_state_status=cast(Literal["opening_state_verified", "opening_state_unverified", "opening_state_unavailable"], opening_state_status),
        verified_total_return_emitted=False,
        benchmark_proof_independent=True,
        disqualifiers=disqualifiers,
        hard_disqualifiers=hard_disqualifiers,
        admission=admission,
        evidence=evidence,
    )


def build_unavailable_portfolio_proof_metadata(reason: str = "portfolio_history_unavailable") -> PortfolioProofMetadata:
    unavailable_corporate_action_policy = PortfolioCorporateActionBasisPolicy(
        scope="broker_scope_unproven",
        cash_dividend_coverage_status="cash_dividend_coverage_unproven",
        cash_dividend_observation_status="cash_dividend_observation_unproven",
        non_dividend_status="non_dividend_corporate_actions_unproven_and_disqualifying",
        scope_start_date=None,
        scope_end_date=None,
        statement_window_count=0,
    )
    evidence = PortfolioProofEvidenceBundle(
        opening_state_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
        valuation_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
        cash_flow_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
        fx_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
        corporate_action_basis=_corporate_action_bucket(
            policy=unavailable_corporate_action_policy,
            positive_evidence=[],
            negative_evidence=[reason],
            disqualifiers=[reason],
            hard_disqualifiers=[reason],
            witnesses=[],
        ),
        terminal_reconciliation_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
        calendar_coverage_basis=_bucket(positive_evidence=[], negative_evidence=[reason], disqualifiers=[reason], hard_disqualifiers=[reason], witnesses=[]),
    )
    admission = _build_portfolio_admission_decision(
        snapshot=None,
        valuation_dates=[],
        history_source="unavailable",
        evidence=evidence,
        disqualifiers=[reason],
    )
    return PortfolioProofMetadata(
        proof_system="portfolio_verified_total_return_v1",
        portfolio_path="unavailable",
        verification_status="unavailable",
        output_status="unavailable",
        replay_status="replay_unavailable",
        opening_state_status="opening_state_unavailable",
        verified_total_return_emitted=False,
        benchmark_proof_independent=True,
        disqualifiers=[reason],
        hard_disqualifiers=[reason],
        admission=admission,
        evidence=evidence,
    )
