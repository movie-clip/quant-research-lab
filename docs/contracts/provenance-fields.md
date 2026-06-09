# Provenance Fields Contract

**Feature:** Portfolio data-sources indicator (Epic 18 / US-18.2)
**Backend schema:** `services/quant-engine/app/schemas/provenance.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `ProvenanceResult`
**Route:** `POST /api/engines/provenance/run`
**Service:** `services/quant-engine/app/services/provenance_engine.py`
**Component:** `apps/desktop/src/features/portfolio/DataSourcesPanel.tsx`
**Last updated:** 2026-06-05

---

## What this is (and isn't)

This contract reports **market-data provenance** — which provider priced each
holding: FMP (primary) vs Yahoo Finance (secondary, via the US-18.1 fallback),
or unpriced. It is a **source label, not a return-basis trust claim.** Yahoo
data is still `verified_adjusted_close` return-basis; the synthetic-history
trust badges remain on the individual analytic cards. No value is fabricated:
a holding with no rows from either provider is `unavailable`, listed separately.

Provider identity is window-independent (FMP 402s a symbol regardless; Yahoo
serves it regardless), so the engine probes a short lookback purely to populate
`MarketDataService.last_fetch_meta` vendor — cached histories make it near-free.

---

## Request: `ProvenanceRequest`

| Field | Backend type | TS type | Description |
|---|---|---|---|
| `snapshot` | `ImportedPortfolioSnapshot` | `ImportedSnapshot` | Full imported portfolio snapshot |
| `lookback_days` | `int` (≥1, default 30) | `number` | Short probe window (trading days); provider identity is window-independent |

---

## Response: `ProvenanceResult`

| Field | Backend type | TS type | UI surface | Nullable |
|---|---|---|---|---|
| `holdings` | `list[HoldingProvenance]` | `HoldingProvenance[]` | (per-symbol detail) | No (may be empty) |
| `fmp_symbols` | `list[str]` | `string[]` | "N via FMP (primary)" line | No (may be empty) |
| `yahoo_sourced_symbols` | `list[str]` | `string[]` | "N via Yahoo Finance (secondary source): …" line | No (may be empty) |
| `unavailable_symbols` | `list[str]` | `string[]` | "N with no price history: …" line | No (may be empty) |
| `identity_warnings` | `list[InstrumentIdentityMismatch]` | `InstrumentIdentityMismatch[]` | "⚠ Possible identity mismatch…" line(s) | No (may be empty) (US-19.1) |
| `lookback_days` | `int` | `number` | (probe window echo) | No |

### `InstrumentIdentityMismatch` (US-19.1)

A registry-known holding whose broker-statement description is identity-disjoint
from the registry fund name (possible ticker→fund mislabel). **Flag only** — never
auto-corrected. Also emitted as the `instrument_description_registry_consistency`
Import Admission check (`warn`/`degraded` when present).

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `symbol` | `str` | `string` | Broker ticker |
| `statement_description` | `str` | `string` | The broker statement's description of the holding |
| `registry_name` | `str` | `string` | The registry's fund name for that ticker |

Detection is conservative: flags only when the two names' normalized significant
tokens are **disjoint** (catches different-issuer mislabels; ignores formatting /
share-class suffix noise). Detector: `app/services/instrument_identity.py`.

### `HoldingProvenance`

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `symbol` | `str` | `string` | Position symbol (as held) |
| `vendor` | `Literal['fmp','yfinance','unavailable']` | `'fmp' \| 'yfinance' \| 'unavailable'` | Which provider answered; `unavailable` = no rows from either |

---

## UI rendering rules (`DataSourcesPanel`)

| Condition | Render |
|---|---|
| No snapshot loaded | Panel not rendered (idle → `null`) |
| All holdings FMP-sourced | Quiet "All N holdings priced via FMP (primary)." |
| ≥ 1 Yahoo-sourced | "◆ N holdings via Yahoo Finance (secondary source): SYM, …" + an FMP-count line |
| ≥ 1 unpriced | "N holdings with no price history: SYM, …" (muted) — never merged into FMP/Yahoo groups |

Source distinction uses a text label (non-color encoder). The panel uses the
Epic 12 design system (tokens only; in the `designSystem.audit.test.ts` set).

---

## Example

```json
{
  "holdings": [
    {"symbol": "AAPL", "vendor": "fmp"},
    {"symbol": "VUAA", "vendor": "yfinance"},
    {"symbol": "NOPE", "vendor": "unavailable"}
  ],
  "fmp_symbols": ["AAPL"],
  "yahoo_sourced_symbols": ["VUAA"],
  "unavailable_symbols": ["NOPE"],
  "lookback_days": 30
}
```
