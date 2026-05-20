from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.schemas.generic_ranking import UniverseSpec, UniverseSpecSnapshot

logger = logging.getLogger(__name__)


# ── Static index snapshot loader ─────────────────────────────────────────────
#
# Indexes that have no live FMP constituent endpoint (currently: russell1000)
# resolve from a versioned static snapshot under data/universe/index_snapshots/.
# Each snapshot file is a JSON document with explicit provenance metadata
# (source URL, snapshot_date, source notes) and a list of constituents.
#
# The snapshot is the source of truth at run time: UniverseSpecSnapshot captures
# the resolved member list AND a content-addressed `spec_digest` so a persisted
# generic_ranking artifact remains reproducible even if the snapshot file is
# later refreshed in place.
#
# Refreshing the snapshot (Russell 1000): download the iShares IWB ETF holdings
# CSV from BlackRock (https://www.ishares.com/us/products/239726/) and overwrite
# the snapshot file with the parsed full membership. A scripted ingestion is
# intentionally deferred to a future slice — until then the bundled snapshot
# is a representative sample of large-cap names, NOT the full Russell 1000.

# __file__ = services/quant-engine/app/services/universe_resolver.py
# .parents[0] = services/quant-engine/app/services/
# .parents[1] = services/quant-engine/app/
# .parents[2] = services/quant-engine/
# .parents[3] = services/
# .parents[4] = repo root
_DEFAULT_INDEX_SNAPSHOTS_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "universe" / "index_snapshots"
)
_INDEX_SNAPSHOT_SCHEMA_VERSION = "index_snapshot_v1"


class IndexSnapshotError(ValueError):
    """Raised when a static index snapshot file is missing, malformed, or fails validation."""


def _load_index_snapshot(index_id: str, snapshots_dir: Path | None = None) -> list[dict]:
    """Load and validate a static index snapshot file.

    Returns the list of constituent dicts (each with `symbol`, optional `name` + `sector`).
    Fails closed on missing file, invalid JSON, schema mismatch, or wrong index_id.
    """
    base_dir = snapshots_dir or _DEFAULT_INDEX_SNAPSHOTS_DIR
    path = base_dir / f"{index_id}.json"
    if not path.exists():
        raise IndexSnapshotError(
            f"index snapshot file missing for index_id={index_id!r}: expected {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise IndexSnapshotError(f"index snapshot {path} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IndexSnapshotError(f"index snapshot {path} root must be an object")
    if payload.get("snapshot_schema_version") != _INDEX_SNAPSHOT_SCHEMA_VERSION:
        raise IndexSnapshotError(
            f"index snapshot {path} has unsupported snapshot_schema_version "
            f"{payload.get('snapshot_schema_version')!r}; expected {_INDEX_SNAPSHOT_SCHEMA_VERSION!r}"
        )
    if payload.get("index_id") != index_id:
        raise IndexSnapshotError(
            f"index snapshot {path} index_id field {payload.get('index_id')!r} does not match requested {index_id!r}"
        )
    constituents = payload.get("constituents")
    if not isinstance(constituents, list):
        raise IndexSnapshotError(f"index snapshot {path} constituents field must be a list")
    for row in constituents:
        if not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or not row["symbol"].strip():
            raise IndexSnapshotError(f"index snapshot {path} contains malformed constituent row: {row!r}")
    return constituents


class UniverseResolver:
    def __init__(self, fmp_client: object | None = None) -> None:
        # fmp_client is an instance of FmpClient; typed as object to avoid circular import
        self._fmp = fmp_client

    def resolve(self, spec: UniverseSpec, as_of_date: str) -> UniverseSpecSnapshot:
        member_sectors: dict[str, str] = {}
        if spec.universe_kind in ("etf_peer_group", "custom_list"):
            # No sector source is consulted for explicit-list universes; member_sectors
            # stays empty and downstream sector-aware constraints surface not_evaluated.
            members = sorted(set(spec.explicit_symbols))
        elif spec.universe_kind in ("broad_equity_screen", "sector_screen"):
            members, member_sectors = self._screen_equity(spec)
        elif spec.universe_kind == "index_constituent":
            members, member_sectors = self._resolve_index_constituents(spec)
        else:
            raise ValueError(f"Unsupported universe_kind: {spec.universe_kind!r}")

        spec_digest = hashlib.sha256(
            json.dumps(spec.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()

        return UniverseSpecSnapshot(
            universe_id=spec.universe_id,
            universe_kind=spec.universe_kind,
            spec_digest=spec_digest,
            evaluated_members=members,
            evaluated_at=as_of_date,
            member_sectors={
                symbol: member_sectors[symbol]
                for symbol in members
                if member_sectors.get(symbol)
            },
        )

    def _screen_equity(self, spec: UniverseSpec) -> tuple[list[str], dict[str, str]]:
        # NOTE: FMP /stock-screener has no historical filtering capability and
        # is a live snapshot. We use it here for broad_equity_screen / sector_screen
        # to produce an approximate universe as of today.
        #
        # If explicit_symbols are provided on a screen-type universe spec, we
        # filter those symbols via profile data instead (per-symbol approach).
        # This avoids issuing a broad screener call when the caller has already
        # narrowed the universe.

        if spec.explicit_symbols:
            return self._filter_by_profiles(spec)

        if self._fmp is None:
            logger.warning(
                "UniverseResolver: fmp_client is None; broad_equity_screen returns empty list. "
                "Pass an FmpClient instance to resolve screener universes."
            )
            return [], {}

        symbols: set[str] = set()
        sector_by_symbol: dict[str, str] = {}
        for exchange in (spec.allowed_exchanges or ["NASDAQ", "NYSE"]):
            params: dict = {
                "exchange": exchange,
                "is_etf": False if spec.exclude_etf else None,
                "limit": 2000,
            }
            if spec.min_market_cap_usd is not None:
                params["market_cap_more_than"] = spec.min_market_cap_usd
            if spec.min_adv_usd is not None:
                params["volume_more_than"] = spec.min_adv_usd
            if spec.price_floor_usd is not None:
                params["price_more_than"] = spec.price_floor_usd

            # sector_screen: if a single sector, pass it directly; multi-sector requires post-filter
            sector_param: str | None = None
            if spec.universe_kind == "sector_screen" and len(spec.sector_include) == 1:
                sector_param = spec.sector_include[0]
            if sector_param:
                params["sector"] = sector_param

            country_param: str | None = None
            if spec.country_iso2 and len(spec.country_iso2) == 1:
                country_param = spec.country_iso2[0]
            if country_param:
                params["country"] = country_param

            try:
                rows = self._fmp.get_screener_results(**params)  # type: ignore[union-attr]
            except Exception as exc:  # noqa: BLE001
                logger.warning("UniverseResolver: screener call failed for exchange %s: %s", exchange, exc)
                continue

            for row in rows:
                symbol = str(row.get("symbol") or "").upper()
                if not symbol:
                    continue
                # Post-filter: sector_include (multi-sector case)
                if spec.universe_kind == "sector_screen" and spec.sector_include and not sector_param:
                    row_sector = str(row.get("sector") or "")
                    if row_sector not in spec.sector_include:
                        continue
                # sector_exclude
                if spec.sector_exclude:
                    row_sector = str(row.get("sector") or "")
                    if row_sector in spec.sector_exclude:
                        continue
                # exclude ADR heuristic: FMP marks type "ADR" or name ends with " ADS"
                if spec.exclude_adr:
                    instrument_type = str(row.get("type") or "").upper()
                    if instrument_type in ("ADR", "ADS"):
                        continue
                symbols.add(symbol)
                row_sector = str(row.get("sector") or "").strip()
                if row_sector:
                    sector_by_symbol[symbol] = row_sector

        return sorted(symbols), sector_by_symbol

    def _resolve_index_constituents(self, spec: UniverseSpec) -> tuple[list[str], dict[str, str]]:
        """Resolve members of a named index. Dispatch by `index_id`:

        - `sp500`: live FMP `/stable/sp500-constituent` (current snapshot only;
          point-in-time historical reconstruction would need the historical endpoint, deferred)
        - `russell1000`: static snapshot file under `data/universe/index_snapshots/russell1000.json`,
          sourced from iShares IWB ETF holdings (no FMP endpoint exists for Russell 1000)

        Optional `sector_include` / `sector_exclude` filters narrow the resolved set
        identically across both paths.
        """
        if spec.index_id is None:
            raise ValueError("index_constituent universe_kind requires index_id")

        rows = self._load_index_constituent_rows(spec.index_id)
        if rows is None:
            # Resolution path emitted its own warning (e.g. fmp_client missing) — return empty
            return [], {}

        symbols: set[str] = set()
        sector_by_symbol: dict[str, str] = {}
        for row in rows:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol:
                continue
            row_sector = str(row.get("sector") or "").strip()
            # Apply optional sector filters from spec (allows narrowing the index by sector)
            if spec.sector_include or spec.sector_exclude:
                if spec.sector_include and row_sector not in spec.sector_include:
                    continue
                if spec.sector_exclude and row_sector in spec.sector_exclude:
                    continue
            symbols.add(symbol)
            if row_sector:
                sector_by_symbol[symbol] = row_sector
        return sorted(symbols), sector_by_symbol

    def _load_index_constituent_rows(self, index_id: str) -> list[dict] | None:
        """Dispatch to the right backend for the given index_id.

        Returns None when the resolver cannot produce rows for known reasons that have
        already been logged (e.g. missing FMP client). Raises for unsupported index_id.
        """
        if index_id == "sp500":
            if self._fmp is None:
                logger.warning(
                    "UniverseResolver: fmp_client is None; sp500 index_constituent returns empty list. "
                    "Pass an FmpClient instance to resolve the live S&P 500 constituent endpoint."
                )
                return None
            try:
                return list(self._fmp.get_sp500_constituents())  # type: ignore[union-attr]
            except Exception as exc:  # noqa: BLE001
                logger.warning("UniverseResolver: sp500 constituent fetch failed: %s", exc)
                return None

        if index_id == "russell1000":
            try:
                return _load_index_snapshot("russell1000")
            except IndexSnapshotError as exc:
                logger.warning(
                    "UniverseResolver: russell1000 static snapshot unavailable: %s", exc
                )
                return None

        raise ValueError(f"Unsupported index_id: {index_id!r}")

    def _filter_by_profiles(self, spec: UniverseSpec) -> tuple[list[str], dict[str, str]]:
        """Filter explicit_symbols through FMP profile data to apply eligibility filters."""
        if self._fmp is None:
            return sorted(set(spec.explicit_symbols)), {}

        eligible: list[str] = []
        sector_by_symbol: dict[str, str] = {}
        for symbol in sorted(set(spec.explicit_symbols)):
            try:
                profiles = self._fmp.get_profile(symbol)  # type: ignore[union-attr]
            except Exception as exc:  # noqa: BLE001
                logger.warning("UniverseResolver: profile fetch failed for %s: %s", symbol, exc)
                eligible.append(symbol)
                continue

            if not profiles:
                eligible.append(symbol)
                continue

            profile = profiles[0]
            mktcap = profile.get("mktCap") or profile.get("marketCap")
            price = profile.get("price")
            exchange = str(profile.get("exchange") or profile.get("exchangeShortName") or "")
            sector = str(profile.get("sector") or "")
            instrument_type = str(profile.get("type") or profile.get("isEtf") or "")
            is_etf = profile.get("isEtf") is True or instrument_type.upper() in ("ETF", "ETN", "FUND")

            if spec.exclude_etf and is_etf:
                continue
            if spec.min_market_cap_usd is not None and mktcap is not None:
                if float(mktcap) < spec.min_market_cap_usd:
                    continue
            if spec.price_floor_usd is not None and price is not None:
                if float(price) < spec.price_floor_usd:
                    continue
            if spec.allowed_exchanges and exchange and exchange not in spec.allowed_exchanges:
                continue
            if spec.universe_kind == "sector_screen" and spec.sector_include:
                if sector not in spec.sector_include:
                    continue
            if spec.sector_exclude and sector in spec.sector_exclude:
                continue

            eligible.append(symbol)
            if sector:
                sector_by_symbol[symbol] = sector

        return eligible, sector_by_symbol
