---
name: fmp-data
description: >
  FMP (Financial Modeling Prep) data provider reference for this project.
  Use when you need to: look up how a symbol is resolved, add support for a
  new ticker, debug missing price history, understand the cache layer, or
  determine why a position has no FMP coverage. Also use when designing
  analytics that require market data to understand what data is available and
  what the trust/availability limitations are.
---

# FMP Data Provider Skill

This skill documents how Financial Modeling Prep (FMP) is integrated into the
quant engine, how symbol resolution works, what the common failure modes are,
and how to add support for new tickers — including European UCITS ETFs that
FMP's basic plan does not cover.

This is a **reference skill**, not a workflow skill. It's read by other skills
(`quant-research` when proposing data dependencies, `build-story` when wiring
a new engine to market data, `verify-story` when debugging market-data mocks)
and by the user directly when something market-data-related is broken.

## Skills that often follow this one

- **quant-research** — if you came here to check data feasibility for a new
  analytic, the brief belongs in quant-research's §2.4 (Data requirements)
- **build-story** — if you came here to wire a new engine, the autouse mocks
  in `conftest.py` will need a sibling for your engine

---

## Architecture overview

```
FmpClient                   ← raw HTTP + caching layer
  └── MarketDataService     ← orchestrated lookups (resolves symbol candidates)
        └── diagnostics / exposure / dashboard engines
```

**FmpClient** (`app/clients/fmp.py`) handles:
- HTTP calls to `https://financialmodelingprep.com/stable/`
- JSON file cache (`data/raw/fmp-cache/`)
- In-flight deduplication (thread-safe)
- Rate-limit enforcement
- Negative caching of 401/402/403/404 responses (stores empty list `[]`)
- Stale cache fallback on transient errors

**MarketDataService** (`app/services/market_data.py`) handles:
- Symbol canonicalization and candidate resolution
- Iterating candidates until one returns data
- Trust/return-basis detection (`detect_history_return_basis`)

**SymbolResolver** (`app/core/symbols.py`) handles:
- Mapping canonical symbols to exchange-suffixed candidates (e.g. VUAA → VUAA.L)
- Proxy candidates for when primary lookups fail
- Symbol aliases

---

## FMP endpoints used

| Method | FMP path | Cache namespace | TTL |
|---|---|---|---|
| `get_quote_short(symbol)` | `quote-short` | `quote` | `fmp_quote_cache_ttl_seconds` |
| `get_historical_price_light(symbol, from, to)` | `historical-price-eod/light` | `history` | `fmp_history_cache_ttl_seconds` |
| `get_profile(symbol)` | `profile` | `profile` | quote TTL |
| `get_etf_holders(symbol)` | `etf-holder/{symbol}` (v3) | `holdings` | history TTL |
| `get_screener_results(...)` | `stock-screener` | `screener` | history TTL |
| `get_income_statements(symbol)` | `income-statement` | `fundamentals` | history TTL |
| `get_balance_sheet_statements(symbol)` | `balance-sheet-statement` | `fundamentals` | history TTL |
| `get_cash_flow_statements(symbol)` | `cash-flow-statement` | `fundamentals` | history TTL |
| `get_ratios_ttm(symbol)` | `ratios-ttm` | `fundamentals` | history TTL |
| `get_key_metrics_ttm(symbol)` | `key-metrics-ttm` | `fundamentals` | history TTL |
| `get_sp500_constituents()` | `sp500-constituent` | `index_constituents` | history TTL |

The `historical-price-eod/light` endpoint returns `adjClose` for US-listed equities
and ETFs. The presence of `adjClose` is what classifies a history as
`verified_adjusted_close`; absence means `unverified_close_only`.

---

## Symbol resolution pipeline

Every market data request goes through this pipeline:

```
requested symbol
    │
    ▼
canonicalize_symbol()          # strips .L/.AS aliases → canonical form
    │
    ▼
resolve_symbol_candidates()    # ordered list of symbols to try
    │
    ├─ override dict provided?  → use override list directly
    ├─ symbol has a rule?       → use rule.quote_candidates / .history_candidates
    └─ no rule                  → [symbol_as_is]
    │
    ▼
FmpClient (try each candidate in order, stop at first non-empty result)
```

**Resolution rules** are defined in `app/core/symbols.py` → `DEFAULT_SYMBOL_RULES`.

Each `SymbolResolutionRule` has:
- `canonical_symbol`: the symbol the engine uses internally (e.g. `"VUAA"`)
- `quote_candidates`: tried for `get_latest_quotes()` and `get_company_profile()`
- `history_candidates`: tried for `get_historical_prices()`
- `holdings_candidates`: tried for `get_etf_holdings()`
- `proxy_candidates`: fallback US-listed proxies, used only when `allow_proxy_fallback=True`
- `aliases`: alternative names that canonicalize to this symbol (e.g. `"VUAA.L"` → `"VUAA"`)

---

## Adding a new ticker

### Step 1 — Add to the instrument registry

Edit `app/instruments/registry.py` → `INSTRUMENT_DEFINITIONS` dict:

```python
"MYSYM": _instrument(
    "etf-mysym",          # unique instrument_id
    "MYSYM",              # canonical symbol
    "My ETF Full Name",   # display name
    "etf",                # asset_class: "equity", "etf", "future", "other"
    "Technology",         # sector (used for sector allocation chart)
    "Thematic UCITS ETF", # category
    "USD",                # native currency
),
```

**Sector values used in this codebase** (use exactly one):
`"Broad Market"`, `"Technology"`, `"Financials"`, `"Health Care"`, `"Energy"`,
`"Defense"`, `"Commodities"`, `"Fixed Income"`, `"Consumer Discretionary"`,
`"Consumer Staples"`, `"Industrials"`, `"Materials"`, `"Real Estate"`,
`"Utilities"`, `"Communication Services"`, `"Other"`

### Step 2 — Add a symbol resolution rule (if needed)

Edit `app/core/symbols.py` → `DEFAULT_SYMBOL_RULES` tuple. A rule is only needed
when the symbol needs exchange-suffix candidates or has proxy fallbacks.

```python
SymbolResolutionRule(
    canonical_symbol="MYSYM",
    quote_candidates=("MYSYM.L", "MYSYM"),   # try London suffix first
    history_candidates=("MYSYM.L", "MYSYM"),
    holdings_candidates=("MYSYM.L", "MYSYM"),
    proxy_candidates=("XLK",),               # US-listed proxy for analytics fallback
    aliases=("MYSYM.L",),                    # so MYSYM.L canonicalizes to MYSYM
),
```

**Exchange suffix conventions:**
| Suffix | Exchange |
|---|---|
| `.L` | London Stock Exchange (LSE / LSEETF) |
| `.AS` | Euronext Amsterdam |
| `.DE` | Deutsche Börse (Xetra) |
| `.MI` | Borsa Italiana (Milan) |
| `.PA` | Euronext Paris |

FMP's basic/starter plan does **not** serve these suffixed symbols — they return
HTTP 402. Only add suffix candidates if you have an FMP plan that covers
international exchanges, or to make the intent clear for future upgrades.

### Step 3 — Verify

```python
from app.core.symbols import resolve_symbol_candidates, resolve_proxy_candidates
from app.instruments.registry import InstrumentRegistry

reg = InstrumentRegistry()
print(reg.get_instrument("MYSYM"))
print(resolve_symbol_candidates("MYSYM", kind="history"))
print(resolve_proxy_candidates("MYSYM"))
```

---

## Cache layer

### Cache file location
`data/raw/fmp-cache/` — JSON files named `{namespace}-{sha256}.json`

Each file contains:
```json
{
  "fetched_at": 1748900000.0,
  "payload": [ { ...row... }, ... ]
}
```

An **empty payload** (`"payload": []`) means a negative cache entry (FMP returned
an error, typically 402). The entry will be returned as a cache hit until it
expires (history TTL), blocking retries.

### Cache management

```bash
# List all cache entries
python scripts/manage_cache.py list

# Clear everything (forces fresh FMP fetch on next engine run)
python scripts/manage_cache.py clear

# Clear only history entries
python scripts/manage_cache.py clear history
```

**In-app (Epic 20 / US-20.1):** `GET /cache/stats` (footprint + per-namespace
counts) and `POST /cache/clear` (`{namespace}` optional; null = all FMP + Yahoo)
back the "Market-data cache" card on the Exposure tab. Service:
`app/services/cache_admin.py`; contract: `docs/contracts/cache-fields.md`.

### Corrupt cache files

If a cache JSON file is malformed (e.g. truncated write), `JsonFileCache.get()`
treats it as a cache miss (`None`) and the caller fetches fresh data. This is
handled by catching `json.JSONDecodeError` in `app/core/cache.py`.

### Negative cache (symbol not found)

When FMP returns 402/401/403/404, the client stores `[]` as the cache entry:
```python
if status_code in {401, 402, 403, 404}:
    self.cache.set(cache_key, [])   # negative cache
```

This means the symbol will appear to return no data on subsequent calls until
the TTL expires. To force a retry:
1. Clear the specific cache file (identify by inspecting `data/raw/fmp-cache/`)
2. Or clear all: `python scripts/manage_cache.py clear`

---

## Subscription tier limitations

FMP's **basic/free plan** covers:
- US-listed equities (NYSE, NASDAQ, AMEX)
- US-listed ETFs (e.g. SPY, QQQ, GLD, XLK, ITA, BIL)
- Major FX pairs

FMP's basic plan does **not** cover:
- European exchange-listed ETFs with `.L`, `.AS`, `.DE`, `.MI` suffixes
- These return **HTTP 402 Payment Required**

> **Multi-provider (Epic 18 / US-18.1):** `MarketDataService` now falls back to
> **Yahoo Finance (`YFinanceClient`, `app/clients/yfinance_client.py`)** when FMP
> returns nothing for a candidate. Yahoo serves most of these UCITS symbols
> (`VUAA.L`, `SXRV.DE`, …) with adjusted close. Provenance is recorded in
> `last_fetch_meta[...]['vendor']` (`fmp`|`yfinance`) and surfaced visibly in the
> UI — it is **not** a proxy substitute (it fetches the real holding). So a
> "no FMP coverage" symbol is no longer automatically "no data". See
> `docs/architecture/system-architecture.md` → "Market-data providers and data
> provenance". The proxy-fallback machinery below is a separate, still-disabled
> mechanism.

### European UCITS ETFs in IB statements (as of 2026)

All 10 of these are LSE/IBIS2-listed and return 402 on FMP basic:

| Symbol | Name | Proxy |
|---|---|---|
| VUAA | Vanguard S&P 500 UCITS ETF | SPY |
| SGLD | Invesco Physical Gold ETC | GLD |
| ICOM | iShares Diversified Commodity Swap UCITS ETF | DBC |
| DFND | iShares Global Aerospace & Defence UCITS ETF (LSE, GBP) | ITA, PPA |  Yahoo line is **DFND.L**. Do **not** use DFNS.L/DFEN.DE/DFNG.L — those are VanEck Defense, a different fund. See US-18.3. |
| VDST | Vanguard USD 0-1 Year Treasury Bond UCITS ETF | BIL, VGSH |
| IUIT | iShares S&P 500 IT Sector UCITS ETF | XLK |
| SEMI | iShares MSCI Global Semiconductors UCITS ETF | SOXX, SMH |
| SXRV | iShares Nasdaq 100 UCITS ETF (EUR, Xetra) | QQQ |
| DEFS | Amundi STOXX Europe Defense UCITS ETF | ITA, PPA |
| IAUP | iShares Gold Producers UCITS ETF | GDX |
| IDFN | Invesco Defence Innovation UCITS ETF | ITA, PPA |

### What "no FMP coverage" means for analytics

When a position has no price history:
- **Sector allocation**: correct (sector comes from `InstrumentRegistry`, not FMP)
- **Factor model**: position is excluded from the regression — the factor loadings
  reflect only positions that have history
- **Rolling risk / beta**: position missing from portfolio return series
- **User sees**: degraded analytics with no per-position explanation (current behaviour)
- **Planned improvement**: position-level data availability indicator

### Proxy fallback (currently not enabled for diagnostics)

`MarketDataService.get_historical_prices()` accepts `allow_proxy_fallback=True`.
When enabled, it appends `proxy_candidates` to the trial list after the primary
candidates. Proxy data would be clearly marked as `unverified_adjusted_proxy`
in the return-basis trust chain.

The diagnostics engine does **not** currently pass `allow_proxy_fallback=True`.
Enabling it is a product decision (it changes the analytical output for UCITS ETFs)
and should be delivered as a dedicated user story that also updates
`docs/finance/financial-methodology.md`.

---

## Trust and return basis

After resolving history rows, `detect_history_return_basis(rows)` classifies:

| Status | Condition | Meaning |
|---|---|---|
| `verified_adjusted_close` | all rows have `adjClose` or `adjusted_close` | Total-return proxy available |
| `unverified_close_only` | rows present but no adjusted close | Price return only — no dividend adjustment |
| `unavailable` | no rows | Position has no price history |

The engine propagates the weakest trust level across all positions via
`detect_histories_return_basis()`. Positions with `unavailable` history degrade
the entire diagnostic result toward `unavailable`.

---

## Debugging FMP issues

### Step 1 — Check what candidates the resolver tries

```python
from app.core.symbols import resolve_symbol_candidates, resolve_proxy_candidates
print(resolve_symbol_candidates("MYSYM", kind="history"))
print(resolve_proxy_candidates("MYSYM"))
```

### Step 2 — Check the cache

```python
from pathlib import Path
import json, hashlib

def cache_key_for(namespace, path, params):
    cache_id = json.dumps({"path": path, "params": params}, sort_keys=True)
    digest = hashlib.sha256(cache_id.encode()).hexdigest()
    return f"{namespace}-{digest}.json"

# e.g. for SGLD.L history 2026-01-08 to 2026-04-30
key = cache_key_for("history", "historical-price-eod/light",
                    {"from": "2026-01-08", "symbol": "SGLD.L", "to": "2026-04-30"})
print(key)
path = Path("data/raw/fmp-cache") / key
print(json.loads(path.read_text()) if path.exists() else "not cached")
```

### Step 3 — Check engine logs

Run the dev server and look for lines like:
```
FMP cache hit [history] {'symbol': 'SPY', ...}
FMP negative cache [quote] {'symbol': 'SGLD.L'} status=402
FMP stale cache fallback [history] {'symbol': 'VUAA.L', ...}
```

`status=402` confirms FMP subscription limit. `status=404` means symbol
genuinely not found. Both produce negative cache entries.

### Step 4 — Run the diagnostics engine directly

```bash
cd services/quant-engine
python -m app.scripts.export_dashboard_goldens   # regenerates, hits FMP where cache misses
```

---

## Common tasks

### "Why does my UCITS ETF show no history?"

1. Check `resolve_symbol_candidates(sym, kind='history')` — what does it try?
2. Check the cache for those candidates — are there negative cache entries (`payload: []`)?
3. If 402: FMP plan doesn't cover international exchanges. Add proxy candidates if
   wanted (then open a story to enable proxy fallback in the diagnostics engine).
4. If 404: Symbol genuinely not on FMP even with paid plan. Proxy fallback is the
   only option.

### "How do I add a new broker statement ticker?"

Follow "Adding a new ticker" above. Check if the symbol is:
- US-listed → just add to registry; FMP will likely find it directly
- European-listed → add to registry + add a resolution rule with `.L`/`.AS`/`.DE`
  candidates and meaningful proxy candidates

### "How do I look up what FMP returns for a symbol?"

```bash
cd services/quant-engine
python -c "
from app.clients.fmp import FmpClient
c = FmpClient()
# Quote:
print(c.get_quote_short('SPY'))
# History:
print(c.get_historical_price_light('SPY', '2025-01-01', '2025-01-31')[:3])
# ETF holdings:
print(c.get_etf_holders('SPY')[:3])
"
```

Results are cached automatically; clear the cache if you want a live fetch.

### "The sector allocation shows 27% Other — why?"

The `"Other"` bucket means positions whose sector lookup returned `"Other"`.
This happens when:
- The symbol is not in `INSTRUMENT_DEFINITIONS` AND
- `classify_imported_instrument` can't determine sector from the IB description

Fix: add the symbol to `INSTRUMENT_DEFINITIONS` with the correct sector.

---

## What this skill does NOT cover

- Financial formulas and methodology → see `docs/finance/financial-methodology.md`
- How to interpret factor loadings or risk metrics → see `docs/finance/financial-methodology.md`
- Portfolio construction or optimizer logic → out of scope for FMP skill
- Writing stories → use the `write-story` skill
- Building stories → use the `build-story` skill
