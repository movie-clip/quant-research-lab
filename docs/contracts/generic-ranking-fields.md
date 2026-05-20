# Generic Ranking Field Inventory

This document captures the current backend contract for the generic ranking feature: request inputs, scoring configuration, persisted artifact payloads, per-instrument row shapes, and recent-run discovery rows.

Authoritative source of truth:
- Backend Pydantic schemas: `services/quant-engine/app/schemas/generic_ranking.py`
- TypeScript types: `apps/desktop/src/features/generic-ranking/types.ts`

## `GenericRankingRequest`

Fields sent by the desktop to the ranking engine.

- `universe_spec`
  - type: `UniverseSpec` (object)
  - universe definition: kind, membership, and screener eligibility filters
- `score_config`
  - type: `ScoreConfig` (object)
  - scoring methodology: normalization, winsorization, and factor weights
- `benchmark_symbol`
  - type: `string`
  - default: `SPY`
  - benchmark used for benchmark-relative comparisons
- `lookback_months`
  - type: `number` (integer, 1–60)
  - default: `6`
  - ranking lookback window in months
- `prefer_live_data`
  - type: `boolean`
  - default: `false`
  - when true the engine prefers live intraday quotes over prior-close data

## `UniverseSpec`

Universe definition — 14 fields total.

- `universe_id`
  - type: `string`
  - stable identifier for the universe (e.g. `broad_us_equity`, `tech_sector`, `custom`)
- `universe_kind`
  - type: `UniverseKind` — `'etf_peer_group' | 'custom_list' | 'broad_equity_screen' | 'sector_screen'`
  - determines how universe membership is resolved
- `universe_label`
  - type: `string | null`
  - optional human-readable display label
- `explicit_symbols`
  - type: `string[]`
  - required when `universe_kind` is `etf_peer_group` or `custom_list`
  - explicit instrument membership list
- `min_market_cap_usd`
  - type: `number | null`
  - screener minimum market cap in USD (e.g. `300000000`)
  - applicable to `broad_equity_screen` and `sector_screen`
- `min_adv_usd`
  - type: `number | null`
  - screener minimum average daily dollar volume in USD
- `price_floor_usd`
  - type: `number | null`
  - screener minimum price in USD (e.g. `1.0`)
- `allowed_exchanges`
  - type: `string[]`
  - default: `["NASDAQ", "NYSE", "NYSE AMERICAN"]`
  - screener exchange allowlist
- `sector_include`
  - type: `string[]`
  - GICS sectors to keep; used by `sector_screen`
- `sector_exclude`
  - type: `string[]`
  - GICS sectors to drop
- `country_iso2`
  - type: `string[]`
  - default: `["US"]`
  - ISO 3166-1 alpha-2 country codes for screener filtering
- `exclude_etf`
  - type: `boolean`
  - default: `true`
  - when true, instruments identified as ETFs are excluded from screener results
- `exclude_adr`
  - type: `boolean`
  - default: `true`
  - when true, American Depositary Receipts are excluded from screener results

Validation rules:
- `universe_kind` of `etf_peer_group` or `custom_list` requires `explicit_symbols` to be non-empty; the backend enforces this at request time

## `ScoreConfig`

Composite score methodology definition.

- `score_config_id`
  - type: `string`
  - stable methodology identifier (e.g. `equity_momentum_v1`, `etf_momentum_v1`)
- `score_config_version`
  - type: `string`
  - default: `v1`
  - version label for the score config
- `normalization`
  - type: `NormalizationMethod` — `'cross_sectional_zscore' | 'percentile_rank' | 'minmax'`
  - default: `cross_sectional_zscore`
  - cross-sectional normalization method applied before weighting
- `winsorize_pct`
  - type: `number` (0.0–0.5)
  - default: `0.05`
  - fraction of the distribution to winsorize before normalization
- `factors`
  - type: `FactorConfig[]`
  - one entry per scoring factor; factor weights must sum to a positive value

## `FactorConfig`

Per-factor scoring definition nested inside `ScoreConfig.factors[]`.

- `factor_id`
  - type: `string`
  - stable factor identifier (e.g. `momentum_6_1`, `realized_volatility_126d`)
- `family`
  - type: `FactorFamily` — `'momentum' | 'volatility' | 'liquidity' | 'quality' | 'value' | 'sentiment'`
  - factor family group used for display and interpretation
- `direction`
  - type: `'higher_is_better' | 'lower_is_better'`
  - scoring direction; controls sign-flip before composite aggregation
- `weight`
  - type: `number` (≥ 0)
  - raw factor weight; normalized server-side relative to other factor weights
- `lookback_days`
  - type: `number | null`
  - lookback window in calendar days for price-based factors; `null` for non-price factors
- `raw_unit`
  - type: `string`
  - default: `score`
  - unit label for the raw factor value (e.g. `pct`, `volume`, `score`)

## `GenericRankingArtifact`

Full persisted artifact returned from a ranking run. Extends `GenericRankingResponse` with `schema_version` and `artifact_id`.

- `schema_version`
  - type: `'generic_ranking_artifact_v1'`
  - fixed literal; current schema version
- `artifact_id`
  - type: `string`
  - stable persisted artifact identity; always starts with `generic_ranking_artifact_`
- `ranking_id`
  - type: `string`
  - run-scoped ranking identity
- `methodology_id`
  - type: `string`
  - stable methodology identifier for audit and downstream handoffs
- `title`
  - type: `string`
  - human-readable title for display
- `as_of_date`
  - type: `string` (ISO date)
  - date basis used for the ranking output
- `benchmark_symbol`
  - type: `string`
  - benchmark used for this ranking run
- `lookback_months`
  - type: `number`
  - lookback window actually applied
- `universe_spec_snapshot`
  - type: `UniverseSpecSnapshot` (object)
  - resolved universe state captured at run time
- `run_metadata`
  - type: `GenericRankingRunMetadata` (object)
  - run-basis audit metadata including scoring provenance and normalization trace
- `ranked_universe`
  - type: `GenericRankingRow[]`
  - eligible instruments ranked by composite score after normalization and weighting
- `excluded_instruments`
  - type: `GenericRankingExcludedInstrument[]`
  - instruments that failed hard eligibility filters; never silently dropped
- `warnings`
  - type: `string[]`
  - non-fatal contract metadata for interpreting ranking quality

### `UniverseSpecSnapshot` (nested in artifact)

Resolved universe state captured at run time.

- `spec_version`
  - type: `string`
  - current value: `universe_spec_v1`
- `universe_id`
  - type: `string`
- `universe_kind`
  - type: `string`
- `spec_digest`
  - type: `string`
  - SHA-256 of the canonical `UniverseSpec` JSON
- `evaluated_members`
  - type: `string[]`
  - resolved and sorted symbol list as of `as_of_date`
- `evaluated_at`
  - type: `string` (ISO date)
  - date the universe was resolved
- `member_sectors`
  - type: `Record<string, string>` (`symbol -> GICS sector`)
  - populated by the universe resolver for `broad_equity_screen` / `sector_screen` / `index_constituent` universes; empty for `etf_peer_group` / `custom_list` (no sector source is consulted)
  - additive-optional (default `{}`) so prior persisted artifacts still load
  - consumed downstream by the construction `max_sector_weight` hard constraint

### `GenericRankingRunMetadata` (nested in artifact)

Run-basis audit metadata.

- `ranking_id`
  - type: `string`
- `methodology_id`
  - type: `string`
- `as_of_date`
  - type: `string` (ISO date)
- `ranking_basis_date`
  - type: `string` (ISO date)
  - currently the same as `as_of_date`; split so later contracts can evolve without reinterpreting `as_of_date`
- `price_basis`
  - type: `string`
  - current value: `close`
- `confidence`
  - type: `'full' | 'partial' | 'degraded'`
  - explicit audit-level ranking confidence
- `score_config_ref`
  - type: `ScoreConfigRef` (object)
  - compact reference to the scoring methodology used
- `composite_score_trace`
  - type: `CompositeScoreTrace | null`
  - normalization statistics captured at scoring time; `null` when trace is unavailable

### `ScoreConfigRef` (nested in run_metadata)

Compact scoring methodology reference stored in the artifact for audit.

- `score_config_id`
  - type: `string`
- `score_config_version`
  - type: `string`
- `score_config_digest`
  - type: `string`
  - SHA-256 of the canonical `ScoreConfig` JSON
- `factor_ids`
  - type: `string[]`
  - ordered list of factor identifiers used in this run
- `normalization`
  - type: `string`
- `winsorize_pct`
  - type: `number`

### `CompositeScoreTrace` (nested in run_metadata)

Cross-sectional normalization statistics captured at scoring time.

- `normalization_method`
  - type: `string`
  - normalization method applied (mirrors `ScoreConfig.normalization`)
- `winsorize_pct`
  - type: `number`
  - winsorization fraction applied
- `universe_size_at_normalization`
  - type: `number` (integer)
  - number of instruments in the cross-section when normalization was computed
- `cross_sectional_mean`
  - type: `Record<string, number>` (factor_id → mean)
  - per-factor cross-sectional means before normalization
- `cross_sectional_std`
  - type: `Record<string, number>` (factor_id → std)
  - per-factor cross-sectional standard deviations before normalization

## `GenericRankingRow`

One ranked instrument row inside `GenericRankingArtifact.ranked_universe[]`.

- `rank`
  - type: `number` (integer)
  - 1-based rank position; rank 1 is the top-ranked instrument
- `symbol`
  - type: `string`
  - instrument ticker symbol (uppercase-normalized)
- `composite_score`
  - type: `number`
  - weighted composite score after normalization
- `component_scores`
  - type: `Record<string, GenericRankingComponentScore>`
  - per-factor score breakdown keyed by `factor_id`
- `eligibility`
  - type: `EligibilityRecord`
  - eligibility evaluation result for this instrument
- `sector`
  - type: `string | null`
  - GICS sector for the symbol, copied from `UniverseSpecSnapshot.member_sectors` at run time; `null` when the resolved universe carried no sector for this symbol
  - additive-optional (default `null`) so prior persisted artifacts still load
  - threaded into the construction ranked-candidate contract to evaluate `max_sector_weight`

### `GenericRankingComponentScore` (nested in row)

Per-factor scoring detail for one ranked instrument.

- `label`
  - type: `string`
  - human-readable factor label
- `family`
  - type: `FactorFamily`
- `direction`
  - type: `'higher_is_better' | 'lower_is_better'`
- `raw_value`
  - type: `number | null`
  - raw factor value before normalization; `null` when unavailable
- `raw_unit`
  - type: `string`
  - unit of the raw value (e.g. `pct`, `volume`, `score`)
- `normalized_score`
  - type: `number | null`
  - cross-sectionally normalized score; `null` when unavailable
- `normalization_method`
  - type: `string`
  - normalization method applied for this factor
- `weight`
  - type: `number`
  - raw weight for this factor (not yet normalized to sum-to-one)
- `weighted_score`
  - type: `number | null`
  - `normalized_score * weight`; `null` when `normalized_score` is `null`

## `EligibilityRecord`

Eligibility evaluation result attached to both ranked and excluded instruments.

- `eligibility_status`
  - type: `'eligible' | 'excluded'`
  - final eligibility determination
- `hard_filter_failures`
  - type: `string[]`
  - names of hard filters that this instrument failed; non-empty when `eligibility_status = 'excluded'`
  - instruments with any hard filter failure are moved to `excluded_instruments` and are never ranked
- `soft_filter_flags`
  - type: `string[]`
  - names of soft filters that flagged this instrument; does not exclude but may appear in warnings

## `GenericRankingArtifactRecentRow`

Catalog/recent discovery row shape returned by the recent-run listing endpoint. Contains lightweight run identity and metadata only; does not include the full ranked payload.

- `artifact_id`
  - type: `string`
  - stable persisted artifact identity
- `ranking_id`
  - type: `string`
- `methodology_id`
  - type: `string`
- `as_of_date`
  - type: `string` (ISO date)
- `ranking_basis_date`
  - type: `string` (ISO date)
- `benchmark_symbol`
  - type: `string`
- `lookback_months`
  - type: `number` (integer)
- `universe_id`
  - type: `string`
- `universe_kind`
  - type: `string`
- `score_config_id`
  - type: `string`
- `evaluated_universe_size`
  - type: `number` (integer)
  - number of instruments in the evaluated universe for this run
- `confidence`
  - type: `'full' | 'partial' | 'degraded'`
  - ranking confidence level for quick filtering and display

## Phase 2 additions

### Universe kinds

- `index_constituent` — resolved by index_id. Requires `index_id` field on the spec.

### IndexId

- `'sp500'` — current S&P 500 membership resolved live via FMP `/stable/sp500-constituent` (point-in-time historical reconstruction deferred to a future phase)
- `'russell1000'` — Russell 1000 membership resolved from a versioned static JSON snapshot under `data/universe/index_snapshots/russell1000.json`. The snapshot is sourced from iShares IWB ETF holdings (no FMP endpoint exists for Russell 1000). Bundled snapshot is a representative sample (26 names spanning 7 GICS sectors); a scripted ingestion of the full ~1000 names is intentionally deferred. Snapshot refresh is currently manual: download IWB holdings CSV from BlackRock, normalize, and overwrite the JSON file.

#### Snapshot file format (`index_snapshot_v1`)

```json
{
  "index_id": "russell1000",
  "snapshot_schema_version": "index_snapshot_v1",
  "snapshot_date": "2026-04-30",
  "source": "ishares_iwb_holdings_csv",
  "source_url": "https://www.ishares.com/...",
  "source_notes": "<provenance and limitations>",
  "constituent_count": 26,
  "constituents": [
    {"symbol": "AAPL", "name": "Apple Inc", "sector": "Information Technology"},
    ...
  ]
}
```

The loader (`_load_index_snapshot` in `app/services/universe_resolver.py`) fails closed on missing file, invalid JSON, schema_version mismatch, index_id field mismatch, or malformed constituent rows. Resolver degradation: when the file is unavailable, `evaluated_members` is `[]` with a logged warning rather than a raised error — the artifact's `confidence` will reflect the degraded state.

### Quality factor IDs (require FMP fundamental data)

| factor_id | formula | direction | source |
|---|---|---|---|
| `quality_profitability` | (revenue − COGS) / total_assets, fallback EBIT/total_assets | higher_is_better | income statement + balance sheet |
| `quality_cash_generation` | OCF / total_assets, fallback FCF/total_assets | higher_is_better | cash flow + balance sheet |
| `quality_accrual` | (net_income − OCF) / total_assets — Sloan ratio | lower_is_better | income statement + cash flow |
| `quality_leverage` | (total_debt − cash) / total_assets — net leverage | lower_is_better | balance sheet |

### Value factor IDs (require FMP TTM ratios)

| factor_id | formula | direction | source |
|---|---|---|---|
| `value_earnings_yield` | EBIT / Enterprise Value (Greenblatt) | higher_is_better | `key-metrics-ttm` |
| `value_book_to_market` | 1 / P/B | higher_is_better | `ratios-ttm.priceToBookRatioTTM` |
| `value_fcf_yield` | FCF / market_cap | higher_is_better | `ratios-ttm.priceToFreeCashFlowsRatioTTM` (invert) or `key-metrics-ttm.freeCashFlowYieldTTM` |
| `value_ev_ebitda_inverse` | 1 / (EV/EBITDA) | higher_is_better | `ratios-ttm.enterpriseValueMultipleTTM` (invert) |

### Catalog summary

`RankingArtifactCatalogRow.generic_summary` is populated for `artifact_kind == "generic_ranking"`:

```typescript
interface RankingArtifactCatalogGenericSummary {
  benchmark_symbol: string;
  lookback_months: number;
  universe_id: string;
  universe_kind: string;
  score_config_id: string;
  evaluated_universe_size: number;
  confidence: string;  // "full" | "partial" | "degraded"
}
```

The cross-kind discovery routes `/strategy-lab/ranking-artifacts/catalog` and `/strategy-lab/ranking-artifacts/recent` now surface generic ranking artifacts alongside ETF and replacement artifacts. Filtering by `artifact_kind="generic_ranking"` returns only generic rows.

### Behavior when fundamentals requested without FMP client

If the request includes quality or value factors but no FMP API key is configured, the service emits a warning and returns the artifact with those factors set to `None`. Confidence drops to `partial`. The artifact still persists — degraded state is surfaced explicitly rather than failing the request.

## Contract Rules

- the Pydantic schema in `services/quant-engine/app/schemas/generic_ranking.py` is the authoritative source of truth; the TypeScript types in `apps/desktop/src/features/generic-ranking/types.ts` must match it exactly
- `excluded_instruments` must remain explicit and are never silently dropped
- `hard_filter_failures` and `soft_filter_flags` are separate; failing a soft filter does not exclude an instrument
- `composite_score_trace` may be `null` and consumers must handle that case
- factor weights are normalized server-side; `FactorConfig.weight` values in the request are raw and not required to sum to any specific value, but the total must be positive
- `artifact_id` values always carry the `generic_ranking_artifact_` prefix; the backend enforces this at write time
- ranking is deterministic; no hidden ML or non-deterministic scoring is used
