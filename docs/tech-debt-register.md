# Tech-Debt Register

**Created:** 2026-06-12 (Epic 23 / US-23.1)

A single living catalog of (a) **dead/unused code** to remove and (b)
**hardcodes / anti-patterns** to improve. Populated during the Epic 23 cleanup
sweep (US-23.2–23.7) and consumed by a follow-up improvement epic (**Epic 24**).

**The split is deliberate.** Epic 23 *removes* dead code (deletions + tooling +
docs only). It only *records* the hardcodes/anti-patterns — those are fixed in
Epic 24, as deliberate reviewed changes, never mixed into deletion diffs.

## How to detect (the tooling — US-23.1)

```bash
# Python (from services/quant-engine/) — install once: pip install -r requirements-dev.txt
ruff check app --select F401,F811,F841            # unused imports / redefs / locals (in-file)
vulture app vulture_allowlist.py --min-confidence 80   # unused functions/classes/attrs (whole-program)

# TypeScript (from apps/desktop/) — knip is a devDependency
npx knip                                          # unused files / exports / types / deps
npx tsc --noEmit                                  # in-file unused (once noUnusedLocals is enabled — see below)

# Both, via the canonical runner (US-23.8 will make this a zero-findings gate):
python scripts/detect_deadcode.py
```

**Allowlists are the integrity risk.** `vulture_allowlist.py` (and any future
knip ignore) must name *why* each entry is a dynamic-use false positive. An
unreasoned allowlist silently re-opens the door.

## Removal protocol (a symbol/file is "confirmed dead" only when ALL hold)

1. **No static reference** anywhere (grep + the area's detector agree).
2. **No dynamic / reflective use** — `getattr`, string-keyed dispatch, FastAPI
   route registration, pytest collection/fixtures, Pydantic
   `field_validator`/`model_post_init`, JSON `schema_version` round-trips,
   IndexedDB/localStorage **persistence or migration** sanitizers. (The
   admission-disposition plumbing is the cautionary example: it *looks* dead but
   sanitizes persisted state.)
3. **Not a public contract** still referenced by docs/types on the other side of
   a seam (reconcile in US-23.5 first if so).
4. The full `python scripts/run_all_tests.py` is green and `npx tsc --noEmit`
   clean **after** removal.

When in doubt → record as `dead-suspected` here, do **not** delete.

## Entry schema

| Field | Values |
|---|---|
| `area` | `backend/analytics-schemas`, `backend/services-routes`, `frontend`, `contracts`, `tests`, `scripts`, `cross` |
| `file:line` | location |
| `category` | `dead-suspected` · `hardcode` · `magic-number` · `anti-pattern` · `duplication` · `fragile-coupling` · `missing-abstraction` |
| `severity` | `low` · `med` · `high` |
| `effort` | `low` · `med` · `high` |
| `owner-story` | the Epic 23 story that acts on it (or `epic-24` for improvements) |
| `note` | one line |

## Findings

> Curated findings, triaged from the US-23.1 detector baseline (appendix) and
> later sweeps. Each row names the owning Epic 23 story (deletions) or `epic-24`
> (improvements).

### Dead code — confirmed deletion candidates (triaged in US-23.5)

The contract audit (US-23.5) confirmed **none** of these cross a documented
contract seam, so the owning story can delete them safely.

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| frontend | `types.ts` `ActivityPoint` | dead-suspected | low | low | US-23.4 | exported type, 0 consumers, no backend source / no contract doc — FE-orphan |
| frontend | `types.ts` `CanonicalLedgerRecord` | dead-suspected | low | low | US-23.4 | exported type, FE-orphan (no backend source, no contract doc) |
| frontend | `types.ts` `ReconciliationCheck` | dead-suspected | low | low | US-23.4 | FE mirror of a backend type with **no FE consumer**; backend `reconciliation.py` keeps its own — delete the FE mirror only |
| frontend | `types.ts` `DiagnosticsPayload` | dead-suspected | low | low | US-23.4 | exported type, FE-orphan |
| frontend | `types.ts` `ExposureEnginePayload` | dead-suspected | low | low | US-23.4 | exported type, FE-orphan |
| frontend | `src/app/featureFlags.ts` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) |
| frontend | `src/app/portfolioState.ts` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) |
| frontend | `CurrentFactorSnapshotCard.tsx` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) — not rendered anywhere |
| frontend | `DashboardPerformanceChart.tsx` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) |
| frontend | `SectorDonutCard.tsx` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) |
| frontend | `historyTruth.ts` | dead-suspected | low | low | US-23.4 | whole file unimported (knip) |
| frontend | `investorEconomics.ts` | dead-suspected | low | low | US-23.4 | whole file unimported (knip) |
| frontend | `src/app/portfolioDb.ts` `getPortfolioDatabaseName` | dead-suspected | low | low | US-23.4 | exported fn, 0 consumers |
| tests | `portfolioFixtures.ts` `createDiagnosticsFixture`, `createIb2026/Ff2026ImportedDashboardFixture`, `createImportedBaselineFixture` | dead-suspected | low | low | US-23.6 | exported fixture factories, never imported |
| cross | `ImportAdmissionReviewDispositionV1` (BE `schemas/import_bootstrap.py`; FE `types.ts` + `portfolioWorkspaceStorage.ts` sanitizers; `import-admission-fields.md`) | dead-suspected | med | med | US-23.4 (FE) + US-23.2 (BE) | **The canonical cross-seam dead case** (US-22.2 close-out): no producer, no consumer; persistence sanitizers self-reference it so `knip` does NOT flag it. Remove FE plumbing first (with persisted-state safety checks), then BE schema, then reconcile the contract doc. Not deletable by a single story — coordinate. |
| backend/analytics-schemas | `analytics/attribution.py` (imports `WINDOW_MIN_OBSERVATIONS`, `_series_to_returns`) | dead-suspected | low | low | US-23.2 | ruff F401 unused imports |
| backend/analytics-schemas | `analytics/risk.py` (import `FactorRiskContribution`; locals `target`/`top_shared`/`alpha_annualized`/`specific_risk`/`collinearity_warnings`) | dead-suspected | med | med | US-23.2 | ruff F401/F841 + vulture — some unused locals may be a computed-but-dropped result; confirm intent (dead vs bug) before deleting |
| backend/analytics-schemas | `schemas/reconciliation.py` (imports `LedgerRecord`, `ImportedPortfolioSnapshot`) | dead-suspected | low | low | US-23.2 | ruff F401 unused imports |
| backend/services-routes | `services/dashboard_history_engine.py` local `allow_exact_slice_benchmark_return_output` | dead-suspected | low | low | US-23.3 | ruff F841 unused local |
| backend/services-routes | `importers/freedom24.py` locals `isin`, `realized_pnl`, `account` | dead-suspected | low | low | US-23.3 | ruff F841 — parsed-but-dropped; confirm not a missing-field bug |
| tests | test-file unused imports (`pytest`/`Path`/`math`) + unused locals (`test_analytics.py`, `test_market_data_fallback.py`, `test_yfinance_client.py`, `test_exposure_engine.py` unreachable-after-return) | dead-suspected | low | low | US-23.6 | ruff + vulture; test hygiene |

### Over-exported (live, not dead) — low priority

71 exported types/functions are **used in-file but never imported elsewhere**
(knip "unused exports") — e.g. the response-shape mirrors composed inside
`types.ts` (`ExposureRunMetadata`, `DiagnosticsProvenance`, `DailyPortfolioState`,
…) and `portfolioDb`/`portfolioWorkspaceStorage` helpers. These are **not dead**;
the `export` keyword is merely unnecessary. **owner US-23.4** (optional
de-export; low priority — harmless, and some are transitively dead once the
confirmed-dead types above are removed, so re-run `knip` iteratively).

### Hardcodes / anti-patterns + latent bugs (→ Epic 24)

**risk.py F841 findings — investigated and RESOLVED as dead code (not bugs).**
A close read against `docs/finance/financial-methodology.md` showed these were
**dead leftover computations**, not missing outputs, so they were removed (see
"Removed" below). Crucially, the methodology (§Statistical Factor Model,
"Residual must never be labeled 'alpha'… never 'alpha_pct'") **forbids
surfacing** the OLS intercept — so "fixing" `alpha_annualized` by exposing it
would have *violated* methodology. The project was never unstable: none of these
affected any computed/returned value (they were discarded locals).

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/importers | `importers/freedom24.py:138,221,266` `isin`, `realized_pnl`, `account` | dead-suspected / parsed-but-dropped | med | low | US-23.3 | Broker-statement fields parsed then dropped — confirm dead vs missing-data (realized P&L / account) before removal. Not yet touched. |
| backend/services | `services/dashboard_history_engine.py` `allow_exact_slice_benchmark_return_output` | dead-suspected | low | low | US-23.3 | F841 unused local (param-shadow) — confirm dead vs dropped flag. Not yet touched. |

> _(More appended by US-23.3/23.4/23.6 as remaining smells are found.)_

#### US-23.2 catalog — `analytics/` + `schemas/` + `domain/` + `instruments/` (recorded, not fixed → Epic 24)

Exhaustive hardcode / magic-number / anti-pattern sweep of the four pure-logic
modules (AC4). **Nothing fixed here** (Epic 23 is deletions-only); each row is an
Epic 24 candidate. Detectors (`ruff F401/F811/F841`, `vulture --min-confidence 80`)
are **clean** on all four trees after the prior dead-code pass — these are *style /
config* findings, not dead code.

**Latent bugs (hardcoded calendar year — highest priority):**

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/analytics-schemas | `analytics/activity.py:24` | anti-pattern / latent-bug | high | low | epic-24 | `if entry.date.year != 2025:` — the activity summary **silently drops every ledger entry not dated 2025**. Breaks for any 2026+ statement. Should derive the year from the statement period, not a literal. |
| backend/analytics-schemas | `analytics/reconciliation.py:24` | anti-pattern / latent-bug | high | low | epic-24 | `candidate.date.year == 2025` in the withholding-tax reconciliation filter — same hardcoded-year class as activity.py; non-2025 withholding entries are excluded. |

**Hardcodes / magic numbers / fragile coupling:**

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/analytics-schemas | `analytics/reconciliation.py:10` | hardcode / fragile-coupling | med | low | epic-24 | `fx_rates.get("EURUSD", 1.0)` — hardcoded FX pair key + 1.0 fallback bakes in an EUR-base assumption; multi-currency statements silently use 1.0. |
| backend/analytics-schemas | `analytics/reconciliation.py:63` | magic-number | med | low | epic-24 | `abs(difference) <= 0.25` — undocumented cash-reconciliation tolerance (0.25 units). No named constant, no citation. |
| backend/analytics-schemas | `domain/ledger.py:67-92` | fragile-coupling | med | med | epic-24 | Broker-statement section labels hardcoded into the domain layer ("Trades", "Deposits & Withdrawals", "Dividends", "Income Summary", "Cash deposits/ withdrawals", "Withholding Tax", "Account Summary", "Fees", "Other Fees", "Commissions"). IBKR/Freedom24 statement format leaks into ledger classification; a label rename silently mis-classifies entries. |
| backend/analytics-schemas | `domain/ledger.py` + analytics (`activity.py:12-19`, etc.) | missing-abstraction | low | med | epic-24 | Entry-type strings (`BUY`/`SELL`/`DIVIDEND`/`INTEREST`/`FEE`/`WITHHOLDING_TAX`/`DEPOSIT`/`WITHDRAWAL`) used as a pseudo-enum across domain + analytics with no shared `Literal`/`Enum` — typo-prone, no single source of truth. |
| backend/analytics-schemas | `domain/ledger.py:158` & `schemas/portfolio.py:9,19` & `portfolio_engine.py` | hardcode | low | low | epic-24 | `"USD"` default base/trade currency repeated across schema defaults + ledger; assumes USD when base currency is absent. |
| backend/analytics-schemas | `analytics/risk.py:138-142` (`STRESS_SCENARIOS`) | hardcode | med | med | epic-24 | Three stress-scenario factor-shock vectors (Broad Market Selloff / Rates Down Risk-On / Inflation Reacceleration) hardcoded inline as a tuple-of-dicts. Surfaced on the Risk tab; methodology-documented but the shock magnitudes are inline data, not a reviewable config. |
| backend/analytics-schemas | `analytics/risk.py:196,232-233,241,248,256,264` | magic-number | med | high | epic-24 | Mapping-match composite scoring weights inline across `_compute_*` (e.g. `0.60/0.25/0.15`; equity `0.65/0.35` & `0.45/0.30/0.25`; bond `0.40/0.25/0.20/0.15`; commodity `0.50/0.30/0.20`; structure `0.35/0.25/0.20/0.20`; implementation `0.40/0.30/0.20/0.10`). No named weights / config; tuning requires editing code. |
| backend/analytics-schemas | `analytics/risk.py:275-288` | magic-number | med | low | epic-24 | Mapping hard-cap ceilings (`50.0/45.0/60.0/25.0/70.0`) + reason strings inline in `_apply_mapping_hard_caps`. |
| backend/analytics-schemas | `analytics/risk.py:293-304,335-470,1055-1064` | magic-number | med | high | epic-24 | Dense inline score literals across the mapping-quality scoring helpers (`_mapping_match_label` thresholds 90/80/65/50; `_index_match_score`, `_style_sector_similarity_score`, the bond/commodity/structure/implementation `_*_fit_score` families, `_cost_fit_score` quality map, `_mapping_quality_score` 0.95/0.82/0.68/0.50). A large rubric encoded as scattered literals. |
| backend/analytics-schemas | `analytics/risk.py:1485-1499,1537-1549` | hardcode / fragile-coupling | med | med | epic-24 | Sector inference from hardcoded proxy-ticker lists (`_infer_sector_from_sources`, `_infer_sector_from_resolved_pair`): e.g. `["XLF"]→Financials`, `["ITA","PPA"]→Defense`, `["BIL","VGSH"]→Fixed Income`. Duplicated across two functions; overlaps the `InstrumentRegistry` sector source of truth. |
| backend/analytics-schemas | `analytics/risk.py:1262-1267` | magic-number | low | low | epic-24 | Volatility-regime percentile cutoffs inline (`< 0.30` calm, `<= 0.80` normal, else stressed). |
| backend/analytics-schemas | `analytics/risk.py:1331` | magic-number | low | low | epic-24 | `len(common_dates) < 10` minimum-history gate for the factor model — undocumented literal (distinct from the named `WINDOW_MIN_OBSERVATIONS`). |
| backend/analytics-schemas | `analytics/risk.py:750-751,1441` | magic-number | low | low | epic-24 | Top-N display slices hardcoded: top over/under-weights `[:5]`, top shared constituents `[:15]`. |
| backend/analytics-schemas | `analytics/risk.py:1038,1040-1052` | hardcode | low | med | epic-24 | `build_factor_exposures` hardcodes the growth-tilt sector composition and the full factor-exposure label/description/basis list inline. |
| backend/analytics-schemas | `analytics/risk.py:122-136` | magic-number (documented) | low | low | epic-24 | Module-level threshold constants are **named** (`COLLINEARITY_WARNING_THRESHOLD=0.85`, `SHIFT_FLAG_20D_THRESHOLD=0.25`, `SHIFT_FLAG_60D_THRESHOLD=0.35`, `STABILITY_GAP_THRESHOLD=0.30`, `VOLATILITY_RATIO_FLAG_THRESHOLD=1.2`, `WINDOW_MIN_OBSERVATIONS`, `ROLLING_RIDGE_FLOOR`) — good practice; listed for completeness. Only gap: no academic/methodology citation beside each value. |
| backend/analytics-schemas | `analytics/rebalance.py:51,83` | magic-number | low | low | epic-24 | `target_equity_weight=0.9`, `tolerance=0.05` default rebalance params inline (repeated in two functions). |
| backend/analytics-schemas | `analytics/drawdown.py:353` | magic-number | low | low | epic-24 | `abs(residual_pct) < 0.001` decomposition-residual epsilon inline (also `top_n` cap at :157). |
| backend/analytics-schemas | `analytics/distribution.py:67-71` | magic-number | low | low | epic-24 | Percentile fractions inline (`0.05/0.10/0.50/0.90/0.95`). Contract-defined and keyed; `_MIN_OBSERVATIONS`/`_DEFAULT_HISTOGRAM_BINS` are already named constants — low concern. |
| backend/analytics-schemas | `analytics/correlation.py:70,123` | magic-number (documented) | low | low | epic-24 | `min_observations: int = 20` default (matches the methodology min-observations); param-exposed and documented — listed for completeness. |
| backend/analytics-schemas | `instruments/registry.py:45-48,180-261` | hardcode / fragile-coupling | low | med | epic-24 | Hardcoded instrument reference data (futures `tick_size`/`point_value`/`multiplier`; ETF→sector defs) plus a keyword-substring sector classifier (`get_sector` fallback chain ~209-242). Reference data is acceptable (documented in the `fmp-data` skill); the keyword classifier is the fragile part. |
| backend/analytics-schemas | `schemas/correlation.py:13`, `intra_correlation.py:22,24`, `provenance.py:21`, `distribution.py:31` | magic-number (documented) | low | low | epic-24 | Window/lookback `Field` defaults (`252`, `60`, `15`, `30`). Sensible, validated (`ge=`) defaults — listed for completeness; consider a shared windows config if they ever need to align. |

### Removed (completed)

- **US-23.4** (frontend, this pass): deleted 6 unimported files (`featureFlags.ts`, `portfolioState.ts`, `CurrentFactorSnapshotCard.tsx`, `SectorDonutCard.tsx`, `historyTruth.ts`, `investorEconomics.ts`); 5 dead types (`ActivityPoint`, `CanonicalLedgerRecord`, `ReconciliationCheck`, `DiagnosticsPayload`, `ExposureEnginePayload`); dead helper `getPortfolioDatabaseName`. knip: 7→1 unused files, 65→60 types, 22→21 exports. tsc + suite green.
- **US-23.2** (backend): removed 5 F401 unused imports (`attribution.py`, `risk.py`, `reconciliation.py`).
- **US-23.2** (backend, risk.py dead-computation sweep — investigated, confirmed not bugs): removed the dead full-period OLS block in `_build_statistical_factor_model` (the global `_orthogonalize_factor_series` call + `_fit_factor_model` fit + the discarded `alpha_annualized` / `specific_risk` / `collinearity_warnings` locals — none reached the `StatisticalFactorModel` response; methodology forbids surfacing the "alpha"); the dead `top_shared` `MarketOverlapConstituent[]` build in the market-overlap summary (superseded by `top_overweights`/`top_underweights`); the dead `target` local in `_apply_mapping_hard_caps`. Cascade: also removed the now-orphaned `_orthogonalize_factor_series` function, the `portfolio_names` local, and the dead `MarketOverlapConstituent` schema class (no TS/contract/test consumer). **Output-neutral** — goldens unchanged, full suite green; also drops a wasted full-period OLS fit per analysis.

### Remaining (deferred within Epic 23)

- **US-23.4 — empty feature dirs (resolved, not dead):** `src/features/market-data/` and `src/features/settings/` contain **only a `README.md`** each — intentional placeholders for unbuilt features (part of the documented repo layout in `CLAUDE.md`). Not dead code; left as-is (AC3 "documented").
- **US-23.4 — `DashboardPerformanceChart.tsx` (deferred → US-23.6):** the file is unimported (knip) but coupled to dead test scaffolding in `App.test.tsx` — a `vi.hoisted` mock-state (`dashboardPerformanceChartMock`, line ~18), a `vi.mock(...)` (line ~31), a reset (line ~446), and a 30-line suspense test (lines ~1040-1065) that may encode real App-suspense-boundary intent. Remove file + scaffolding together when doing App.test.tsx hygiene (US-23.6).
- **US-23.4 — over-exported live types (low priority):** ~60 `types.ts`/`workspaceTypes.ts` exports are used in-file but never imported elsewhere → optional de-export (or leave). Re-run `knip` iteratively after the disposition removal.
- **US-23.4 — suspected-unused CSS tokens (verify before removing):** `styles.css` defines 82 custom-property tokens; a crude `var()`-reference scan flags 7 with no direct reference — `--bg`, `--panel-3`, `--space-2xl`, `--font-body`, `--font-heading-sm`, `--opacity-unavailable`, `--color-line-benchmark`. **Not removed** — several are documented *design-scale* tokens (ui-polish contract) kept for completeness, and `--color-line-benchmark`/`--opacity-unavailable` may be referenced indirectly (class-based / JS string). A careful CSS pass (keep `designSystem.audit.test.ts` green; check class + string refs) owns these. Low value.
- **US-23.4 — FE anti-patterns:** none of note. Post-Epic-12 the Exposure cards use the design tokens/primitives consistently (the audit enforces it); the legacy Concentration Pack / Dashboard CSS classes are a *known, intentionally-deferred* migration (ui-polish migration notes), not catalogued here.

### ✅ Removed (US-23.9): disposition-plumbing removal (the marquee cross-seam dead case)

**Status: DONE (2026-06-19, US-23.9).** The entire closed removal set below was
removed across the seam, gated by the workspace save/load round-trip tests. A
pre-US-23.9 workspace's `admissionReviewDispositions` blob is now dropped on
read (field absent, no throw, storage not rewritten) — proven by the regression
"drops a legacy admissionReviewDispositions blob on read without rewriting
storage" in `portfolioWorkspaceStorage.test.ts`. The `import-admission-fields.md`
contract was reconciled (subsystem → "Removed" note). 234 frontend + backend
green; ruff/knip clean; no new vulture findings; tsc clean; goldens untouched.

The `ImportAdmissionReviewDispositionV1` subsystem had **no producer and no
consumer** (US-22.2 close-out): no UI called any disposition save; the README
called it "optional desktop-local metadata". Blast radius was **fully mapped and
contained** — a ~250-line cross-file change to the **persistence
layer + a 726-line test file (77 disposition lines / 14 blocks) + the BE
schema** — so it was done as **its own focused slice** with the workspace
save/load round-trip tests as the gate.

Closed removal set (no external/production users — verified via grep + knip):
- `apps/desktop/src/app/portfolioWorkspaceStorage.ts`: the disposition **save
  function** (calls `assertValidImportAdmissionReviewDispositionForSave`, writes
  `admissionReviewDispositions`); `assertValidImportAdmissionReviewDispositionForSave`;
  the 8 sanitize/canonicalize/match helpers (`sanitizeAdmissionEvidenceValue`,
  `canonicalizeAdmissionEvidenceValue`, `canonicalizeImportAdmissionEvidenceSummary`,
  `buildCurrentImportAdmissionCheckEvidence`, `importAdmissionEvidenceSummariesMatch`,
  `sanitizeImportAdmissionEvidenceSummary`, `sanitizeImportAdmissionReviewDisposition`,
  `sanitizeImportAdmissionReviewDispositions`); the type aliases
  `CanonicalImportAdmissionEvidenceSummary` / `ImportAdmissionCheckV1` /
  `NonPassImportAdmissionCheckV1`; the `admissionReviewDispositions` handling in
  `buildPersistedImportedSource` + `sanitizeImportedNodeSource`; the import of
  `ImportAdmissionReviewDispositionV1`. **The whole fingerprint subsystem**
  (`canonicalizeForFingerprint`, `buildDeterministicImportAdmissionFingerprint`,
  `buildImportSnapshotFingerprint`, `buildImportAdmissionSummaryFingerprint`)
  exists only to build disposition fields and is used only by the test → remove
  with it.
- `workspaceTypes.ts`: the `admissionReviewDispositions` field + the
  `ImportAdmissionReviewDispositionV1` import.
- `types.ts`: `ImportAdmissionReviewDispositionV1` + `ImportAdmissionCheckEvidenceSummaryV1`.
- `portfolioWorkspaceStorage.test.ts`: the disposition fixtures + ~14 disposition/
  fingerprint test blocks (keep the non-disposition workspace round-trip tests).
- `App.test.tsx`: the `admissionReviewDispositions` lines in the `buildImportedSource` helper.
- **BE (US-23.2 coordinate):** `schemas/import_bootstrap.py` —
  `ImportAdmissionReviewDispositionV1`, `ImportAdmissionReviewEvidenceSummaryV1`,
  `ImportAdmissionReviewDisposition` enum (+ their `test_import_admission.py` refs).
- **Persisted-state safety:** dropping the read-path sanitizer means a saved
  workspace's `admissionReviewDispositions` is simply not carried forward on load
  (no crash); confirm with a saved-workspace load round-trip test.

- **US-23.2/23.3:** the F841 items above (freedom24 / dashboard_history_engine) await US-23.3; the disposition BE schema waits on the FE removal.

### Contract audit result (US-23.5)

A three-way audit (backend Pydantic schemas ↔ `types.ts`/`workspaceTypes.ts` ↔
`docs/contracts/*.md`) found **no type-level drift**: every CamelCase identifier
referenced in the contract docs resolves to a live schema class, a live TS type,
or is a UI component / prose word in a "UI display" column (not a type
reference). No stale contract rows, no dangling documented types. The only
mismatches are the FE-dead types above (no backend source / no consumer), which
are FE-only and flagged to US-23.4 — deleting them does **not** break any
documented seam. Contract docs are accurate as-is; no reconciliation edits
required.

---

## Appendix — detector baseline (captured US-23.1, 2026-06-12)

Raw detector output at epic start. **Unverified** — each item must pass the
removal protocol in its owning story before deletion (some are dynamic-use false
positives; some test-file items are intentional). Reproduce with the commands
above.

### Python — `ruff` (29 findings: 17×F401 unused-import, 12×F841 unused-local)

App (non-test) candidates → **US-23.2 / US-23.3**:
- `app/analytics/attribution.py` — unused imports `WINDOW_MIN_OBSERVATIONS`, `_series_to_returns` (from `app.analytics.risk`)
- `app/analytics/risk.py` — unused import `FactorRiskContribution`; unused locals `target`, `top_shared`, `alpha_annualized`, `specific_risk`, `collinearity_warnings`
- `app/schemas/reconciliation.py` — unused imports `LedgerRecord`, `ImportedPortfolioSnapshot`
- `app/services/dashboard_history_engine.py` — unused local `allow_exact_slice_benchmark_return_output`
- `app/importers/freedom24.py` — unused locals `isin`, `realized_pnl`, `account`

Test-file candidates → **US-23.6** (unused `pytest`/`Path`/`math` imports, unused locals in `test_analytics.py`, `test_attribution.py`, `test_drift_engine.py`, etc.).

### Python — `vulture` (min-confidence 80, allowlisted)

- `app/analytics/risk.py:10` — unused import `FactorRiskContribution` (also ruff F401) → **US-23.2**
- Test-file items (`test_exposure_engine.py` unreachable-after-return; unused vars in `test_market_data_fallback.py`, `test_yfinance_client.py`) → **US-23.6**
- (`app/schemas/imports.py` `__context` is allowlisted — Pydantic hook, not dead.)

### TypeScript — `knip` (7 unused files, 22 unused exports, 65 unused exported types) → **US-23.4** (types crossing the seam → coordinate **US-23.5**)

Unused files (highest-signal — confirm no dynamic import, then delete):
- `src/app/featureFlags.ts`, `src/app/portfolioState.ts`
- `src/features/portfolio/CurrentFactorSnapshotCard.tsx`, `DashboardPerformanceChart.tsx`, `SectorDonutCard.tsx`
- `src/features/portfolio/historyTruth.ts`, `investorEconomics.ts`

Plus 22 unused exported functions (incl. `portfolioDb` helpers, several
`portfolioAnalysisAdapter`/`portfolioSnapshot` builders, `portfolioFixtures`
factories) and 65 unused exported types in `types.ts` — many are contract
mirrors with no consumer (coordinate removal with **US-23.5**).

### Staged compiler flag

`tsconfig` `noUnusedLocals`/`noUnusedParameters` are **not yet enabled**:
turning them on surfaces ~20 in-file violations, several inside the knip
"unused files" above (which US-23.4 deletes) and in test/fixtures (US-23.6).
The flags are **staged for US-23.8** — enable them once US-23.4/23.6 clear the
blockers, so they go green as part of the standing dead-code gate.
