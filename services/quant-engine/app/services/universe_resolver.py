from __future__ import annotations

import hashlib
import json
import logging

from app.schemas.generic_ranking import UniverseSpec, UniverseSpecSnapshot

logger = logging.getLogger(__name__)


class UniverseResolver:
    def __init__(self, fmp_client: object | None = None) -> None:
        # fmp_client is an instance of FmpClient; typed as object to avoid circular import
        self._fmp = fmp_client

    def resolve(self, spec: UniverseSpec, as_of_date: str) -> UniverseSpecSnapshot:
        if spec.universe_kind in ("etf_peer_group", "custom_list"):
            members = sorted(set(spec.explicit_symbols))
        elif spec.universe_kind in ("broad_equity_screen", "sector_screen"):
            members = self._screen_equity(spec)
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
        )

    def _screen_equity(self, spec: UniverseSpec) -> list[str]:
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
            return []

        symbols: set[str] = set()
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

        return sorted(symbols)

    def _filter_by_profiles(self, spec: UniverseSpec) -> list[str]:
        """Filter explicit_symbols through FMP profile data to apply eligibility filters."""
        if self._fmp is None:
            return sorted(set(spec.explicit_symbols))

        eligible: list[str] = []
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

        return eligible
