# OpenCode Spec: ETF Mapping Match Score

```text
Implement a professional `Mapping Match %` scoring system for US ETF proxy -> UCITS ETF mappings.

Important product constraint:
- Do NOT add narrative explanations, educational text, or recommendation text
- Only return structured component scores, overall score, label, score basis, and optional cap/degraded metadata
- The user will interpret the result manually

Goal:
Replace the current placeholder mapping score with a more professional and defensible composite score.

The score should quantify how good a UCITS mapping is relative to the US analytical proxy.

This is not a pure marketing score.
It should combine:
- exposure similarity
- historical similarity
- structure fit
- implementation fit

Primary use cases:
- show users how strong a UCITS mapping is for a given US proxy
- help distinguish exact mappings from usable but imperfect proxies
- support both metadata-only and full-data scoring modes

================================
SCORING FRAMEWORK
================================

Top-level formula:

`Mapping Match % = 100 * (0.40 * ExposureMatch + 0.30 * HistoricalSimilarity + 0.15 * StructureFit + 0.15 * ImplementationFit)`

All component scores must be normalized to the range `0.00 - 1.00`.

Final score must be clamped to `0 - 100`.

================================
TOP-LEVEL COMPONENTS
================================

1. `ExposureMatch`
2. `HistoricalSimilarity`
3. `StructureFit`
4. `ImplementationFit`

Also return:
- `score_basis`: `full` | `metadata_only`
- `score_status`: `ok` | `degraded` | `insufficient_data`
- `hard_cap_reason`: string | null

================================
COMPONENT FORMULAS
================================

1. ExposureMatch

This is the most important component.
Use asset-class-specific scoring.

For equity ETFs:

`ExposureMatch_equity = 0.45 * IndexMatch + 0.30 * HoldingsOverlap + 0.25 * StyleSectorSimilarity`

Definitions:

- `IndexMatch`
  - `1.00` = same index / same target exposure
  - `0.85` = same segment, different index provider
  - `0.60` = close proxy
  - `0.30` = loose proxy
  - `0.00` = wrong exposure

- `HoldingsOverlap`
  - if holdings data exists, use a normalized overlap score
  - suggested formula:
  - `HoldingsOverlap = min(1.0, overlap_weight / 0.80)`
  - if holdings data is unavailable, mark component unavailable and use fallback weights in metadata-only mode

- `StyleSectorSimilarity`
  - use normalized sector/style weight distance
  - suggested formula:
  - `StyleSectorSimilarity = max(0, 1 - 0.5 * sum(abs(w1_i - w2_i)))`

For bond ETFs:

`ExposureMatch_bond = 0.40 * DurationMatch + 0.25 * MaturityBucketMatch + 0.20 * CreditQualityMatch + 0.15 * IssuerCurveMatch`

Definitions:

- `DurationMatch = max(0, 1 - abs(duration_1 - duration_2) / 6)`

- `MaturityBucketMatch`
  - `1.00` same bucket
  - `0.65` adjacent bucket
  - `0.25` otherwise

- `CreditQualityMatch`
  - `1.00` same sleeve: Treasury / IG / HY
  - `0.00` otherwise

- `IssuerCurveMatch`
  - `1.00` same sovereign/corporate market and curve type
  - `0.50` close
  - `0.00` mismatch

For commodity ETFs/ETCs:

`ExposureMatch_commodity = 0.50 * BasketMatch + 0.30 * RollMethodMatch + 0.20 * CollateralStructureMatch`

Definitions:

- `BasketMatch`
  - `1.00` same broad commodity basket or same single commodity
  - `0.60` close broad commodity proxy
  - `0.00` mismatch

- `RollMethodMatch`
  - `1.00` same or very similar roll methodology
  - `0.50` partially similar
  - `0.00` materially different or unavailable

- `CollateralStructureMatch`
  - `1.00` close structure
  - `0.50` acceptable
  - `0.00` mismatch

2. HistoricalSimilarity

Use aligned total-return series if available.

Formula:

`HistoricalSimilarity = 0.45 * CorrScore + 0.35 * TrackingDiffScore + 0.20 * BetaScore`

Definitions:

- `CorrScore = clamp((corr - 0.70) / 0.30, 0, 1)`

- `TrackingDiffScore = clamp(1 - tracking_error_ann / threshold, 0, 1)`

- `BetaScore = clamp(1 - abs(beta - 1.0) / 0.50, 0, 1)`

Recommended annualized tracking-error thresholds:
- broad/sector/style equity ETFs: `0.08`
- bond ETFs: `0.05`
- commodity products: `0.12`

History requirements:
- preferred minimum: 252 aligned trading days
- acceptable minimum for partial scoring: 126 aligned trading days
- if below minimum, set `score_basis = metadata_only` or `score_status = degraded`

3. StructureFit

Formula:

`StructureFit = 0.35 * HedgeStatusFit + 0.25 * DistributionFit + 0.20 * UcitsFit + 0.20 * CurrencyShareClassFit`

Definitions:

- `HedgeStatusFit`
  - `1.00` match
  - `0.40` mismatch
  - `0.70` unknown

- `DistributionFit`
  - `1.00` desired distribution policy match
  - `0.60` mismatch
  - `0.75` unknown

- `UcitsFit`
  - `1.00` UCITS
  - `0.00` non-UCITS

- `CurrencyShareClassFit`
  - `1.00` preferred investor-facing share class / suitable trading line
  - `0.70` acceptable
  - `0.40` inconvenient

4. ImplementationFit

Formula:

`ImplementationFit = 0.40 * LiquidityFit + 0.30 * HistoryFit + 0.20 * CostFit + 0.10 * AvailabilityFit`

Definitions:

- `LiquidityFit`
  - compute from AUM, spread, and/or volume when available
  - if limited data exists, use conservative fallback values and mark degraded if needed

- `HistoryFit`
  - `1.00` if >= 3 years history
  - `0.75` if 1-3 years
  - `0.40` if < 1 year

- `CostFit = clamp(1 - ter / 0.0060, 0, 1)`
  - assumes `ter` in decimal form, e.g. `0.0020` for 0.20%

- `AvailabilityFit`
  - `1.00` available at target broker/venue
  - `0.50` uncertain
  - `0.00` unavailable

================================
HARD CAPS
================================

Apply hard caps after the raw score is computed.

Rules:

- if asset class mismatch => cap final score at `25`
- if region/market mismatch => cap final score at `50`
- if bond credit sleeve mismatch => cap final score at `45`
- if bond duration bucket is materially off => cap final score at `60`
- if hedge status mismatch for rate-sensitive bond mapping => cap final score at `70`
- if distributing ETF lacks total-return-equivalent history => `score_status = degraded`

Return `hard_cap_reason` when any cap is applied.

================================
FALLBACK / METADATA-ONLY MODE
================================

If historical comparison data is unavailable, use this fallback formula:

`Mapping Match % = 100 * (0.60 * ExposureMatch + 0.25 * StructureFit + 0.15 * ImplementationFit)`

In this mode:
- `score_basis = metadata_only`
- `HistoricalSimilarity = null`
- final score still returned

================================
LABEL BANDS
================================

Use these score labels:

- `90-100` => `Exact / Best Match`
- `80-89` => `Strong Match`
- `65-79` => `Usable Proxy`
- `50-64` => `Loose Proxy`
- `0-49` => `Poor Match`

These labels should be separate from `mapping_quality` if both are shown.

================================
BACKEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `services/quant-engine/app/analytics/risk.py`
- `services/quant-engine/app/schemas/reconciliation.py`
- any factor registry / mapping source files

Update the current mapping metadata flow so each mapping can return:

```python
class MappingMatchComponents(BaseModel):
    exposure_match: float | None = None
    historical_similarity: float | None = None
    structure_fit: float | None = None
    implementation_fit: float | None = None
```

```python
class MappingMatchSummary(BaseModel):
    score_pct: float | None = None
    label: str | None = None
    score_basis: str
    score_status: str
    hard_cap_reason: str | None = None
    components: MappingMatchComponents
```
```

Attach this to:
- `UcitsMapping`
- `FactorProxyDefinition.primary_mapping`
- `SnapshotItem.primary_mapping`

Optional:
- do the same for alternative mappings later

================================
IMPLEMENTATION NOTES
================================

Suggested helper functions:
- `_compute_mapping_match_summary(...)`
- `_compute_exposure_match_equity(...)`
- `_compute_exposure_match_bond(...)`
- `_compute_exposure_match_commodity(...)`
- `_compute_historical_similarity(...)`
- `_compute_structure_fit(...)`
- `_compute_implementation_fit(...)`
- `_apply_mapping_hard_caps(...)`
- `_mapping_match_label(...)`

Use deterministic scoring.
Do not return prose explanations.

If some inputs are unavailable:
- return null for missing component values
- switch to metadata-only mode when appropriate

================================
FRONTEND REQUIREMENTS
================================

Relevant files to inspect and update:
- `apps/desktop/src/features/portfolio/ExposurePanel.tsx`
- `apps/desktop/src/features/portfolio/types.ts`

UI behavior:
- replace the current placeholder numeric score with `score_pct`
- display score as percent
- display label as compact sublabel if desired
- keep quality tag if product wants both
- do not add prose explanations

Recommended mapping cell content:
- quality badge
- match percent
- optional compact label

Example visual stack:
- `High`
- `86%`
- `Strong Match`

No commentary text.

================================
TESTING
================================

Add backend tests for:
- exact equity mapping => high score
- bond mapping with duration mismatch => capped score
- metadata-only mode when no history exists
- poor structure fit lowers score appropriately
- hard cap rules override otherwise high raw score

Add frontend tests for:
- score percent renders
- label renders if present
- null score renders as `n/a`

================================
DELIVERY NOTES
================================

Implement in 2 phases if needed:

Phase 1:
- metadata-only score
- hard-cap support
- UI rendering

Phase 2:
- historical similarity using aligned return series
- richer implementation-fit inputs

When finished, report:
- files changed
- formulas implemented
- which components are live vs placeholder
- whether score is `full` or `metadata_only`
```
