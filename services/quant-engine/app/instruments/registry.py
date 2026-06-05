from __future__ import annotations

from datetime import date
from typing import cast

from app.core.symbols import canonicalize_symbol
from app.schemas.imports import ImportedInstrument, ImportedPortfolioSnapshot
from app.schemas.instruments import AssetClass, FuturesContract, Instrument, InstrumentKind


def _instrument(
    instrument_id: str,
    symbol: str,
    name: str,
    asset_class: AssetClass,
    sector: str,
    category: str,
    currency: str,
    *,
    exchange: str | None = None,
    kind: InstrumentKind = "spot",
    tick_size: float | None = None,
    point_value: float | None = None,
    multiplier: float | None = None,
) -> Instrument:
    return Instrument(
        instrument_id=instrument_id,
        symbol=symbol,
        name=name,
        asset_class=cast(AssetClass, asset_class),
        kind=cast(InstrumentKind, kind),
        sector=sector,
        category=category,
        exchange=exchange,
        currency=currency,
        tick_size=tick_size,
        point_value=point_value,
        multiplier=multiplier,
    )


INSTRUMENT_DEFINITIONS: dict[str, Instrument] = {
    "ES": _instrument("future-root-es", "ES", "E-mini S&P 500", "future", "Equity Index", "Futures", "USD", exchange="CME", kind="continuous_future", tick_size=0.25, point_value=50.0, multiplier=50.0),
    "NQ": _instrument("future-root-nq", "NQ", "E-mini Nasdaq 100", "future", "Equity Index", "Futures", "USD", exchange="CME", kind="continuous_future", tick_size=0.25, point_value=20.0, multiplier=20.0),
    "CL": _instrument("future-root-cl", "CL", "Crude Oil", "future", "Energy", "Futures", "USD", exchange="NYMEX", kind="continuous_future", tick_size=0.01, point_value=1000.0, multiplier=1000.0),
    "GC": _instrument("future-root-gc", "GC", "Gold", "future", "Metals", "Futures", "USD", exchange="COMEX", kind="continuous_future", tick_size=0.1, point_value=100.0, multiplier=100.0),
    "GOOG": _instrument("equity-goog", "GOOG", "Alphabet Class C", "equity", "Communication Services", "Equity", "USD"),
    "AAPL": _instrument("equity-aapl", "AAPL", "Apple", "equity", "Technology", "Equity", "USD"),
    "ADBE": _instrument("equity-adbe", "ADBE", "Adobe", "equity", "Technology", "Equity", "USD"),
    "ASML": _instrument("equity-asml", "ASML", "ASML", "equity", "Technology", "Equity", "USD"),
    "ACN": _instrument("equity-acn", "ACN", "Accenture", "equity", "Technology", "Equity", "USD"),
    "CRM": _instrument("equity-crm", "CRM", "Salesforce", "equity", "Technology", "Equity", "USD"),
    "DOCN": _instrument("equity-docn", "DOCN", "DigitalOcean", "equity", "Technology", "Equity", "USD"),
    "FICO": _instrument("equity-fico", "FICO", "Fair Isaac", "equity", "Financials", "Equity", "USD"),
    "NICE": _instrument("equity-nice", "NICE", "NICE", "equity", "Technology", "Equity", "USD"),
    "ZM": _instrument("equity-zm", "ZM", "Zoom", "equity", "Technology", "Equity", "USD"),
    "MSFT": _instrument("equity-msft", "MSFT", "Microsoft", "equity", "Technology", "Equity", "USD"),
    "NVDA": _instrument("equity-nvda", "NVDA", "NVIDIA", "equity", "Technology", "Equity", "USD"),
    "GOOGL": _instrument("equity-googl", "GOOGL", "Alphabet", "equity", "Communication Services", "Equity", "USD"),
    "META": _instrument("equity-meta", "META", "Meta Platforms", "equity", "Communication Services", "Equity", "USD"),
    "AMZN": _instrument("equity-amzn", "AMZN", "Amazon", "equity", "Consumer Discretionary", "Equity", "USD"),
    "MA": _instrument("equity-ma", "MA", "Mastercard", "equity", "Financials", "Equity", "USD"),
    "LYFT": _instrument("equity-lyft", "LYFT", "Lyft", "equity", "Consumer Discretionary", "Equity", "USD"),
    "TXRH": _instrument("equity-txrh", "TXRH", "Texas Roadhouse", "equity", "Consumer Discretionary", "Equity", "USD"),
    "UBER": _instrument("equity-uber", "UBER", "Uber", "equity", "Industrials", "Equity", "USD"),
    "BRK": _instrument("equity-brk", "BRK", "Berkshire Hathaway", "equity", "Financials", "Equity", "USD"),
    "BRK-B": _instrument("equity-brkb", "BRK-B", "Berkshire Hathaway B", "equity", "Financials", "Equity", "USD"),
    "SPGI": _instrument("equity-spgi", "SPGI", "S&P Global", "equity", "Financials", "Equity", "USD"),
    "MCO": _instrument("equity-mco", "MCO", "Moody's", "equity", "Financials", "Equity", "USD"),
    "TROW": _instrument("equity-trow", "TROW", "T Rowe Price", "equity", "Financials", "Equity", "USD"),
    "EFX": _instrument("equity-efx", "EFX", "Equifax", "equity", "Financials", "Equity", "USD"),
    "CPRT": _instrument("equity-cprt", "CPRT", "Copart", "equity", "Industrials", "Equity", "USD"),
    "JPM": _instrument("equity-jpm", "JPM", "JPMorgan Chase", "equity", "Financials", "Equity", "USD"),
    "XOM": _instrument("equity-xom", "XOM", "Exxon Mobil", "equity", "Energy", "Equity", "USD"),
    "CVX": _instrument("equity-cvx", "CVX", "Chevron", "equity", "Energy", "Equity", "USD"),
    "EQNR": _instrument("equity-eqnr", "EQNR", "Equinor", "equity", "Energy", "Equity", "USD"),
    "UNH": _instrument("equity-unh", "UNH", "UnitedHealth", "equity", "Health Care", "Equity", "USD"),
    "JNJ": _instrument("equity-jnj", "JNJ", "Johnson & Johnson", "equity", "Health Care", "Equity", "USD"),
    "VRTX": _instrument("equity-vrtx", "VRTX", "Vertex Pharmaceuticals", "equity", "Health Care", "Equity", "USD"),
    "NVO": _instrument("equity-nvo", "NVO", "Novo Nordisk", "equity", "Health Care", "Equity", "USD"),
    "CRSP": _instrument("equity-crsp", "CRSP", "CRISPR Therapeutics", "equity", "Health Care", "Equity", "USD"),
    "EDIT": _instrument("equity-edit", "EDIT", "Editas Medicine", "equity", "Health Care", "Equity", "USD"),
    "ALLO": _instrument("equity-allo", "ALLO", "Allogene Therapeutics", "equity", "Health Care", "Equity", "USD"),
    "PG": _instrument("equity-pg", "PG", "Procter & Gamble", "equity", "Consumer Staples", "Equity", "USD"),
    "KO": _instrument("equity-ko", "KO", "Coca-Cola", "equity", "Consumer Staples", "Equity", "USD"),
    "ADM": _instrument("equity-adm", "ADM", "Archer-Daniels-Midland", "equity", "Consumer Staples", "Equity", "USD"),
    "NEE": _instrument("equity-nee", "NEE", "NextEra Energy", "equity", "Utilities", "Equity", "USD"),
    "CAT": _instrument("equity-cat", "CAT", "Caterpillar", "equity", "Industrials", "Equity", "USD"),
    "BA": _instrument("equity-ba", "BA", "Boeing", "equity", "Industrials", "Equity", "USD"),
    "LIN": _instrument("equity-lin", "LIN", "Linde", "equity", "Materials", "Equity", "USD"),
    "VALE": _instrument("equity-vale", "VALE", "Vale", "equity", "Materials", "Equity", "USD"),
    "NTR": _instrument("equity-ntr", "NTR", "Nutrien", "equity", "Materials", "Equity", "USD"),
    "PLD": _instrument("equity-pld", "PLD", "Prologis", "equity", "Real Estate", "Equity", "USD"),
    "VNQ": _instrument("etf-vnq", "VNQ", "Vanguard Real Estate ETF", "etf", "Real Estate", "ETF", "USD"),
    # Common US-listed broad-market / sector / benchmark ETFs. Without explicit
    # entries here, `get_sector(symbol)` returns "Other" because neither the
    # ticker-only description from Freedom24 nor the static asset_type from
    # Interactive Brokers reliably triggers the description-based ETF
    # classification in `classify_imported_instrument`.
    "SPY": _instrument("etf-spy", "SPY", "SPDR S&P 500 ETF Trust", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "VOO": _instrument("etf-voo", "VOO", "Vanguard S&P 500 ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "IVV": _instrument("etf-ivv", "IVV", "iShares Core S&P 500 ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "VTI": _instrument("etf-vti", "VTI", "Vanguard Total Stock Market ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "VT": _instrument("etf-vt", "VT", "Vanguard Total World Stock ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "VEA": _instrument("etf-vea", "VEA", "Vanguard FTSE Developed Markets ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "VWO": _instrument("etf-vwo", "VWO", "Vanguard FTSE Emerging Markets ETF", "etf", "Broad Market", "Broad Market ETF", "USD"),
    "QQQ": _instrument("etf-qqq", "QQQ", "Invesco QQQ Trust", "etf", "Technology", "Thematic ETF", "USD"),
    "GLD": _instrument("etf-gld", "GLD", "SPDR Gold Shares", "etf", "Commodities", "Commodity ETF", "USD"),
    "SLV": _instrument("etf-slv", "SLV", "iShares Silver Trust", "etf", "Commodities", "Commodity ETF", "USD"),
    "IEF": _instrument("etf-ief", "IEF", "iShares 7-10 Year Treasury Bond ETF", "etf", "Fixed Income", "Bond ETF", "USD"),
    "TLT": _instrument("etf-tlt", "TLT", "iShares 20+ Year Treasury Bond ETF", "etf", "Fixed Income", "Bond ETF", "USD"),
    "AGG": _instrument("etf-agg", "AGG", "iShares Core US Aggregate Bond ETF", "etf", "Fixed Income", "Bond ETF", "USD"),
    "BND": _instrument("etf-bnd", "BND", "Vanguard Total Bond Market ETF", "etf", "Fixed Income", "Bond ETF", "USD"),
    "VUAA": _instrument("etf-vuaa", "VUAA", "Vanguard S&P 500 UCITS ETF", "etf", "Broad Market", "Broad Market UCITS ETF", "USD"),
    "SXRV": _instrument("etf-sxrv", "SXRV", "iShares Nasdaq 100 UCITS ETF", "etf", "Technology", "Thematic UCITS ETF", "EUR"),
    "ISLN": _instrument("etf-isln", "ISLN", "iShares Physical Silver ETC", "etf", "Commodities", "Commodity UCITS ETF", "USD"),
    "SGLD": _instrument("etf-sgld", "SGLD", "Invesco Physical Gold ETC", "etf", "Commodities", "Commodity UCITS ETF", "USD"),
    "ICOM": _instrument("etf-icom", "ICOM", "iShares Diversified Commodity Swap UCITS ETF", "etf", "Commodities", "Commodity UCITS ETF", "USD"),
    "DFND": _instrument("etf-dfnd", "DFND", "iShares Global Aerospace & Defence UCITS ETF", "etf", "Defense", "Thematic UCITS ETF", "GBP"),
    "BTEC": _instrument("etf-btec", "BTEC", "iShares Nasdaq US Biotechnology UCITS ETF", "etf", "Health Care", "Sector UCITS ETF", "USD"),
    "IUFS": _instrument("etf-iufs", "IUFS", "iShares S&P 500 Financials Sector UCITS ETF", "etf", "Financials", "Sector UCITS ETF", "USD"),
    "IUHC": _instrument("etf-iuhc", "IUHC", "iShares S&P 500 Health Care Sector UCITS ETF", "etf", "Health Care", "Sector UCITS ETF", "USD"),
    "IUIT": _instrument("etf-iuit", "IUIT", "iShares S&P 500 Information Technology Sector UCITS ETF", "etf", "Technology", "Sector UCITS ETF", "USD"),
    "SEMI": _instrument("etf-semi", "SEMI", "iShares MSCI Global Semiconductors UCITS ETF", "etf", "Technology", "Thematic UCITS ETF", "GBP"),
    # European UCITS ETFs present in IB statements but without a direct FMP price feed.
    # Sector and category are assigned explicitly here to avoid relying on description parsing.
    "DEFS": _instrument("etf-defs", "DEFS", "Amundi STOXX Europe Defense UCITS ETF", "etf", "Defense", "Thematic UCITS ETF", "USD"),
    "IAUP": _instrument("etf-iaup", "IAUP", "iShares Gold Producers UCITS ETF", "etf", "Commodities", "Commodity UCITS ETF", "USD"),
    "IDFN": _instrument("etf-idfn", "IDFN", "Invesco Defence Innovation UCITS ETF", "etf", "Defense", "Thematic UCITS ETF", "USD"),
    "VDST": _instrument("etf-vdst", "VDST", "Vanguard USD 0-1 Year Treasury Bond UCITS ETF", "etf", "Fixed Income", "Bond UCITS ETF", "USD"),
    "COPX": _instrument("etf-copx", "COPX", "Global X Copper Miners ETF", "etf", "Commodities", "Thematic ETF", "USD"),
    "HOOD": _instrument("equity-hood", "HOOD", "Robinhood Markets", "equity", "Financials", "Equity", "USD"),
    "TSM": _instrument("equity-tsm", "TSM", "Taiwan Semiconductor", "equity", "Technology", "Equity", "USD"),
    "DUOL": _instrument("equity-duol", "DUOL", "Duolingo", "equity", "Communication Services", "Equity", "USD"),
    "NFLX": _instrument("equity-nflx", "NFLX", "Netflix", "equity", "Communication Services", "Equity", "USD"),
    "TW": _instrument("equity-tw", "TW", "Tradeweb", "equity", "Financials", "Equity", "USD"),
    "PYPL": _instrument("equity-pypl", "PYPL", "PayPal", "equity", "Financials", "Equity", "USD"),
    "ACOMO": _instrument("equity-acomo", "ACOMO", "Acomo", "equity", "Consumer Staples", "Equity", "EUR"),
}


class InstrumentRegistry:
    def __init__(self) -> None:
        self._instruments: dict[str, Instrument] = INSTRUMENT_DEFINITIONS.copy()

    def normalize_symbol(self, symbol: str) -> str:
        normalized = canonicalize_symbol(symbol).replace(".L", "").replace(".AS", "").replace("/", "-").strip().upper()
        normalized = "-".join(normalized.split())
        return normalized

    def get_instrument(self, symbol: str) -> Instrument | None:
        normalized = self.normalize_symbol(symbol)
        return self._instruments.get(normalized)

    def list_instruments(self, symbols: list[str]) -> list[Instrument]:
        return [instrument for symbol in symbols if (instrument := self.get_instrument(symbol)) is not None]

    def build_front_contract(self, root_symbol: str, contract_symbol: str, expiry_date: str) -> FuturesContract | None:
        instrument = self.get_instrument(root_symbol)
        if instrument is None or instrument.exchange is None or instrument.currency is None:
            return None

        return FuturesContract(
            instrument_id=f"{instrument.instrument_id}:{contract_symbol}",
            root_symbol=self.normalize_symbol(root_symbol),
            contract_symbol=contract_symbol.upper(),
            exchange=instrument.exchange,
            currency=instrument.currency,
            expiry_date=date.fromisoformat(expiry_date),
            tick_size=instrument.tick_size,
            point_value=instrument.point_value,
            multiplier=instrument.multiplier,
        )

    def get_sector(self, symbol: str) -> str:
        instrument = self.get_instrument(symbol)
        return instrument.sector if instrument and instrument.sector else "Other"

    def _merge_known_instrument_metadata(
        self,
        instrument: Instrument,
        imported: ImportedInstrument | None,
        currency: str | None,
    ) -> Instrument:
        updates: dict[str, str | None] = {}
        if imported is not None:
            if imported.description:
                updates["name"] = imported.description.strip()
            if imported.listing_exchange:
                updates["exchange"] = imported.listing_exchange
        if currency:
            updates["currency"] = currency
        return instrument.model_copy(update=updates) if updates else instrument

    def classify_imported_instrument(self, imported: ImportedInstrument, currency: str | None = None) -> Instrument:
        symbol = self.normalize_symbol(imported.symbol)
        description = (imported.description or symbol).strip()
        description_upper = description.upper()
        instrument_type = (imported.instrument_type or "").upper()
        listing_exchange = (imported.listing_exchange or "").upper()
        resolved_currency = currency or imported.currency or "USD"

        if instrument_type == "ETF" or listing_exchange == "LSEETF" or "UCITS" in description_upper or "ETF" in description_upper or "ETC" in description_upper:
            sector = "Broad Market"
            category = "ETF"

            if listing_exchange == "LSEETF" or "UCITS" in description_upper:
                category = "UCITS ETF"
            if "COMMOD" in description_upper or "GOLD" in description_upper or "SILVER" in description_upper or "PRECIOUS" in description_upper:
                sector = "Commodities"
                category = "Commodity UCITS ETF" if category == "UCITS ETF" else "Commodity ETF"
            elif "AEROSPACE" in description_upper or "DEF" in description_upper:
                sector = "Defense"
                category = "Thematic UCITS ETF" if category == "UCITS ETF" else "Thematic ETF"
            elif "INFORMATION TECHNOLOGY" in description_upper or "INFO TECH" in description_upper or " IT SECTOR" in description_upper:
                sector = "Technology"
                category = "Sector UCITS ETF" if category == "UCITS ETF" else "Sector ETF"
            elif "SEMIC" in description_upper or "SEMICONDUCT" in description_upper:
                sector = "Technology"
                category = "Thematic UCITS ETF" if category == "UCITS ETF" else "Thematic ETF"
            elif "FINANCIAL" in description_upper:
                sector = "Financials"
                category = "Sector UCITS ETF" if category == "UCITS ETF" else "Sector ETF"
            elif "HEALTH CARE" in description_upper or "HEALTHCARE" in description_upper:
                sector = "Health Care"
                category = "Sector UCITS ETF" if category == "UCITS ETF" else "Sector ETF"
            elif "BIOTECH" in description_upper:
                sector = "Health Care"
                category = "Sector UCITS ETF" if category == "UCITS ETF" else "Sector ETF"
            elif "TREAS" in description_upper or "TRBD" in description_upper or "BOND" in description_upper:
                sector = "Fixed Income"
                category = "Bond UCITS ETF" if category == "UCITS ETF" else "Bond ETF"
            elif ("NASDAQ" in description_upper and "100" in description_upper) or "QQQ" in description_upper:
                sector = "Technology"
                category = "Thematic UCITS ETF" if category == "UCITS ETF" else "Thematic ETF"
            elif "S&P500" in description_upper or "S&P 500" in description_upper:
                sector = "Broad Market"
                category = "Broad Market UCITS ETF" if category == "UCITS ETF" else "Broad Market ETF"

            return _instrument(
                f"imported-etf-{symbol.lower()}",
                symbol,
                description,
                "etf",
                sector,
                category,
                resolved_currency,
                exchange=imported.listing_exchange,
            )

        return _instrument(
            f"imported-equity-{symbol.lower()}",
            symbol,
            description,
            "equity",
            "Other",
            "Equity",
            resolved_currency,
            exchange=imported.listing_exchange,
        )

    def attach_snapshot_metadata(self, snapshot: ImportedPortfolioSnapshot) -> dict[str, Instrument]:
        metadata: dict[str, Instrument] = {}
        imported_by_symbol = {
            self.normalize_symbol(instrument.symbol): instrument
            for instrument in snapshot.instruments
        }

        for position in snapshot.positions:
            imported_instrument = imported_by_symbol.get(self.normalize_symbol(position.symbol))
            imported_exchange = (imported_instrument.listing_exchange or "").upper() if imported_instrument else ""
            imported_type = (imported_instrument.instrument_type or "").upper() if imported_instrument else ""
            instrument = self.get_instrument(position.symbol)

            if instrument is not None:
                metadata[position.symbol] = self._merge_known_instrument_metadata(
                    instrument,
                    imported_instrument,
                    position.currency,
                )
                continue

            if imported_instrument is not None and (imported_type == "ETF" or imported_exchange == "LSEETF"):
                metadata[position.symbol] = self.classify_imported_instrument(imported_instrument, currency=position.currency)
                continue

            if imported_instrument is not None:
                metadata[position.symbol] = self.classify_imported_instrument(imported_instrument, currency=position.currency)
                continue

            metadata[position.symbol] = Instrument(
                instrument_id=f"snapshot:{self.normalize_symbol(position.symbol)}",
                symbol=position.symbol,
                name=position.symbol,
                asset_class="other",
                kind="spot",
                sector="Other",
                category="Imported Position",
                currency=position.currency,
            )

        return metadata
