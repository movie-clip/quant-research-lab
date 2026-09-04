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

## Epic 24 backlog (consolidated — US-23.7)

The improvement findings below (catalogued during US-23.2/23.3/23.6, never fixed
in Epic 23) are consolidated here into a prioritized backlog, grouped to the
proposed Epic 24 stories in `docs/product/prd/epic-24-codebase-improvement.md`.
Priority = severity × (inverse) effort; the detailed, line-referenced rows live
in the per-area catalogs further down.

| Epic 24 story | Priority | Findings rolled up (see detail rows) |
|---|---|---|
| US-24.1 — hardcoded-year bugs | ✅ **RESOLVED (US-24.1)** | `analytics/activity.py`, `analytics/reconciliation.py` — the hardcoded `year == 2025` filters were removed (the snapshot ledger already scopes the period); non-2025 statements now reconcile correctly. 2025 goldens unchanged; 4 regression tests added. |
| US-24.2 — risk-model rubric & thresholds | ✅ **RESOLVED (US-24.2)** | The tunable policy numbers were lifted into a documented named-constants block in `risk.py` (composite/sub-weights, hard-cap ceilings, label thresholds, quality maps, regime cutoffs, min-history) + `BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT` in `exposure_engine.py`. Behaviour-neutral (goldens unchanged), golden-master-pinned. **Remaining (deferred):** the leaf per-token match scores in the `_*_score` helpers stay inline (rubric body, no tunable value) — low-value follow-up. |
| US-24.3 — shared analytics constants | ✅ **RESOLVED (US-24.3)** | New `app/core/constants.py` holds `lookback_calendar_days` / `MIN_DAILY_OBSERVATIONS` / `DEFAULT_BENCHMARK_SYMBOL` as the single source of truth. Consolidated the lookback helper across 6 engines (attribution/correlation/distribution/drawdown/stress/provenance + intra-correlation), the flat `_MIN_OBSERVATIONS=20` across 5 sites (incl. the analytics modules + an intra-correlation copy the original catalog missed), and ~10 `"SPY"` defaults (3 schema field defaults + the engine `or "SPY"` fallbacks). Behaviour-neutral (goldens unchanged); `WINDOW_MIN_OBSERVATIONS` + `attribution.min_observations=window` correctly left alone. |
| US-24.4 — Freedom24 importer hardening | ✅ **RESOLVED (US-24.4)** | **Correction:** the "ISIN data gap" was a misread — `_parse_instruments` already parses ISIN and sets `isin=` on every `ImportedInstrument` (Freedom24 ISINs already flow + feed US-19.2). The `:138` `isin` was just dead position-parser offset-walk code (positions don't model ISIN) — removed. Made all 5 Freedom24 positional parsers **fail-safe** (skip a malformed/non-numeric record + continue instead of crashing the import); extracted the inline format hardcodes (currency whitelist / `.US` suffix / default currency / page indices) to named constants; removed the 3 dead parsed-but-dropped locals. Behaviour-neutral (FF2026 fixture pinned, incl. a new ISIN assertion); `realized_pnl` stays unmodeled (deferred — see row below). |
| US-24.5 — decouple broker format from domain | ✅ **RESOLVED (US-24.5, 2026-08-09)** | **Severity correction: the row was rated Med as coupling debt; it was a High correctness defect on two of three brokers.** Re-validating before refactoring (Epic 24 discipline) found `domain/ledger.py` matched broker display strings inline, so any importer whose statement used different labels fell through to `cash_movement_classification == "unknown"` silently. **F-1:** Freedom24 calls its trade section `"Transactions"` — all 3 FF2026 trades unclassified. **F-2:** ESPP emits `"Employee Stock Purchase Summary"` for both the payroll DEPOSIT and the BUY — both unclassified, and since `external_capital_flow` is how `portfolio_proof._cash_flow_witnesses` recognises investor contributions, the deposit was reported `not_observed` while the statement stated it plainly. IB2026 classified all 204 entries cleanly, which is why it survived — the primary fixture never exercised it. **Fix:** a section-role registry resolving (label, entry_type) → semantic role, with `source_section` preserved as provenance (no importer relabels its broker's vocabulary). `unknown` stays reachable for genuinely unrecognised sections. **The real deliverable is the AC7 guard:** an AST scan asserts every `source_section` literal any importer emits resolves to a role, so the next broker fails the suite instead of degrading output in production. FF2026 and ESPP2026 now classify with zero `unknown`; IBKR byte-identical; goldens untouched. +22 backend tests. **Second register item was stale:** `LedgerEntryType` already exists as a shared `Literal` in `app/schemas/imports.py:9` and is imported by the domain and both IBKR importers — no pseudo-enum left to extract. |
| US-24.6 — market-data client config | ✅ **RESOLVED (US-24.6)** | Two of the three recorded items were real and are fixed; the third was a misread. **Fixed — the escaped URL (the actual defect):** `get_etf_holders` built an **absolute** `https://financialmodelingprep.com/api/v3/etf-holder/{symbol}` inline, the one call bypassing `settings.fmp_base_url`, so it could not be redirected to a proxy/mock/fixture. **Note the subtlety:** it legitimately targets the **legacy v3** API while `fmp_base_url` is `/stable`, so reusing `fmp_base_url` would 404 — the fix adds a *separate* `fmp_legacy_base_url` (default `https://financialmodelingprep.com/api/v3`, preserving the exact live URL). No vendor host literal remains in `fmp.py`. **Fixed:** `timeout=30.0` → `fmp_request_timeout_seconds` (default 30.0), the last non-configurable transport knob. **Preserved deliberately:** the `get_etf_holders` **cache identifier** still serialises the v3 *path* (`api/v3/etf-holder/<SYM>`) and is intentionally independent of the now-configurable host — changing it would have invalidated every cached holdings entry and broken in-flight coalescing (regression-pinned). **Scoping correction — `:248` `limit=500` is NOT debt:** it is a caller-overridable keyword default on a public method (correct API design, not a buried constant) with no in-app callers; promoting it to settings would add config surface nothing sets. Left unchanged. Behaviour-neutral at defaults; goldens untouched; +4 backend tests. |
| US-24.7 — minor hardcodes + de-export + test smells | ✅ **RESOLVED (US-24.7, 2026-08-09)** | Re-validated item by item; two real, one a guardrail violation rather than debt, three scoping corrections. **F-1 (the real finding):** the public `build_position_risk_contributions` (`risk.py:596`) had **no production caller** — the live Risk Summary path is the private `_build_position_risk_contributions` — yet `financial-methodology.md` named the public one as the source of per-position beta/correlation. The canonical methodology doc pointed a reader at a function that never executed, a direct hit on guardrail #1 ("one formula, one code path"). Deleted, together with the `PortfolioRiskContribution` model that only it used (on no response schema) and the three tests that existed solely for it; the doc now names the live path, and the US-30.5b observation-floor coverage is retained against that path. It escaped the dead-code gate because vulture counts test callers — a function reachable only from tests is invisible to it (general limitation, not a gate bug). **F-2:** `STATEMENT_RECONCILIATION_TOLERANCE` (0.25, the statement-reconciliation pass threshold) and `PORTFOLIO_PROOF_TERMINAL_MATCH_TOLERANCE` (0.01) are now named constants with rationales — the latter states **why** it is 100× tighter than `REPLAY_RECONCILIATION_TOLERANCE` (it compares the proof path's own recomputation against the statement, where a cent of disagreement means the recomputation is wrong; the replay tolerance absorbs genuine valuation residuals). Values unchanged. **Scoping corrections — examined and deliberately NOT changed:** (a) `statement_importer.py:197` `/100` is a percentage→fraction **unit conversion**, self-evident in context, not a magic number; (b) the `"USD"` repetition (76 non-test sites) mixes base-currency *fallbacks* with currency *data* — a blanket constant would conflate them, touch 76 sites for zero behaviour change and make the fallbacks harder to find; (c) de-export is stale (US-23.8 shipped knip with `ignoreExportsUsedInFile`). Hand-rolled test-builder migration stays deferred on US-23.6's still-valid reason. Behaviour-neutral; goldens byte-identical; dead-code gate green after the deletion. |
| US-24.9 — cash de-dilution on the imported ledger-replay return series | ✅ **RESOLVED (US-24.9, 2026-08-09)** | New `DailyPortfolioState.trade_flow` (net base-currency market value moved into the holdings by that day's BUY/SELL entries, FX-converted per entry) plus a third `ReturnBasis`, `market_value_trade_neutral` — `r_t = (MV_t − trade_flow_t)/MV_{t−1} − 1`. The imported ledger-replay path's RISK statistics (beta / correlation / volatility / relative risk / volatility regime / factor model) now exclude the cash sleeve without reading a BUY as a gain; the investor-performance family (TWR, monthly returns, max drawdown) deliberately keeps the cash-inclusive basis. **Scoping correction:** cash is ~3% of NAV only at the window's END — the median weight is **5.60%** (range −1.91% .. 17.53%). Measured de-dilution: annualised volatility **14.54% → 15.47%** (×1.064 vs the cash-weight prediction ×1.059), comparing like-for-like. **Two findings surfaced by the AC9 tripwire:** (a) counting trades in UNPRICED symbols fabricated **+9.43%** on IB2026 2026-04-27 — fixed in-story by gating `trade_flow` on a per-day `is_valued` predicate; (b) the same unpriced symbols corrupt the cash-inclusive TWR — logged as **US-24.10** below. Goldens purely additive (209 states gain the field, zero value changes). |
| US-24.10 — unpriced-symbol cash events fabricate investor-performance returns | ✅ **RESOLVED (US-24.10, 2026-08-09)** | New **third valuation tier**: a symbol with no market history and no statement close is valued at the **last broker execution price at or before the day**, carried FORWARD only (no back-fill — US-27.7), converted from the trade's settle currency, and disclosed as `trade_price_anchored_symbols` (flat between trades). Precedence is history → statement close → trade price, never inverted, so every currently-priced or statement-anchored symbol behaves exactly as before. **Result on IB2026:** the two fabricated days are gone — 2026-04-08 TWR **−7.90% → +2.54%**, 2026-04-27 **+9.61% → −0.12%**; max daily TWR move **9.61% → 2.76%**; TWR annualised volatility **23.32% → 14.72%**; `unpriced_replay_symbols` empties (BTEC/IUFS/IUHC reclassified); terminal market value unchanged at $61,239.88 ($1.35 from the statement `stock_total`). **A second fabrication class was found and fixed in the same pass:** US-24.9's `trade_flow` gate ("is this symbol valued today") mis-handles a symbol first observed by its own SELL, and a **same-day round trip** in a new symbol — 2026-06-11 IITU, bought and fully sold before any close, in no day's market value, produced **−3.45%** against an expected −0.36%. Replaced by one state-derived rule (a leg counts only if the symbol is priced today or was priced yesterday), which subsumes the original unpriced case too. **Deferred:** rendering the replay disclosures — logged as **US-24.11** below. |
| US-24.11 — replay disclosures are computed but never rendered | ✅ **RESOLVED (US-24.11, 2026-08-09)** | New `ReplayDisclosuresCard` on the Dashboard renders all five `run_metadata` disclosures as prose notes on `CardShell` — each stating what was degraded AND what it affects, not a field dump. Renders nothing at all on a clean run, and shows the cash anchor only when its trust is not `verified`. **No Synthetic badge:** the imported replay is broker truth that has been degraded, a different truth class from synthetic history, and `TrustBadge` only speaks `Synthetic`/`Unavailable` (guardrail #2). `withheld` is rendered with the engine's own reason, never collapsed into `unavailable` (guardrail #3). Frontend-only: no schema, engine or methodology change; `dashboardGoldens.ts` byte-identical. Added to the design-system audit's `ALL_CARD_FILES`. +9 frontend tests. **Deferred:** extending `TrustBadge` with `verified`/`degraded`/`withheld` types is a design-system change affecting every card, and these notes read better as prose — recorded, not done. |
| US-26.3 — request path fabricates a currency for currency-less positions | Med — **NEW (logged by US-26.1, 2026-08-11)** | `portfolio_snapshot_builder.py:43` coerces `currency=item.currency or request.base_currency or 'USD'` when building an `ImportedPortfolioSnapshot` from a `PortfolioEngineRequest`. `PortfolioPositionSnapshot.currency` is `str | None`, so a caller may legitimately omit it — and the position then arrives at every downstream analytic labelled with the base currency (or a hardcoded `'USD'` when there is no base either). Guardrail #3: this is a silent fallback that fabricates provenance, and the **Currency Exposure card is where it matters most** — such a portfolio would read as 100% base-currency with no indication. The imported path is unaffected (`ImportedPosition.currency` is schema-required, 3 chars, so real statements always state it). Fixing it properly needs a way to represent "currency unknown" on `ImportedPosition`, which is a schema change touching persisted snapshots — hence its own story. US-26.1 deliberately did NOT add an "unclassified" bucket to paper over it, since the bucket could never fill while the coercion happens upstream. |

Anything not rolled up above is **low-severity / completeness-only** and may be
folded into US-24.7 or left as documented. The two **High** rows (US-24.1 latent
bugs) should lead Epic 24.

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
| frontend | `DashboardPerformanceChart.tsx` | dead-suspected | med | low | US-23.6 | whole file unimported (knip). **RESOLVED (US-23.6): removed** with its vacuous App.test.tsx suspense scaffolding. |
| frontend | `SectorDonutCard.tsx` | dead-suspected | med | low | US-23.4 | whole file unimported (knip) |
| frontend | `historyTruth.ts` | dead-suspected | low | low | US-23.4 | whole file unimported (knip) |
| frontend | `investorEconomics.ts` | dead-suspected | low | low | US-23.4 | whole file unimported (knip) |
| frontend | `src/app/portfolioDb.ts` `getPortfolioDatabaseName` | dead-suspected | low | low | US-23.4 | exported fn, 0 consumers |
| tests | `portfolioFixtures.ts` `createDiagnosticsFixture`, `createIb2026/Ff2026ImportedDashboardFixture`, `createImportedBaselineFixture` | dead-suspected | low | low | US-23.6 | exported fixture factories, never imported. **RESOLVED (US-23.6): removed** (4 dead leaf factories; the over-exported-but-live ones kept). |
| cross | `ImportAdmissionReviewDispositionV1` (BE `schemas/import_bootstrap.py`; FE `types.ts` + `portfolioWorkspaceStorage.ts` sanitizers; `import-admission-fields.md`) | dead-suspected | med | med | US-23.4 (FE) + US-23.2 (BE) | **The canonical cross-seam dead case** (US-22.2 close-out): no producer, no consumer; persistence sanitizers self-reference it so `knip` does NOT flag it. Remove FE plumbing first (with persisted-state safety checks), then BE schema, then reconcile the contract doc. Not deletable by a single story — coordinate. |
| backend/analytics-schemas | `analytics/attribution.py` (imports `WINDOW_MIN_OBSERVATIONS`, `_series_to_returns`) | dead-suspected | low | low | US-23.2 | ruff F401 unused imports |
| backend/analytics-schemas | `analytics/risk.py` (import `FactorRiskContribution`; locals `target`/`top_shared`/`alpha_annualized`/`specific_risk`/`collinearity_warnings`) | dead-suspected | med | med | US-23.2 | ruff F401/F841 + vulture — some unused locals may be a computed-but-dropped result; confirm intent (dead vs bug) before deleting |
| backend/analytics-schemas | `schemas/reconciliation.py` (imports `LedgerRecord`, `ImportedPortfolioSnapshot`) | dead-suspected | low | low | US-23.2 | ruff F401 unused imports |
| backend/services-routes | `services/dashboard_history_engine.py` local `allow_exact_slice_benchmark_return_output` | dead-suspected | low | low | US-23.3 | ruff F841 unused local. **RESOLVED (US-23.3): removed** — confirmed dead duplicate (live gating is the per-range call). |
| backend/services-routes | `importers/freedom24.py` locals `isin`, `realized_pnl`, `account` | dead-suspected | low | low | US-23.3 | ruff F841 — parsed-but-dropped; confirm not a missing-field bug |
| tests | test-file unused imports (`pytest`/`Path`/`math`) + unused locals (`test_analytics.py`, `test_market_data_fallback.py`, `test_yfinance_client.py`, `test_exposure_engine.py` unreachable-after-return) | dead-suspected | low | low | US-23.6 | ruff + vulture; test hygiene. **RESOLVED (US-23.6): removed** (12 F401 imports + 3 F841 locals); ruff clean. |

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
| backend/importers | `importers/freedom24.py:138,221,266` `isin`, `realized_pnl`, `account` | dead-suspected / parsed-but-dropped | med | low | US-23.3 | Broker-statement fields parsed then dropped. **RESOLVED (US-23.3): investigated vs schema, kept under `# noqa: F841` + re-catalogued** in the US-23.3 section above (`isin` = real data gap, `realized_pnl` = unmodeled scope, `account` = benign). Not deleted (evidence preserved). |
| backend/services | `services/dashboard_history_engine.py` `allow_exact_slice_benchmark_return_output` | dead-suspected | low | low | US-23.3 | F841 unused local. **RESOLVED (US-23.3): removed** as a dead duplicate (not a dropped-flag bug — the live gating is the per-range call). |

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
| backend/analytics-schemas | `analytics/activity.py:24` | anti-pattern / latent-bug | high | low | epic-24 | `if entry.date.year != 2025:` — the activity summary **silently drops every ledger entry not dated 2025**. Breaks for any 2026+ statement. **RESOLVED (US-24.1): filter removed** (the `%Y-%m` bucketing + the snapshot-scoped ledger handle the period). |
| backend/analytics-schemas | `analytics/reconciliation.py:24` | anti-pattern / latent-bug | high | low | epic-24 | `candidate.date.year == 2025` in the withholding-tax reconciliation filter — same hardcoded-year class as activity.py; non-2025 withholding entries are excluded. **RESOLVED (US-24.1): filter removed** (now consistent with the sibling dividends/fees/interest/deposit actuals, which never year-filtered). |

**Hardcodes / magic numbers / fragile coupling:**

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/analytics-schemas | `analytics/reconciliation.py:10` | hardcode / fragile-coupling | med | low | epic-24 | `fx_rates.get("EURUSD", 1.0)` — hardcoded FX pair key + 1.0 fallback bakes in an EUR-base assumption; multi-currency statements silently use 1.0. |
| backend/analytics-schemas | `analytics/reconciliation.py:63` | magic-number | med | low | epic-24 | `abs(difference) <= 0.25` — undocumented cash-reconciliation tolerance (0.25 units). No named constant, no citation. |
| backend/analytics-schemas | `domain/ledger.py:67-92` | fragile-coupling | med | med | epic-24 | Broker-statement section labels hardcoded into the domain layer ("Trades", "Deposits & Withdrawals", "Dividends", "Income Summary", "Cash deposits/ withdrawals", "Withholding Tax", "Account Summary", "Fees", "Other Fees", "Commissions"). IBKR/Freedom24 statement format leaks into ledger classification; a label rename silently mis-classifies entries. |
| backend/analytics-schemas | `domain/ledger.py` + analytics (`activity.py:12-19`, etc.) | missing-abstraction | low | med | epic-24 | Entry-type strings (`BUY`/`SELL`/`DIVIDEND`/`INTEREST`/`FEE`/`WITHHOLDING_TAX`/`DEPOSIT`/`WITHDRAWAL`) used as a pseudo-enum across domain + analytics with no shared `Literal`/`Enum` — typo-prone, no single source of truth. |
| backend/analytics-schemas | `domain/ledger.py:158` & `schemas/portfolio.py:9,19` & `portfolio_engine.py` | hardcode | low | low | epic-24 | `"USD"` default base/trade currency repeated across schema defaults + ledger; assumes USD when base currency is absent. |
| backend/analytics-schemas | `analytics/risk.py:138-142` (`STRESS_SCENARIOS`) | hardcode | med | med | epic-24 | Three stress-scenario factor-shock vectors (Broad Market Selloff / Rates Down Risk-On / Inflation Reacceleration) hardcoded inline as a tuple-of-dicts. Surfaced on the Risk tab; methodology-documented but the shock magnitudes are inline data, not a reviewable config. |
| backend/analytics-schemas | `analytics/risk.py:196,232-233,241,248,256,264` | magic-number | med | high | epic-24 | Mapping-match composite scoring weights inline across `_compute_*`. **RESOLVED (US-24.2): → named `MAPPING_SCORE_*` / `EQUITY/BOND/COMMODITY_EXPOSURE_*` / `STRUCTURE_FIT_*` / `IMPLEMENTATION_FIT_*` constants** with a one-line "heuristic, no academic basis" rationale. |
| backend/analytics-schemas | `analytics/risk.py:275-288` | magic-number | med | low | epic-24 | Mapping hard-cap ceilings (`50.0/45.0/60.0/25.0/70.0`) + reason strings inline in `_apply_mapping_hard_caps`. **RESOLVED (US-24.2): → `MAPPING_HARD_CAP_*` named constants.** |
| backend/analytics-schemas | `analytics/risk.py:293-304,335-470,1055-1064` | magic-number | med | high | epic-24 | Dense inline score literals across the mapping-quality scoring helpers. **PARTIALLY RESOLVED (US-24.2):** the label thresholds (`_mapping_match_label`), `_cost_fit_score` / `_mapping_quality_score` quality maps → named constants. The leaf per-token `_*_score` branch literals (`_index_match_score` etc.) stay inline (rubric body — deferred, low value). |
| backend/analytics-schemas | `analytics/risk.py:1613-1627,1665-1677` (pre-fix location) | hardcode / fragile-coupling | med | med | epic-24 | Sector inference from hardcoded proxy-ticker lists (`_infer_sector_from_sources`, `_infer_sector_from_resolved_pair`): e.g. `["XLF"]→Financials`, `["ITA","PPA"]→Defense`, `["BIL","VGSH"]→Fixed Income`. Duplicated across two functions; overlapped the `InstrumentRegistry` sector source of truth. **RESOLVED (US-38.1 / Epic 38, F-B): both functions deleted, replaced by the static-registry-or-"Unclassified" rule** (`build_lookthrough_sector_exposure`, `_build_shared_sector_overlap`); the eight ETF tickers the lists referenced but the registry didn't curate (`XLF`/`XLV`/`IBB`/`ITA`/`PPA`/`BIL`/`VGSH`/`DBC`) are now curated in `INSTRUMENT_DEFINITIONS`. F-B's separate, narrower "ETF-side FMP sector reliability" observation (US-37.1 Out of scope) is unaffected and remains open — re-deriving ETF-level sector classification from FMP directly stays explicitly out of scope per US-38.1. |
| backend/analytics-schemas | `analytics/risk.py:1262-1267` | magic-number | low | low | epic-24 | Volatility-regime percentile cutoffs inline (`< 0.30` calm, `<= 0.80` normal, else stressed). |
| backend/analytics-schemas | `analytics/risk.py:1331` | magic-number | low | low | epic-24 | `len(common_dates) < 10` minimum-history gate for the factor model — undocumented literal (distinct from the named `WINDOW_MIN_OBSERVATIONS`). |
| backend/analytics-schemas | `analytics/risk.py:750-751,1441` | magic-number | low | low | epic-24 | Top-N display slices hardcoded: top over/under-weights `[:5]`, top shared constituents `[:15]`. |
| backend/analytics-schemas | `analytics/risk.py:1038,1040-1052` | hardcode | low | med | epic-24 | `build_factor_exposures` hardcodes the growth-tilt sector composition and the full factor-exposure label/description/basis list inline. |
| backend/analytics-schemas | `analytics/risk.py:122-136` | magic-number (documented) | low | low | epic-24 | Module-level threshold constants are **named** (`COLLINEARITY_WARNING_THRESHOLD=0.85`, `SHIFT_FLAG_20D_THRESHOLD=0.25`, `SHIFT_FLAG_60D_THRESHOLD=0.35`, `STABILITY_GAP_THRESHOLD=0.30`, `VOLATILITY_RATIO_FLAG_THRESHOLD=1.2`, `WINDOW_MIN_OBSERVATIONS`, `ROLLING_RIDGE_FLOOR`) — good practice; listed for completeness. Only gap: no academic/methodology citation beside each value. |
| backend/analytics-schemas | `analytics/drawdown.py:353` | magic-number | low | low | epic-24 | `abs(residual_pct) < 0.001` decomposition-residual epsilon inline (also `top_n` cap at :157). |
| backend/analytics-schemas | `analytics/distribution.py:67-71` | magic-number | low | low | epic-24 | Percentile fractions inline (`0.05/0.10/0.50/0.90/0.95`). Contract-defined and keyed; `_MIN_OBSERVATIONS`/`_DEFAULT_HISTOGRAM_BINS` are already named constants — low concern. |
| backend/analytics-schemas | `analytics/correlation.py:70,123` | magic-number (documented) | low | low | epic-24 | `min_observations: int = 20` default (matches the methodology min-observations); param-exposed and documented — listed for completeness. |
| backend/analytics-schemas | `instruments/registry.py:45-48,180-261` | hardcode / fragile-coupling | low | med | epic-24 | Hardcoded instrument reference data (futures `tick_size`/`point_value`/`multiplier`; ETF→sector defs) — reference data, acceptable (documented in the `fmp-data` skill), untouched. **RESOLVED for the direct-held ETF branch (US-39.1): the keyword-substring `sector` classifier in `classify_imported_instrument`'s ETF branch (formerly a `sector = "Broad Market"` default plus ~9 keyword `elif` branches) is removed, replaced by identity-gated, dominance-thresholded FMP `etf/sector-weightings` resolution** (`etf_sector_resolution.py::resolve_etf_sector`) or `"Unclassified"` — no more silent `"Broad Market"` default. `category`'s own keyword-substring derivation in the same branch is unaffected (out of scope for US-39.1) and stays as-is. |
| backend/analytics-schemas | `schemas/correlation.py:13`, `intra_correlation.py:22,24`, `provenance.py:21`, `distribution.py:31` | magic-number (documented) | low | low | epic-24 | Window/lookback `Field` defaults (`252`, `60`, `15`, `30`). Sensible, validated (`ge=`) defaults — listed for completeness; consider a shared windows config if they ever need to align. |
| backend/analytics-schemas | `analytics/risk.py:1654` (`_build_shared_sector_overlap`'s `market_data: HoldingsMarketData` parameter); call site `risk.py:1531` | dead-suspected | low | low | epic-24 | Unreferenced in the function body since US-38.1 removed the live FMP look-through fallback it fed — confirmed by direct code reading (`05-technical-plan.md` § T-40.1.3). **Not caught by `detect_deadcode.py --strict`**: vulture's `--min-confidence 80` doesn't flag unused function parameters the way it flags unused locals/functions (confirmed by a live run, clean/zero findings). Whenever picked up, both the parameter and its single call-site argument must be dropped in the same pass (US-40.1 close-out). |

#### US-23.3 catalog — `services/` + `api/` + `clients/` + `core/` + `importers/` (recorded, not fixed → Epic 24)

Wiring-tier sweep (AC4). Detectors after the US-23.3 removal are **clean**
(`ruff F401/F811/F841` pass; `vulture --min-confidence 80` finds no whole-program
dead routes/methods/classes in these trees). Dead code removed this pass: the
discarded duplicate `allow_exact_slice_benchmark_return_output` computation in
`dashboard_history_engine.py` (the live gating is the per-range call at ~L676 →
`_compute_visible_summary`). The 3 Freedom24 parsed-but-dropped locals were
**kept** with reasoned `# noqa: F841` (preserving the statement-layout map + the
data-gap evidence) rather than deleted. `core/` is exemplary (all config is
settings-driven with named defaults) — no findings.

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/services-routes | `importers/freedom24.py` (`isin`) | parsed-but-dropped / data-gap | med | med | epic-24 | **CORRECTED + RESOLVED (US-24.4): not a gap.** `_parse_instruments` already flows ISIN to `ImportedInstrument.isin` (pinned by the FF2026 test). The `_parse_positions` `isin` copy was dead offset-walk code (positions don't model ISIN) — removed. |
| backend/services-routes | `importers/freedom24.py:221` (`realized_pnl`) | parsed-but-dropped / scope | med | med | epic-24 | Freedom24 parses per-trade realized P&L but `ImportedLedgerEntry` has no realized-P&L field. **US-24.4: dead binding removed (now a documented offset comment); modeling deferred** — adding a realized-P&L field is a schema change with contract impact, out of US-24.4 scope. Revisit if the product needs it. |
| backend/services-routes | `importers/freedom24.py` (`account`) | parsed-but-dropped | low | low | epic-24 | Per-line account identity parsed then dropped; account is modeled at statement level (`ImportedStatement.account_id`). **RESOLVED (US-24.4): dead binding removed** (offset documented by comment). |
| backend/services-routes | `importers/freedom24.py` (positional parsing, ~50 sites) | fragile-coupling | high | high | epic-24 | Fixed-offset positional PDF reading. **PARTIALLY RESOLVED (US-24.4): each of the 5 parsers is now fail-safe** — a malformed/non-numeric record is skipped + parsing continues (a layout drift yields a partial snapshot surfaced by reconciliation, not a crash or silent mis-parse); page indices are named constants. A **full** parser rewrite (table-structure detection vs fixed offsets) remains a deferred follow-up. The fail-safe-parsing follow-up for `interactive_brokers.py` / `espp.py` is **RESOLVED (US-24.8): IBKR hardened** (post-match numeric/date conversions now degrade a field/record instead of raising); **ESPP investigated and found not to need it** — its regex groups (`[\d,]+\.\d+`) cannot capture a value that fails `float()`, so there is no reachable failure to guard. |
| backend/services-routes | `importers/freedom24.py:146,223,238` | hardcode | low | low | epic-24 | Inline currency whitelist; `.replace(".US","")`; hardcoded `currency="USD"`; magic page indices. **RESOLVED (US-24.4): → named constants** (`_KNOWN_CURRENCIES`, `_US_SUFFIX`, `_DEFAULT_CURRENCY`, `_PAGE_*`). |
| backend/services-routes | `clients/fmp.py:33` | magic-number | med | low | epic-24 | `httpx.Client(timeout=30.0)` — HTTP timeout hardcoded; everything else in the client (TTLs, rate limit, base URL) is settings-driven — this should be too. |
| backend/services-routes | `clients/fmp.py:183` | hardcode / fragile-coupling | med | low | epic-24 | `get_etf_holders` hardcodes the full URL `https://financialmodelingprep.com/api/v3/etf-holder/{symbol}` — the only endpoint that bypasses the settings-driven `self.base_url` (`/stable`). Host + `api/v3` version pinned inline. |
| backend/services-routes | `clients/fmp.py:248` | magic-number | low | low | epic-24 | `limit: int = 500` screener default inline. |
| backend/services-routes | `services/{exposure,stress,drift,drawdown}_engine.py` (`'SPY'`) | hardcode / duplication | low | low | epic-24 | Default benchmark `"SPY"` hardcoded in ≥4 engines + `SnapshotAnalysisRequest` default. **RESOLVED (US-24.3): → `DEFAULT_BENCHMARK_SYMBOL`** in `app/core/constants.py` (schemas + engine fallbacks). |
| backend/services-routes | `services/exposure_engine.py:251` | magic-number | med | low | epic-24 | `loaded_weight >= 99.0` ETF-holdings coverage threshold gates `verified` vs `degraded` — undocumented literal driving a trust decision. **RESOLVED (US-24.2): → `BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT`.** |
| backend/services-routes | `services/stress_engine.py:36`, `drawdown_engine.py:52`, `attribution_engine.py` | duplication | med | med | epic-24 | The lookback heuristic `math.ceil(window * 1.6) + 30` re-implemented in ≥3 engines. **RESOLVED (US-24.3): → one shared `lookback_calendar_days`** in `app/core/constants.py` (6 engines now import it). |
| backend/services-routes | `services/drawdown_engine.py:34`, `analytics/distribution.py:23`, `analytics/correlation.py` | duplication | low | low | epic-24 | `_MIN_OBSERVATIONS = 20` defined independently in ≥3 modules (+ correlation/distribution/intra-correlation engines). **RESOLVED (US-24.3): → shared `MIN_DAILY_OBSERVATIONS`** in `app/core/constants.py`. |
| backend/services-routes | `services/portfolio_proof.py:1264` | magic-number | low | low | epic-24 | `_terminal_totals_match(... tolerance: float = 0.01)` — reconciliation tolerance inline (cf. the `0.25` cash tolerance in `analytics/reconciliation.py`). |
| backend/services-routes | `services/statement_importer.py:190` | magic-number | low | low | epic-24 | Percent→fraction `/100` conversion inline in the TWR compounding loop. |
| backend/services-routes | `services/exposure_engine.py:137-144` (`_build_exposure_source_status`'s `lookthrough_resolution`) vs `:181` (`_build_exposure_availability`'s `lookthrough_status`) | duplication | med | med | epic-24 | Two functions independently reimplement the identical three-way classification conditional over the identical inputs; `run_metadata.confidence` is a pure recombination of two fields `availability` already carries. Real duplication (same shape as the US-34.8 `risk.py` case), found while closing US-40.1's trust-source retirement (`03-quant-research.md` § Duplication finding, `05-technical-plan.md` § Duplication finding disposition). **NOT fixable as a plain hardcode extraction** — per project guardrail 1, any change touching a trust classification needs a quant-research pass first, since simplifying the derivation changes *how* a trust-classification value is computed, not just where the constant lives. Deliberately not folded into US-40.1 (a doc-only, zero-behavior-change story). |
| backend/services-routes | `core/` (settings/cache/symbols) | (good hygiene — no action) | — | — | — | Noted as the positive baseline: `settings.py` keeps all config in named `Field(default=…)` (TTLs `300`/`86400`, rate-limit `250`, base URL, artifact dirs); `cache.py` is clean; `symbols.py` `DEFAULT_SYMBOL_RULES` is documented reference data (`fmp-data` skill). The `except Exception: # noqa: BLE001` fail-closed handlers in `fmp.py`/`yfinance_client.py` are intentional (per story Notes) — not smells. |

#### US-23.6 catalog — test suites (recorded, not fixed → Epic 24)

Test-hygiene sweep (AC5) + the AC1 fixture-migration decision. Dead code removed
this pass: 12 `F401` unused test imports + 3 `F841` dead test locals (backend);
`DashboardPerformanceChart.tsx` + its App.test.tsx scaffolding + 4 dead leaf
fixture factories (frontend) — see "Removed" below. The 4 remaining knip-flagged
fixtures (`createImportedFixtureParts` / `createImportedDashboardFixture` /
`createDashboardHistoryRunMetadataFixture` / `createDiagnosticsRunMetadataFixture`)
are **over-exported but live** (called transitively by `createExposureEngineFixture`
/ `createDiagnosticsEngineFixture` / `createImportedDashboardHistoryFixture`) — not
dead; covered by the "Over-exported (live, not dead)" section above.

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| tests | backend test files hand-rolling snapshot builders: `test_correlation_engine.py:140` `_minimal_snapshot`, `test_exposure_engine.py:94` `_build_snapshot`, `test_provenance_engine.py:15,77` `_snapshot*`, `test_analytics.py:210` `_sample_snapshot`, `test_intra_correlation_engine.py:120` `_snapshot`, `test_import_admission.py:16` `_snapshot`, `test_instrument_enrichment.py:39` `_make_snapshot`, `test_attribution.py:26` `_make_daily_states`, `test_drawdown_analytics.py:191` `_state` | duplication | low | med | epic-24 | **AC1 decision — migration deferred with reason (not a wholesale migrate):** these duplicate `app/tests/fixtures.py` builders, but many return route-payload **`dict`s** (422-proof for `TestClient` POSTs) whereas `fixtures.imported_snapshot()` returns a **Pydantic model** for engine inputs — they serve route-test vs engine-test needs and are per-test tuned. Wholesale migration is low-value / higher-risk (could subtly change inputs); migrate opportunistically in Epic 24. Only 5 test files currently import the shared module. |
| tests | `test_analytics.py::test_build_portfolio_risk_summary_and_position_contributions` | missing-coverage | low | low | epic-24 | The test name promises position-contributions coverage but the body never calls `build_position_risk_contributions` — the `snapshot` + `price_histories` locals (its would-be inputs) were dead and removed this pass. Adding the missing assertion is out of US-23.6 scope (coverage expansion → Epic 24). |
| tests | `test_importer.py` (`test_three_broker_combine_ib_ff_espp` and siblings `test_combine_imported_snapshots_merges_sequential_ib_statements`, `test_combine_imported_snapshots_allows_mixed_broker_same_currency_imports`, `test_multi_year_combination_does_not_backfill_fake_pre_funding_positions`) | missing-coverage / fragile-coupling | med | low | epic-24 | Each guards on `if not <path>.exists(): return` for `docs/IB2026.pdf` / `docs/U8516450_20260101_20260408.pdf`. Neither file is present in this checkout (pre-existing, predates US-40.2 — confirmed via `Path.exists()`), so every one of these tests hits its early `return` and pytest reports `PASSED` without ever exercising real distinct-account combine data — a skip disguised as a pass. Surfaced by `10-quant-reaudit.md` (2026-08-25) while re-verifying US-40.2's CR-1 account-identity fix; the re-audit substituted independent synthetic scripts rather than trust the silent no-op. Fix is either committing the two golden PDFs or converting these tests to a committed-fixture-independent synthetic construction. |

### Removed (completed)

- **US-23.4** (frontend, this pass): deleted 6 unimported files (`featureFlags.ts`, `portfolioState.ts`, `CurrentFactorSnapshotCard.tsx`, `SectorDonutCard.tsx`, `historyTruth.ts`, `investorEconomics.ts`); 5 dead types (`ActivityPoint`, `CanonicalLedgerRecord`, `ReconciliationCheck`, `DiagnosticsPayload`, `ExposureEnginePayload`); dead helper `getPortfolioDatabaseName`. knip: 7→1 unused files, 65→60 types, 22→21 exports. tsc + suite green.
- **US-23.2** (backend): removed 5 F401 unused imports (`attribution.py`, `risk.py`, `reconciliation.py`).
- **US-23.2** (backend, risk.py dead-computation sweep — investigated, confirmed not bugs): removed the dead full-period OLS block in `_build_statistical_factor_model` (the global `_orthogonalize_factor_series` call + `_fit_factor_model` fit + the discarded `alpha_annualized` / `specific_risk` / `collinearity_warnings` locals — none reached the `StatisticalFactorModel` response; methodology forbids surfacing the "alpha"); the dead `top_shared` `MarketOverlapConstituent[]` build in the market-overlap summary (superseded by `top_overweights`/`top_underweights`); the dead `target` local in `_apply_mapping_hard_caps`. Cascade: also removed the now-orphaned `_orthogonalize_factor_series` function, the `portfolio_names` local, and the dead `MarketOverlapConstituent` schema class (no TS/contract/test consumer). **Output-neutral** — goldens unchanged, full suite green; also drops a wasted full-period OLS fit per analysis.
- **US-23.6** (tests, backend + frontend): **backend** — removed 12 `F401` unused imports across 8 test files (`pytest`/`Path`/`math` + unused schema imports) and 3 `F841` dead locals (`test_analytics.py` `snapshot`/`price_histories`, `test_drawdown_analytics.py` `top_returns`); ruff clean. **Frontend** — removed `DashboardPerformanceChart.tsx` (no production importer — knip-confirmed) together with its now-vacuous App.test.tsx scaffolding (the `vi.hoisted` suspense mock, the `vi.mock(...)` of the component, the `afterEach` reset, and the suspense test, which could not exercise a real suspense boundary because App never renders the component); plus 4 dead leaf fixture factories (`createIb2026ImportedDashboardFixture`, `createFf2026ImportedDashboardFixture`, `createImportedBaselineFixture`, `createDiagnosticsFixture` — zero callers). The over-exported-but-live fixtures were intentionally kept. tsc clean; 233 desktop tests green (was 234 — the one removed test was the vacuous suspense test); backend suite green; goldens untouched.
- **US-23.3** (backend, services/api/clients/core/importers): removed the dead **duplicate** `allow_exact_slice_benchmark_return_output` computation in `dashboard_history_engine.py` (top-level `run` path) — investigated and confirmed dead: the result was discarded while the **live** gating is the per-range call (`~L676` → `_compute_visible_summary`); benchmark withholding at `_withhold_benchmark_return_series` is independent and unchanged. **Output-neutral** — goldens unchanged, full suite green; drops a wasted function call per dashboard run. The 3 Freedom24 F841 locals (`isin`/`realized_pnl`/`account`) were investigated against the schema and **kept** under reasoned `# noqa: F841` (parsed-but-dropped: `isin` is a real coverage gap, `realized_pnl` is unmodeled, `account` is benign) rather than deleted — see the US-23.3 catalog above. `vulture --min-confidence 80` finds no whole-program dead symbols in these five trees.

### Remaining (deferred within Epic 23)

- **US-23.4 — empty feature dirs (resolved, not dead):** `src/features/market-data/` and `src/features/settings/` contain **only a `README.md`** each — intentional placeholders for unbuilt features (part of the documented repo layout in `CLAUDE.md`). Not dead code; left as-is (AC3 "documented").
- **US-23.4 — `DashboardPerformanceChart.tsx` (deferred → US-23.6): RESOLVED in US-23.6.** The file was unimported (knip) and coupled to App.test.tsx scaffolding (`vi.hoisted` `dashboardPerformanceChartMock`, the `vi.mock(...)`, the reset, and the suspense test). Investigation confirmed the suspense test was **vacuous** — App never renders the component, so `shouldSuspend=true` could not trigger a real suspense boundary and the assertions passed trivially. Removed the file + all four scaffolding pieces together.
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

- **US-23.2/23.3:** the F841 items above (freedom24 / dashboard_history_engine) were resolved in US-23.3 (dashboard duplicate removed; freedom24 locals kept under reasoned `# noqa` + catalogued); the disposition BE schema was removed in US-23.9.

### Deferred findings — 2026-08-26 Performance & Benchmark chart audit (not Epic 23/24)

These four items were surfaced by a review/audit run (not a story or epic —
`.agentic/runs/2026-08-26-performance-benchmark-chart-audit`) that fixed two
real bugs in the Dashboard's Performance & Benchmark card (US-25.1 / US-27.8
lineage): a fabricated chart line (raw NAV ratio instead of the TWR-indexed
`portfolio_return_pct` chain) and a chart that ignored the range selector
entirely. Three further findings from the same run were explicitly **not**
fixed — by human decision, routed here instead of a code/doc edit. None of
these are dead code or a hardcode in the Epic 23/24 sense, so the four
category values below extend the Entry schema's enum with `doc-gap` and
`typing-precision` for this section only.

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| finance-docs | `docs/finance/financial-methodology.md` §Indexed Return Series, "Implementation:" list (~line 2253-2257) | doc-gap | med | low | none (open) | The list names only `services/quant-engine/app/services/drift_engine.py` (the Exposure-tab drift panel). It omits `app/analytics/performance.py::build_true_performance_series` (the shared TWR daily-return chain that actually feeds `performance_series[].portfolio_return_pct`) and `PerformanceBenchmarkCard.tsx::buildIndexedSeries` (the Dashboard chart's consumer of it) — a guardrail-2 traceability gap: a reader following the section's own pointer lands in a different card's engine module. **Source: `cr/CR-2.md` CHANGE REQUEST 2 (SHOULD_FIX, round 1) — explicitly not fixed this run per this order's `non_goals`.** Fix: add both names to the list, worded so it's clear the section governs two cards (Dashboard performance, Exposure drift) via two separate code paths implementing the same documented formula family, not one shared implementation. |
| backend/services-routes | `services/dashboard_history_engine.py:400-419` (`run_dashboard_history_engine`) | doc-gap | low | low | none (open) | The non-imported `/run` route's two branches (missing `history_context` vs present) both unconditionally call `_build_unavailable_dashboard_history_result` — the function never computes anything. Judged an intentional, architecturally-correct fail-closed stub (the investor-performance family needs ledger-derived cash-flow dates a non-imported snapshot doesn't carry; computing anything would mean fabricating cash-flow assumptions, guardrail 4), but that reasoning lives nowhere at the point of implementation, so a zero-comment function whose both branches converge on "unavailable" reads exactly like an unfinished stub to the next engineer. **Source: `cr/CR-2.md` CHANGE REQUEST 3 (SHOULD_FIX, round 1) — explicitly not fixed this run per this order's `non_goals`.** Fix: a short comment stating this is permanently unavailable-only, not a partial implementation to be finished later. No behavior change. |
| finance-docs | `app/schemas/dashboard_history.py:51-61` (docstring) / `docs/finance/financial-methodology.md` §Indexed Return Series (no mention) | doc-gap | low | low | none (open) | `window_start_date` silently means two different things for two range kinds: for 1M/3M/1Y it is the last daily state strictly *before* the window's first counted day (a "day zero" baseline outside the window); for YTD it is the year's own first trading day (*inside* the window). Not a wrong number — chart and summary strip use the identical convention per range, confirmed consistent — but a future engineer extending `window_start_date` to a new range kind could pick either convention without knowing two already coexist. **Source: `10-quant-audit.md` §Log/4, FINDING 1 (MINOR, non-blocking) — not fixed this run.** Fix: a one- or two-line note near the `window_start_date` docstring (or in the methodology section, alongside the CR-2 #2 pointer fix above) stating YTD's anchor is inside the window while the sliding windows' anchor is outside it. |
| frontend | `apps/desktop/src/features/portfolio/types.ts:553` (`DashboardRangeMetrics.window_start_date`) | typing-precision | low | low | none (open) | Typed `window_start_date?: string \| null` (optional) where the backend always serializes the field as `string \| null` (07-backend.md's contract note asked for the strict form). Judged safe-direction / non-blocking: `PerformanceBenchmarkCard.tsx` normalizes via `metrics.window_start_date ?? null` before use, so an absent key and an explicit `null` behave identically, and the sibling `portfolio_return_trust?:` field in the same type is the same established optional-on-a-backend-guaranteed-field shape. Worth tightening for precision — doing so would also force `portfolioFixtures.ts`'s `createImportedDashboardFixture` (currently supplies **no** `window_start_date` in any of its five `range_metrics` entries) to give real, distinct per-range values, closing a latent gap where any future test rendering the card off the shared fixture without an inline override would silently exercise the exact "chart ignores the range selector" shape CR-2 #1 fixed, and pass. **Source: `11-integration.md` § Typing judgment (DoD 2) and § Fixture coverage footgun — routed to Open, not a CR, not fixed this run.** |

### Engine seam consolidation — 2026-09-02 architecture review (→ Epic 43)

Surfaced by an `/improve-codebase-architecture` review of the quant-engine hot
spots (the areas the last ~60 commits keep touching). Four **shallow seams**:
an interface leaks, or a concept has no module and is re-implemented as private
helpers across several engines. All four are addressed in **Epic 43 — Engine
Seam Consolidation** (`docs/product/prd/epic-43-engine-seam-consolidation.md`),
each as a **behaviour-neutral relocation** — the goldens stay byte-identical.
Category `missing-abstraction` / `fragile-coupling` per the Entry schema.

| area | file:line | category | severity | effort | owner-story | note |
|---|---|---|---|---|---|---|
| backend/services-routes | `services/diagnostics_engine.py:774` (`_build_synthetic_snapshot_history_states_with_coverage`) + `:761` | missing-abstraction / fragile-coupling | med | med | US-43.1 | The Synthetic History truth class (`CLAUDE.md` → Truth Classes) is reconstructed by a **private** helper in the diagnostics engine, yet imported across the seam by **five** other engines — `attribution_engine.py:24`, `correlation_engine.py:35`, `distribution_engine.py:25`, `drawdown_engine.py:26`, `stress_engine.py:26`. Fix: move to a new `services/synthetic_history.py`, public names; rewire the 6 consumers. `test_correlation_engine.py:310` patches the name on the *consuming* module, so the patch target survives the move. Behaviour-neutral. **RESOLVED (US-43.1, 2026-09-02): new `services/synthetic_history.py` holds the public `build_synthetic_snapshot_history_states` / `..._with_coverage`; all six consumers (diagnostics, attribution, correlation, distribution, drawdown, stress) rewired to import it; goldens byte-identical; full suite green.** |
| backend/analytics-schemas | `analytics/risk.py` (factor-model internals: `_fit_factor_model:1741`, `_orthogonalize_factors_window:1698`, `_selected_history_return_series:871`; constants `FACTOR_KEY_MAP` / `FACTOR_PROXY_MAP` / `DEFAULT_FACTOR_DEFINITIONS` / `ROLLING_RIDGE_FLOOR`; `ReturnBasis:62`; `FactorDefinition:98`) | missing-abstraction | med | med | US-43.2 | Four modules reach across the seam into `risk.py`'s factor-model internals: `analytics/attribution.py:28` imports three `_private` factor-model helpers + four bare constants + `ReturnBasis`; `services/stress_engine.py:18`, `services/attribution_engine.py:21` and `services/diagnostics_engine.py:6` each import `FACTOR_PROXY_MAP` (and `stress_engine.py` also `STRESS_SCENARIOS`). `risk.py` is 2,295 lines / ~30 public `build_*` across six unrelated concerns. **Leak-first only:** move the factor-model internals + factor-definition data to a new `analytics/factor_model.py` (`risk.py` imports them back, keeps `build_statistical_factor_model`); move the `ReturnBasis` execution-basis literal to `schemas/return_basis.py` (beside the existing `ReturnBasis*` family). Retarget ~4 `monkeypatch.setattr(risk_module, …)` sites in `test_analytics.py`. **A full `risk.py` split (the other five concerns) is a separate, tracked follow-up — not Epic 43.** Behaviour-neutral. **RESOLVED (US-43.2, 2026-09-02):** new leaf module `analytics/factor_model.py` holds `UcitsCandidateMapping`, `FactorDefinition`, `DEFAULT_FACTOR_DEFINITIONS`, `FACTOR_PROXY_MAP`, `FACTOR_KEY_MAP`, `ROLLING_RIDGE_FLOOR`, `ORTHOGONALIZATION_ZERO_RESIDUAL_THRESHOLD`, `orthogonalize_factors_window` + `fit_factor_model` (the two `def` names lost their leading underscore); all four consumers above rewired to `analytics.factor_model`. **AC3 linalg disposition:** `_least_squares` / `_solve_linear_system` / `_dot` moved into `factor_model.py` and kept underscore-private — recon confirmed zero non-factor callers remained in `risk.py`, which does not re-import them. **AC1 amendment:** `selected_history_return_series` (and its private helper `_series_to_returns`) stayed in `risk.py`, renamed from `_selected_history_return_series` to a public name, to avoid a `risk.py` ↔ `factor_model.py` import cycle via `select_history_price_series`. `ReturnBasis` literal now in `schemas/return_basis.py`, imported by `risk.py`, `attribution.py`, `diagnostics_engine.py`. Goldens byte-identical; quant-audit char-diff PASS; integration + acceptance gates PASS; full suite green (backend 982). |
| backend/services-routes | `services/dashboard_history_engine.py` (`_build_dashboard_section_trust:133`, `_allow_dashboard_drawdown_outputs:237`, `_has_any_symbol_price_history:720`, `_has_replay_outputs:724`, `_classify_portfolio_return_basis:162`, `_build_dashboard_return_basis_contract:187`, investor-economics status builders) + `services/diagnostics_engine.py` (`_resolve_section_trust:182`, `_allow_diagnostics_drawdown_outputs:209` + `_apply_diagnostics_drawdown_output_policy:213`, `_has_any_symbol_price_history:952`, `_build_diagnostics_investor_economics_status:258`) | missing-abstraction / duplication | med | med | US-43.3 | The trust ladder (`verified > degraded > withheld > unavailable` — guardrail #3) has no module; it is parallel private helpers in the two largest engines. `_has_any_symbol_price_history` is a **byte-for-byte copy**. Fix: a new `services/trust_gate.py` holding both `SectionTrust` builders (**kept as two engine-qualified functions** — different section shapes and inputs), both drawdown output-admission gates, both investor-economics status builders, and the dashboard return-basis classification helpers; **merge only** the byte-identical `_has_any_symbol_price_history`. Behaviour-neutral. **Not in scope:** unifying the two `SectionTrust` builders or the two return-basis paths — that changes *how* a trust value is computed and needs a quant-research pass first (cf. US-40.1 duplication finding); left OPEN. **RESOLVED (US-43.3, 2026-09-03):** new leaf module `services/trust_gate.py`; 14 trust helpers moved verbatim (bodies unchanged apart from the leading `_` dropping, plus the one sanctioned rename `_resolve_section_trust` → `build_diagnostics_section_trust`) + the module constant `DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED` (rode along with the dashboard partial-unlock helper). Single merge: `has_any_symbol_price_history`, byte-identical in both engines → one public function. Both engines import every relocated name from `trust_gate`; the former `diagnostics_engine → dashboard_history_engine` cross-import is removed. AC1 extended by `build_diagnostics_drawdown_summary` — the tail of the drawdown output-admission pair AC1 half-moved; single call site; verbatim (design ruling `.agentic/runs/2026-09-03-us43.3-trust-gate-module/02-technical-plan.md` § A, human-approved). Goldens byte-identical; quant-audit char-diff PASS (anchor = pre-move git blob 04cd099); integration + acceptance gates PASS; full suite green (backend 984). |
| backend/services-routes | `services/import_engine_composer.py` (whole file, 36 lines) | anti-pattern / duplication | low | low | US-43.4 | Exposes one function, `compose_import_bootstrap_response`, that only fills an `ImportedBootstrapResponse` from kwargs `import_engine.py` passed through unchanged. Deletion test: folding it into `import_engine.py` concentrates nothing — one hop removed. `import_engine.py` is its only importer anywhere in `app/`. Fix: fold the body in as `_compose_import_bootstrap_response`, delete the file. Behaviour-neutral. |

**Recorded, NOT scheduled — need a methodology-reviewed story, not a relocation:**

- **The four daily-return implementations have genuinely diverged.**
  `analytics/risk.py::_portfolio_time_weighted_return_series` applies the US-34.8
  reconciliation correction (`total_portfolio_value − reconciliation_adjustment`)
  and the `return_is_publishable` skip; `analytics/attribution.py::_portfolio_return_series`
  (whose own docstring says it "mirrors" the risk.py function) **omits the
  reconciliation correction**; `services/distribution_engine.py::_compute_daily_returns`
  and its `drawdown_engine.py` sibling take **no basis parameter** and apply
  **neither** correction, chaining raw `total_market_value`. Consolidating them
  onto one series type (a `ReplaySeries` wrapping `list[DailyPortfolioState]`)
  would change attribution / distribution / drawdown outputs on the imported
  ledger-replay path — it is a methodology change, not a behaviour-neutral
  refactor, and per the guardrail-1 discipline (see the US-40.1 duplication
  finding above) any change to *how* these values are computed needs a
  quant-research pass first. Owner: a future methodology story; **not Epic 43**
  (whose US-43.2 explicitly leaves `_portfolio_return_series` alone). The
  output-neutral residue — `_build_wealth_index` / `_build_drawdown_from_return_index`
  and the `daily_states: list` → `list[DailyPortfolioState]` annotations —
  travels with US-43.2/US-43.3 where those helpers already move.
- **`services/portfolio_proof.py` (3,181 lines) has two responsibilities in one
  file.** Witness-building (FX / opening-state / cash-flow / calendar /
  valuation / terminal-reconciliation — ~1,700 lines) and the admission
  decision (`_evaluate_investor_economics_admission:1889`,
  `_build_portfolio_admission_decision:2471` — ~950 lines). The public interface
  is already small (`build_portfolio_proof_metadata`,
  `build_unavailable_portfolio_proof_metadata`) so friction is **low today** —
  the file is a deep module, not a shallow one. Splitting the admission half
  into its own module is worth doing only **after** US-43.3 names the
  trust-decision vocabulary, so the two can share it. Owner: revisit post-Epic-43;
  low priority.

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
