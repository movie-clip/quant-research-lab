# Epic Roadmap

*Living execution snapshot. Updated: 2026-07-05 (Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience **backlog** (3 stories authored); Epic 27 — Financial Calculation Correctness **active** (US-27.1 + US-27.2 done, 7 stories remaining); Epic 25 — Dashboard Performance & Risk Summary complete; Epic 24 — Codebase Improvement active; Epic 26 — Currency Exposure & Risk backlog (research brief only); Epic 23 — dead-code cleanup & codebase review complete; Epics 13/18/19/20/21/22 complete).*

---

## Backlog Epic: Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience

**PRD:** [`docs/product/prd/epic-28-ibkr-csv-importer.md`](product/prd/epic-28-ibkr-csv-importer.md)

Created 2026-07-05 from the owner's actual workflow: the IB statement file is
replaced with a fresh broker export every few weeks, so exact-number pins
break on every refresh — and the fragile PDF regex parsing (hardened twice in
Epic 24) re-parses a *layout* when IBKR ships the same statement as a
machine-readable CSV. `docs/IB2026.csv` (Activity Statement, 2026-01-01 →
2026-06-30, 22 sections, utf-8-sig) is committed as the real statement to
build against. Three stories: **US-28.1** a fail-safe
`interactive_brokers_csv.py` importer producing the unchanged snapshot
contract (per-currency Open Positions, ISIN from Financial Instrument
Information, reconciles against its own Change-in-NAV totals); **US-28.2**
remove the three `.pdf` gates (statement_importer suffix check, App.tsx
picker filter + accept attr), key the golden pipeline off the CSV, one
deliberate `refresh_statement.py` regeneration (window moves Jan–Apr →
Jan–Jun; needs FMP key + registry entries for new symbols), legacy 2022–2025
PDFs keep working; **US-28.3** classify statement-truth vs structural
assertions, centralize the truths into one module per side, prove via a
swap-simulation meta-test that a statement refresh fails only the documented
pin set, and document the one-command workflow.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-28.1 | IBKR Activity-Statement CSV importer (backend) | Backlog |
| US-28.2 | Wire CSV end-to-end: detection, upload UI, golden pipeline on IB2026.csv | Backlog |
| US-28.3 | Statement-refresh resilience: centralize statement-truth pins + document the workflow | Backlog |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-05 | — | Epic created ("switch the IB parser from PDF to the CSV export; fix whatever a periodic statement refresh breaks"). Verified against the real `docs/IB2026.csv`: IBKR's `Section,Header|Data` framing with per-section column headers covers everything the PDF regexes reconstruct, at full precision, plus data the PDF path lacks (per-currency EUR/GBP/USD Open Positions, `Security ID` ISINs, Conids). Confirmed the three `.pdf` gates (`statement_importer.import_statement`, App.tsx selection filter, `<input accept>`), the golden pipeline's `IB2026.pdf` keying (`export_dashboard_goldens.py`, `_statement_fixtures.py`), and that the upload route is already suffix-agnostic. Noted the statement-window move (PDF Jan–Apr vs CSV Jan–Jun) makes the US-28.2 golden regeneration the epic's main scheduled cost. PRD + 3 stories authored; `docs/IB2026.csv` committed; no code changed. |

---

## Active Epic: Epic 27 — Financial Calculation Correctness

**PRD:** [`docs/product/prd/epic-27-financial-calculation-correctness.md`](product/prd/epic-27-financial-calculation-correctness.md)

Created 2026-07-05 from a full financial-calculations audit of the analytics +
engine layer against `financial-methodology.md` (findings recorded first, no
fixes applied during the audit — the PRD's F1–F13 table is the canonical
record). **13 findings**: 4 confirmed math bugs shown to the researcher today
(Information Ratio under-stated ~√252×; dashboard monthly returns drop every
month-boundary day; dashboard max drawdown measured on raw
cash-flow-contaminated value; covariance cells can pair returns from different
dates), 6 guardrail violations (stress projections zero-fill missing loadings;
factor risk-share denominator diverges from the doc; collinear factors kept
raw instead of nulled; synthetic history flat back-fills before a symbol's
first quote; missing FX rates silently convert 1:1; drift-window returns
aren't cash-flow-neutral), and 3 low-severity consistency gaps. 9 stories
authored (US-27.1–27.9); recommended order 27.1 → 27.2 → 27.3 (small,
wrong-number-today fixes) before the behaviour-aware valuation changes
(27.7/27.8) that will shift goldens.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-27.1 | Fix the Information Ratio annualization | Done |
| US-27.2 | Fix dashboard monthly-return chaining + max-drawdown basis | Done |
| US-27.3 | Fix covariance-matrix date alignment | Backlog |
| US-27.4 | Stress scenarios: null semantics for missing loadings | Backlog |
| US-27.5 | Reconcile the factor risk-share denominator | Backlog |
| US-27.6 | Null collinear factors in per-window orthogonalization | Backlog |
| US-27.7 | Stop flat back-filling synthetic history before first quote | Backlog |
| US-27.8 | Surface FX-fallback trust + fix drift-window return basis | Backlog |
| US-27.9 | Low-severity tail (fabricated 0.0 points, stdev conventions, DR/return basis) | Backlog |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-05 | US-27.2 | **Fixed dashboard monthly-return chaining + max-drawdown basis (audit F3 + F2).** `_compute_contribution_adjusted_monthly_returns` now buckets each cash-flow-neutral daily return into its **end date's** month with the baseline carried across month boundaries — the old per-month grouping reset the baseline each month, dropping every month-boundary return so Π(1+mᵢ) ≠ period TWR (FF2026 proof: old months compounded to −24.8% vs the actual −23.86%; corrected months chain exactly). A month with no computable return now emits no entry (never a fabricated 0.0%). `_compute_max_drawdown` now builds the compounded return index (reusing `_build_wealth_index`/`_build_drawdown_from_return_index` from `risk.py`, anchored at 100 on the range's first state date) instead of walking raw `portfolio_value` — a same-day deposit no longer masks a real drawdown (fixture: −10% was reported as 0.0) and a withdrawal no longer fabricates one (fixture: 0.0 was reported as −50%). Withholding gates untouched. +6 pytest (chaining property, boundary regression, boundary-flow neutrality, deposit-mask, withdrawal-fabricate, first-day-decline parity); FF2026 golden constant + its test-local mirror re-pinned to the corrected convention with a chaining sanity note; `dashboardGoldens.ts` regenerated deliberately (diff reviewed field-by-field — only monthly_returns/returnPct shifted; the ib2026 1M-range May +75.99% verified to chain exactly to that range's own +19.21% summary, a sparse-series/synthetic-anchor artifact documented in the new methodology edge case). Methodology gained §Monthly Returns + §Dashboard range max drawdown; `dashboard-fields.md` monthly-cells row updated. 459 backend + 252 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.1 | **Fixed the Information Ratio annualization (audit finding F1).** `build_relative_risk_summary` in `risk.py` computed `mean_active × √252 / TE_annualized` — algebraically the *daily* IR, under-stating the displayed value by √252 ≈ 15.87×. Now `mean_active × VOLATILITY_ANNUALIZATION_DAYS (252) / tracking_error`, exactly the methodology §Information Ratio form (daily IR × √252). Edge cases (no pairs / TE=0 → null) unchanged and still covered by the four pre-existing null-path assertions. Added `test_build_relative_risk_summary_information_ratio_is_annualized_exact_value` — a hand-derived fixture (expected 18.71) that the pre-fix code fails at 1.18, closing the null/not-null test gap the audit flagged. Verified no golden or fixture embeds an IR value (`dashboardGoldens.ts` untouched); contract docs (`diagnostics-fields.md`/`dashboard-fields.md`/`exposure-fields.md`) defer the formula to the methodology section — no edit needed; methodology doc already correct, unchanged. 453 backend + 252 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | — | Epic created from a "check all financial calculations" audit. Every formula in `app/analytics/*` + the engine services + `dashboard_history_engine.py` + `engine/portfolio_state.py` was read against `financial-methodology.md`. Also recorded what was **checked and found correct** (Modified Dietz, VaR/CVaR + invariant, percentiles/moments/histogram, wealth index/underwater/episodes + decomposition reconciliation, attribution identity + NaN guards, correlation-matrix null semantics, ENB, active share, exposure HHIs, tracking error, β/ρ/R²) so future audits don't re-litigate. Notable pattern: none of the 13 findings were test-caught because the suite asserts null/not-null rather than numeric values at exactly these spots — every Epic 27 story therefore requires exact-value or property pins. PRD + 9 stories authored; no code changed. |

---

## Backlog Epic: Epic 26 — Currency Exposure & Risk

**PRD:** [`docs/product/prd/epic-26-currency-exposure-and-risk.md`](product/prd/epic-26-currency-exposure-and-risk.md)

Research brief only — not yet ticketed. A project-wide review found the
project has no view of portfolio currency exposure despite already importing
`ImportedPosition.currency`/`ImportedStatement.base_currency` on every
statement. `financial-methodology.md` gained a §Currency Exposure section
(snapshot weight-by-currency formula, ready to implement) and a
§Currency Risk Contribution subsection (historical FX-return decomposition,
explicitly documented as **not** ready — the interaction-term and portfolio-
variance-decomposition questions are open, and
`MarketDataService.get_fx_history` — which exists but has zero callers today
— needs empirical verification before any engine work begins). Run
`write-story` against the PRD's US-26.1 when this epic is picked up.

---

## Completed Epic: Epic 25 — Dashboard Performance & Risk Summary

**PRD:** [`docs/product/prd/epic-25-dashboard-performance-risk-summary.md`](product/prd/epic-25-dashboard-performance-risk-summary.md)

### Goal

Restore the Dashboard tab's performance/risk surface that `dashboard-fields.md`
and `current-product-state.md` describe but `DashboardPanel.tsx` no longer
renders (removed piecemeal across several undocumented refactors, per git
history — `bc4ff4d`/`195dc70`/`e0254d6`/`df5d478`). The backend
(`DashboardHistoryResult`, `DiagnosticsResult`) already computes every field
needed: no schema/engine change, frontend-only restoration + a docs
reconciliation pass.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-25.1 | Performance & benchmark comparison card | Done |
| US-25.2 | Monthly returns grid card | Done |
| US-25.3 | Risk metrics card (volatility, drawdown, concentration) | Done |
| US-25.4 | Docs close-out | Done |
| US-25.5 | Information Ratio on the Risk Summary card | Done |

Recommended build order: 25.1 → 25.2 → 25.3 → 25.4 (docs last). US-25.5 was
added afterward from a separate quant-research pass and picked up as an
Epic 25 addendum since it extends the same US-25.3 card.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-04 | US-25.5 | **Information Ratio on the Risk Summary card.** A `quant-research` pass on "what risk-adjusted return metrics are missing" found `RelativeRiskSummary.information_ratio`/`.active_return_pct` were **already fully computed** in `risk.py` and already flowing into `DiagnosticsResult.relative_risk` — contract-documented, but with no `financial-methodology.md` section and no UI consumer anywhere (the same "computed but never surfaced" pattern as the rest of Epic 25). Added a §Information Ratio methodology section (Grinold & Kahn 2000; Goodwin 1998 citations) that explicitly distinguishes the IR's annualized-mean-daily active return from the schema's separate compounded `active_return_pct`. Added two rows to `RiskSummaryCard.tsx` (US-25.3) reading the already-fetched `diagnosticsAnalysis.relative_risk` — no new fetch, prop, or schema change. The two rows are omitted (not `n/a`) when `tracking_error_pct` is null, since they're mathematically dependent on it. Frontend + docs only. +3 `DashboardPanel.test.tsx` tests (32 total); full `run_all_tests.py` green; tsc clean; goldens untouched. |
| 2026-07-04 | US-25.4 | **Epic 25 docs close-out — closes the epic.** Corrected this story's own premise during implementation: `money_weighted_return_pct` is **Modified Dietz**, not IRR/XIRR, implemented in `app/analytics/performance.py` (not `app/analytics/portfolio.py` as originally assumed) — added §Money-Weighted Return to `financial-methodology.md` with the correct formula, edge cases, and Dietz (1966) + GIPS citations. Fleshed out §Risk Contribution and Concentration with the risk-share, top-N risk-share, and HHI formulas (Herfindahl 1950 / Hirschman 1964 citations), explicitly distinguishing the risk-contribution HHI from the separate current-state holdings HHI in `exposure_engine.py`. **Caught a real scale bug while cross-checking the methodology against the implementation:** `risk.py`'s `top_*_risk_share` fields are 0-1 fractions, but `RiskSummaryCard.tsx` (US-25.3) was rendering them with a bare `%` suffix (~100x too small); fixed with a dedicated `formatShareAsPct` formatter and corrected the test fixture. Rewrote `dashboard-fields.md`'s Field Inventory/Provider-Chain/Accuracy-Rules sections wholesale (the prior version described `draftSnapshot`/Allocation-Overview/`capitalChartData` helpers that no longer exist anywhere in the codebase — confirmed by grep) and `current-product-state.md`'s Dashboard bullet list (dropped the unsubstantiated "Sharpe-equivalent" line; no Sharpe ratio exists anywhere in the codebase). Docs-only + one bugfix; full `run_all_tests.py` green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.3 | **Risk metrics card (volatility, drawdown, concentration).** New `RiskSummaryCard.tsx` on the Dashboard tab, sourced from the already-fetched `DiagnosticsResult` (`volatility_summary`, `drawdown_summary`, `risk_concentration_summary`) — deliberately not `DashboardHistoryResult.max_drawdown_pct`, which stays behind the investor-economics withholding policy. Threaded `diagnosticsAnalysis` (already held in `App.tsx` state) into `DashboardPanel` as a new prop. Trust shown as a plain-text label following `run_metadata.section_trust.risk_contribution_path`. **Hardening found by the full suite, not the story's own tests:** `App.test.tsx` exercises a real case where `diagnosticsAnalysis` is present but its `volatility_summary`/`drawdown_summary`/`risk_concentration_summary` sub-objects are absent — the card crashed on first render; fixed to fail closed to the EmptyState instead of trusting `availability` alone, with a dedicated regression test. Frontend-only, no backend/schema change. +6 `DashboardPanel.test.tsx` tests (31 total in the file); 249 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.2 | **Monthly returns grid card.** New `MonthlyReturnsGrid.tsx` on the Dashboard tab: one cell per `range_metrics[selectedRange].monthly_returns[]` entry, signed `+X.XX%`/`−X.XX%` formatting (color + sign, never color-only), whole-card EmptyState when `monthly_returns_reliable = false` or `range_metrics` is absent. Refactored the shared range-selection state up from `PerformanceBenchmarkCard` (US-25.1) into `DashboardPanel`, which now renders one `WindowSelector` driving both cards so they can never show mismatched ranges. Frontend-only, no backend/schema change. +4 `DashboardPanel.test.tsx` tests (20 total in the file); 243 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.1 | **Performance & benchmark comparison card.** New `PerformanceBenchmarkCard.tsx` on the Dashboard tab: indexed portfolio-vs-benchmark line chart (base 100, reuses the `IndexedReturnChart`/`normalizePerformanceSeries` rebasing convention) + a summary strip (Portfolio Value, Time-Weighted Return, Money-Weighted Return, Net Contributions) sourced from the already-computed `range_metrics[selectedRange].summary`; a range selector switches both without any new fetch (data already present in `result`). Trust reflected as a plain-text return-basis label per path (`return_basis_contract`), not the shared `TrustBadge` primitive — that primitive's synthetic/unavailable vocabulary doesn't fit dashboard-history's verified/price-return/unverified-proxy ladder (documented in the story's Notes). Deliberately never reads `max_drawdown_pct` (withheld investor-economics field; that's US-25.3's diagnostics-sourced card). Frontend-only, no backend/schema change. +6 `DashboardPanel.test.tsx` tests; 239 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | — | Epic created from a project-wide review that found `DashboardPanel.tsx` renders only 3 cards (Rolling Factor Analysis, Sector composition, Benchmark Positioning) while two contract docs still describe a performance chart, monthly returns grid, risk metrics, and investor-economics status as shipped. Confirmed via grep + git log that the backend fields are fully live/tested/golden-pinned and the gap is UI-only, accumulated across several past refactors rather than one regression. PRD + 4 stories authored. |

---

## Completed Epic: Epic 23 — Dead-Code Cleanup & Codebase Review

**PRD:** [`docs/product/prd/epic-23-dead-code-cleanup-and-review.md`](product/prd/epic-23-dead-code-cleanup-and-review.md)

### Goal

A safe, comprehensive, per-area sweep that removes confirmed-dead code across the
whole project (one reviewable area per story, full suite green after each, zero
behaviour change), stands up a dead-code detection floor (tooling + tsconfig
flags), and **catalogs** hardcodes / anti-patterns into `docs/tech-debt-register.md`
to seed a follow-up improvement epic (Epic 24). Deletions + tooling + docs only —
no behaviour change, no smell fixes (those are Epic 24).

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-23.1 | Detection tooling + tech-debt register + removal protocol | Done |
| US-23.2 | Backend sweep — analytics, schemas, domain, instruments | Done |
| US-23.3 | Backend sweep — services, routes, clients, core, importers | Done |
| US-23.4 | Frontend sweep — app & features | Done |
| US-23.5 | Contract & schema↔type↔docs drift reconciliation | Done |
| US-23.6 | Tests, fixtures & golden-pipeline hygiene | Done |
| US-23.7 | Scripts, tooling & docs reconciliation | Done |
| US-23.8 | Enforce the dead-code floor in the canonical test gate | Done |
| US-23.9 | Remove the unused disposition plumbing (cross-seam) | Done |

Recommended build order: 23.1 → 23.5 → 23.2 → 23.3 → 23.4 → 23.6 → 23.7 → 23.8.
(23.1 stands up the tooling/register; 23.5 settles cross-seam contracts before
deletions; 23.7 reconciles docs + hands the register to Epic 24; **23.8 last** —
wires `knip`/`ruff`/`vulture` zero-findings enforcement into `run_all_tests.py`
once the baseline is clean, so dead code can't re-accumulate and no future
cleanup epic is needed. ESLint deliberately not adopted — `tsc` + `knip` cover
the dead-code goal; ESLint's in-file `no-unused-vars` is redundant with `tsc`.)

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-19 | US-23.8 | **Epic 23 tail — the dead-code detection floor is now an enforced gate, and Epic 23 is Completed.** `scripts/run_all_tests.py` gained two gate steps: `npx tsc --noEmit` and `python scripts/detect_deadcode.py --strict` (ruff + vulture + knip, zero-findings) — so any newly-introduced dead code or in-file unused local fails the suite. **Baseline cleaned to green:** `knip.json` set `ignoreExportsUsedInFile: true` (so a flagged export is used *nowhere*, not merely over-exported) — collapsing 74 findings to 5 genuinely-dead exports, which were removed (the dead `buildExposureFactorModelResponse` duplicate + its `ImportedExposureFactorModelSource` type, the unused `buildImportedExposureView`/`buildImportedDashboardView`/`buildImportedDiagnosticsView` adapter views, `hashPortfolioSnapshot`); plus 4 vulture-100% test-dead items (an unreachable-after-return method, two unused lambda params, one signature-match `auto_adjust` kwarg → reasoned `vulture_allowlist.py` entry). **Enforcement proven (AC4):** a scratch unused export was shown to fail the gate, then removed. **Documented (AC6)** in `CLAUDE.md` + `testing-architecture.md` (how to read a failure; reasoned-allowlist policy). Full suite + both gate steps green; goldens untouched; `git status` clean. No app behaviour change — tooling only. |
| 2026-06-19 | US-23.7 | Epic 23 reconciliation close-out (the enforcement gate US-23.8 is the tail that flips the epic to Completed). **scripts/** swept — `ruff` + `vulture` clean, no dead code (CLI entry points are live by design). **Docs reconciled** to the leaner tree: removed the stale live-state references to the US-23.9-removed disposition subsystem from `system-architecture.md`, `dashboard-fields.md`, and `financial-methodology.md` (contract `import-admission-fields.md` was already reconciled in US-23.9); contract docs confirmed free of the removed `MarketOverlapConstituent` schema + US-23.4 dead types. **Register consolidated** into a prioritized "Epic 24 backlog" (severity × effort, grouped to proposed stories). **Epic 24 — Codebase Improvement PRD seeded** (`docs/product/prd/epic-24-codebase-improvement.md`, Backlog) with a 7-story list led by the two hardcoded-year latent bugs. **Epic 23 removal totals (US-23.1–23.7):** 7 unimported files deleted + the cross-seam disposition subsystem; ~1,550 lines of dead/duplicate code removed across 36 services/apps files (gross deletions; net is smaller — insertions are mostly the US-23.9 persistence-test rewrite + reasoned `# noqa`); detectors now clean on all backend trees (`ruff`/`vulture`) with knip down to over-exported-but-live only. Full suite green throughout; goldens untouched; no methodology change. |
| 2026-06-19 | US-23.6 | Test-suite hygiene sweep (backend pytest + frontend vitest). **Removed:** backend — 12 `F401` unused imports across 8 test files + 3 `F841` dead locals (`test_analytics.py` `snapshot`/`price_histories`, `test_drawdown_analytics.py` `top_returns`); frontend — `DashboardPerformanceChart.tsx` (no production importer) together with its **vacuous** App.test.tsx suspense scaffolding (the `vi.hoisted` mock + `vi.mock` + reset + suspense test — confirmed it could not exercise a real suspense boundary since App never renders the component), plus 4 dead leaf fixture factories (`createIb2026/Ff2026ImportedDashboardFixture`, `createImportedBaselineFixture`, `createDiagnosticsFixture`). The 4 over-exported-but-live fixtures were kept. **AC1 decision:** the ~10 hand-rolled snapshot builders were NOT wholesale-migrated to `fixtures.py` — many return route-payload dicts vs the shared model builder, so migration is deferred to Epic 24 with a recorded reason. **AC5 catalog:** fixture-duplication + a coverage gap (`test_build_portfolio_risk_summary_and_position_contributions` never calls `build_position_risk_contributions`) recorded. Golden invariants intact; `git status` clean after `run_all_tests.py`; 233 desktop + backend green; tsc clean. |
| 2026-06-19 | US-23.3 | Backend wiring-tier dead-code sweep (`services/` + `api/` + `clients/` + `core/` + `importers/`). **Removal (AC1):** the dead **duplicate** `allow_exact_slice_benchmark_return_output` computation in `dashboard_history_engine.py` — investigated and confirmed dead (its result was discarded; the live benchmark-output gating is the per-range call → `_compute_visible_summary`; withholding logic unchanged). Output-neutral; drops a wasted call per dashboard run. The 3 Freedom24 `F841` locals (`isin`/`realized_pnl`/`account`) were checked against the schema and **kept under reasoned `# noqa: F841`** (parsed-but-dropped: `isin` is a real `ImportedInstrument.isin` coverage gap, `realized_pnl` is unmodeled, `account` is benign) rather than deleted — evidence preserved. `vulture --min-confidence 80` finds no dead routes/methods/classes; every registered route still passes the US-21.3 route-table check. **AC4 catalog (16 wiring smells → Epic 24):** the fragile positional Freedom24 PDF parser (~50 fixed-offset reads), `fmp.py` hardcoded `timeout=30.0` + hardcoded `etf-holder` v3 URL bypassing settings `base_url`, the `"SPY"` default benchmark duplicated across ≥4 engines, the `99.0` coverage threshold, the `ceil(window*1.6)+30` lookback heuristic duplicated across 3 engines, and `_MIN_OBSERVATIONS=20` triplication; `core/` noted as exemplary settings-driven config (no findings). Full suite green; goldens untouched; no methodology change. |
| 2026-06-19 | US-23.2 | Backend dead-code sweep of the pure-logic core (`analytics/` + `schemas/` + `domain/` + `instruments/`) — closed out. Dead-code removal (AC1–AC3) was landed in a prior pass (5 F401 unused imports across `attribution.py`/`risk.py`/`reconciliation.py`; the dead full-period OLS block + discarded `alpha_annualized`/`specific_risk`/`collinearity_warnings` locals + orphaned `_orthogonalize_factor_series`; the dead `top_shared` market-overlap build + `MarketOverlapConstituent` schema; the `target`/`portfolio_names` locals — all output-neutral, methodology cross-checked). This pass **confirmed** the four modules are now `ruff F401/F811/F841`-clean and `vulture --min-confidence 80`-clean, and completed **AC4**: an exhaustive hardcode/anti-pattern catalog (24 findings → Epic 24), headlined by two **hardcoded calendar-year `2025` latent bugs** (`activity.py:24`, `reconciliation.py:24` silently drop non-2025 ledger entries), hardcoded broker-section strings in `domain/ledger.py`, and the inline mapping-score weight/threshold clusters in `risk.py`. No code change this pass; full suite green; goldens untouched; no methodology edit (proof of behaviour-neutrality). |
| 2026-06-19 | US-23.9 | Removed the never-wired `ImportAdmissionReviewDispositionV1` disposition plumbing across the seam (carved from US-23.4, gated by the workspace round-trip tests). **FE** (`portfolioWorkspaceStorage.ts`): dropped the disposition save fn, `assertValidImportAdmissionReviewDispositionForSave`, the 8 sanitize/canonicalize/match helpers, the whole fingerprint subsystem (`canonicalizeForFingerprint`/`buildDeterministicImportAdmissionFingerprint`/`buildImportSnapshotFingerprint`/`buildImportAdmissionSummaryFingerprint`), the now-dead `isPlainRecord`/`isNonEmptyString`, the type aliases, and `admissionReviewDispositions` handling in `buildPersistedImportedSource`+`sanitizeImportedNodeSource`. Removed `ImportAdmissionReviewDispositionV1`+`ImportAdmissionCheckEvidenceSummaryV1` (`types.ts`) and the `admissionReviewDispositions` field+import (`workspaceTypes.ts`). **BE** (`import_bootstrap.py`): dropped `ImportAdmissionReviewDispositionV1`+`ImportAdmissionReviewEvidenceSummaryV1`+the `ImportAdmissionReviewDisposition` enum+`ImportAdmissionReviewEvidenceStatus` alias+the now-unused `field_validator` import. **Persisted-state safety**: a pre-US-23.9 workspace's `admissionReviewDispositions` blob is dropped on read (field absent, no throw, storage not rewritten) — proven by a new round-trip regression. Removed the ~14 disposition/fingerprint test blocks + 3 BE disposition tests; `import-admission-fields.md` reconciled (disposition subsystem → "Removed" note). 234 frontend green (added 1, net −13 blocks); backend `test_import_admission.py` 17 green; ruff/knip clean, no new vulture findings; tsc clean; goldens untouched. |
| 2026-06-17 | US-23.4 | Frontend dead-code sweep — closed out. Removed the confirmed-dead set (6 unimported files: `featureFlags`/`portfolioState`/`CurrentFactorSnapshotCard`/`SectorDonutCard`/`historyTruth`/`investorEconomics`; 5 dead types; `getPortfolioDatabaseName`) — knip 7→1 files, 65→60 types, 22→21 exports. Resolved `features/market-data` + `features/settings` as intentional README-only placeholders (not dead). Recorded the over-exported live types, 7 suspected-unused CSS tokens (kept — design-scale/indirect-ref risk), and "no FE anti-patterns of note" in the register. **Carved out** the two heavy/entangled remainders to their own slices: the disposition plumbing → **US-23.9** (per the 2026-06-17 stability decision — ~250-line persistence+test+schema change gated by the workspace round-trip tests), and `DashboardPerformanceChart` (test-coupled) → **US-23.6**. Suite green; tsc clean; goldens untouched. |
| 2026-06-12 | US-23.5 | Contract & schema↔type↔docs drift reconciliation (sequenced before the deletion sweeps). Triaged the US-23.1 detector baseline into the register: of knip's 81 flagged exports/types, **only 10 are truly dead** (5 FE-orphan types `ActivityPoint`/`CanonicalLedgerRecord`/`ReconciliationCheck`/`DiagnosticsPayload`/`ExposureEnginePayload` + 5 unused fixture/db helpers) and 7 whole unimported files; the other **71 are live in-file mirrors merely over-exported** (not deletable — `export` keyword unnecessary; re-run knip iteratively as the 10 are removed). Three-way audit (Pydantic schemas ↔ `types.ts` ↔ `docs/contracts/*`) found **no type-level drift** — every doc-referenced identifier resolves to a live schema/TS type or a UI-component/prose word; no stale rows, no dangling types, so contract docs are accurate as-is and **no reconciliation edits were needed**. Confirmed none of the deletion candidates cross a documented seam (safe for US-23.4). Flagged the canonical cross-seam dead case — the `ImportAdmissionReviewDispositionV1` disposition plumbing — with coordinated owners (FE US-23.4 + BE US-23.2). Register/docs only; suite green, tsc clean, goldens untouched. |
| 2026-06-12 | US-23.1 | Dead-code detection floor + tech-debt register. Python: `ruff` (`ruff.toml`, unused rules F401/F811/F841) + `vulture` (`vulture_allowlist.py` for dynamic-use FPs — Pydantic `__context` etc.), declared in new `requirements-dev.txt`. TypeScript: `knip` devDependency + minimal `knip.json` (auto-detects Vite/Vitest entries). New `scripts/detect_deadcode.py` runs all three (informational; `--strict` = the US-23.8 gate mode). New `docs/tech-debt-register.md` (category schema + per-entry fields + the "confirmed dead" removal protocol + the captured baseline as the per-area worklist). Documented in CLAUDE.md + testing-architecture.md (incl. why ESLint is not adopted — redundant with tsc). **Baseline captured**: ruff 29 (17×F401, 12×F841), vulture (FactorRiskContribution + test items), knip **7 unused files / 22 unused exports / 65 unused types** — triaged to US-23.2/23.3/23.4/23.6. `tsconfig noUnusedLocals/noUnusedParameters` **staged** (enabling surfaces ~20 in-file violations inside not-yet-deleted dead files; turned on in US-23.8). Tooling/config/docs only — no app code; 242 frontend + backend green; tsc clean; goldens untouched. |
| 2026-06-12 | — | Epic created from a "clean dead code + review the whole project" request, after the US-22.2 review surfaced never-consumed disposition plumbing and a survey found **no dead-code tooling** (no ruff/vulture/knip/ts-prune/eslint) and no `noUnusedLocals`. Per-area story breakdown (tooling+register, backend×2, frontend, contracts, tests, scripts-docs) so nothing is missed; dual deliverable per story — remove dead code AND catalog hardcodes/anti-patterns into a tech-debt register feeding a follow-up Epic 24. Tail story US-23.8 added per request: enforce the detectors (`knip`+`ruff`+`vulture`, zero-findings) in `run_all_tests.py` once the baseline is clean, so dead code can't re-accumulate and no future cleanup epic is needed (researched: ESLint not adopted — redundant with `tsc` for the dead-code goal). PRD + 8 stories authored. |

---

## Active Epic: Epic 24 — Codebase Improvement

**PRD:** [`docs/product/prd/epic-24-codebase-improvement.md`](product/prd/epic-24-codebase-improvement.md)

Seeded by Epic 23 (US-23.7) from the consolidated "Epic 24 backlog" in
`docs/tech-debt-register.md`. Fixes the catalogued hardcodes / magic numbers /
fragile coupling / latent bugs as deliberate, reviewed, **behaviour-aware**
changes (the complement to Epic 23's deletions). Every change keeps the
deterministic suite green and updates methodology / contract docs when a
surfaced value becomes a named, documented constant.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-24.1 | Fix hardcoded-year ledger filters (latent bugs) | Done |
| US-24.2 | Extract the risk-model scoring rubric & thresholds | Done |
| US-24.3 | De-duplicate shared analytics constants | Done |
| US-24.4 | Harden importer parsing (Freedom24) + extract hardcodes | Done |
| US-24.5 | Decouple broker format from the domain | Backlog |
| US-24.6 | Market-data client config hygiene | Backlog |
| US-24.7 | Reconcile minor hardcodes + de-export + test smells | Backlog |
| US-24.8 | Harden the IBKR importer parsing (fail-safe) | Done |

Recommended order: US-24.1 first (highest-impact latent bugs, low effort), then
US-24.2/24.3 (the analytics-constant work), then US-24.4/24.5/24.6, with US-24.7
the low-severity tail. Stories are authored via `write-story` as each is picked up.
US-24.8 (the deferred US-24.4 importer-hardening follow-up) was picked up out of
order alongside a broader codebase review.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-04 | US-24.8 | **Hardened the IBKR importer parsing (fail-safe).** Investigation corrected this story's original two-importer premise: `interactive_brokers.py` and `espp.py` are already regex-`match()`-guarded (unlike Freedom24's raw offset walk), so the real gap was narrower — a captured numeric/date group can match the shape but fail the subsequent `float()`/`datetime.strptime()` conversion, with no guard between that and `import_statement`. Fixed in `interactive_brokers.py`: `_parse_statement_totals`'s per-field loop (+ TWR/EURUSD parses), `_parse_period_end_date` (catches `ValueError`, returns `None` so the existing `2025-12-31` fallback applies), and the record-append blocks in `_parse_trades`/`_parse_simple_cash_section`/`_parse_deposits_and_withdrawals` now degrade one field/record instead of raising. **`espp.py` investigated and left unchanged** — every numeric regex group there uses the strict `[\d,]+\.\d+` shape, which cannot capture a value `float()` will reject, so there was no reachable failure to guard (confirmed by trying to construct one and failing). Behaviour-neutral for valid statements (IB2026 golden import unchanged). +3 `test_importer.py` tests. Methodology "Importer resilience rule" extended to both importers + the ESPP investigation note; tech-debt register row marked Resolved (IBKR) / Investigated-not-needed (ESPP). Full suite + dead-code gate green; tsc clean; goldens untouched. |
| 2026-06-24 | US-24.4 | **Hardened the Freedom24 importer + extracted its format hardcodes.** Investigation first **corrected the register's premise**: the "Freedom24 ISIN data gap" was a misread — `_parse_instruments` already flows ISIN to `ImportedInstrument.isin` (now pinned by an FF2026 assertion); the `_parse_positions` `isin` copy was dead offset-walk code. Made all 5 positional parsers **fail-safe** — a malformed/non-numeric record is skipped and parsing continues (a layout drift → partial snapshot surfaced by reconciliation, never a crash or fabricated/zero row). Extracted the inline format hardcodes (currency whitelist / `.US` suffix / default currency / the magic page indices) to named constants; removed the 3 dead parsed-but-dropped locals (`isin`/`realized_pnl`/`account`, now documented offset comments). **Behaviour-neutral for valid statements** — the FF2026.pdf golden-master test is byte-identical (+ a new ISIN + constants pin + a malformed-input degradation test). `realized_pnl` stays unmodeled (schema change deferred). Methodology gained an "Importer resilience rule"; register rows corrected/Resolved. Full suite + dead-code gate green; goldens untouched. |
| 2026-06-24 | US-24.3 | **De-duplicated the three copy-pasted analytics defaults** into a single `app/core/constants.py` (the lowest layer, so `schemas` can import it without a cycle): `lookback_calendar_days(window)` (= `ceil(window*1.6)+30`), `MIN_DAILY_OBSERVATIONS` (= `20`), `DEFAULT_BENCHMARK_SYMBOL` (= `"SPY"`). Replaced the duplicate `_lookback_calendar_days` in **6** engines (attribution / correlation / distribution / drawdown / stress / provenance + intra-correlation — two more consumers than the original catalog noted), the flat `_MIN_OBSERVATIONS=20` across the distribution/correlation/drawdown/intra engines + the `analytics/distribution.py`/`analytics/correlation.py` modules, and ~10 `"SPY"` defaults (3 schema field defaults + the engine `or "SPY"` fallbacks). **Behaviour-neutral** — values unchanged, `dashboardGoldens.ts` untouched, full suite + dead-code gate green; the distinct `WINDOW_MIN_OBSERVATIONS` (OLS buffer) and `attribution.min_observations=window` were deliberately **not** merged. Added 3 shared-module tests; methodology doc + register updated. |
| 2026-06-19 | US-24.2 | **Extracted the risk-model scoring rubric & thresholds into named, documented constants** (behaviour-neutral). Lifted the factor→UCITS mapping-quality composite/sub-weights, hard-cap ceilings + reasons, `_mapping_match_label` thresholds, the `_mapping_quality_score`/`_cost_fit_score` quality maps, the volatility-regime percentile cutoffs, and the factor-model `FACTOR_MODEL_MIN_SHARED_OBSERVATIONS` floor into a documented `# ── Factor-mapping scoring rubric ──` constants block in `risk.py`; plus `BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT` in `exposure_engine.py`. Each constant carries a one-line rationale ("heuristic, no academic basis" where applicable — **no fabricated citations**). **Pin-tests-first discipline:** added 6 exact-value golden-master tests (`test_analytics.py`) capturing the *current* score_pcts/labels/hard-caps/regime-cutoffs/stress-projections/min-history before the extraction, so a transposed weight fails loudly. Behaviour-neutral — `dashboardGoldens.ts` untouched; 141 analytics+exposure tests green; full suite + dead-code gate green; tsc clean. The leaf per-token `_*_score` rubric literals stay inline (deferred, low value). Methodology doc + register updated. |
| 2026-06-19 | US-24.1 | **Fixed the two hardcoded calendar-year `2025` latent bugs** (the register's only High-severity entries). Removed `if entry.date.year != 2025` from `analytics/activity.py` `build_activity_series` (which silently dropped every non-2025 ledger entry → empty activity for 2026+ statements) and `and candidate.date.year == 2025` from `analytics/reconciliation.py` `_negative_withholding_total` (which reconciled non-2025 withholding against `0`). Removal — not "derive the year" — because the snapshot ledger is already period-scoped and the sibling reconciliation actuals (dividends/fees/interest/deposits) never year-filtered; the `%Y-%m` bucketing handles any span. **Behaviour-neutral for 2025** (all-2025 fixtures → identical output; `dashboardGoldens.ts` untouched). Added 4 `test_analytics.py` regressions (2026 non-empty activity, 2025-unchanged pin, 2026 withholding reconciles, multi-year span). Methodology doc gained a "Statement reconciliation & activity scoping" rule; register rows marked Resolved. Full suite + dead-code gate green; tsc clean. |

---

## Completed Epic: Epic 22 — Import Admission Review UI

**PRD:** [`docs/product/prd/epic-22-import-admission-review-ui.md`](product/prd/epic-22-import-admission-review-ui.md)

### Goal

Give the Import Admission Review (overall decision + trust level + per-check
results) a visible home in the UI. The summary is already computed, delivered,
and persisted as workspace `admissionSummary` — but never rendered (only the
identity-mismatch slice leaks through the Data Sources panel). Render it from
existing state; no backend change.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-22.1 | Import Admission Review card | Done |
| US-22.2 | Admission review disposition workflow | Won't do (2026-06-12) |

US-22.2 reviewed and **closed as not needed** (2026-06-12): the disposition
schema models an enterprise review/sign-off (reviewer label, required rationale,
accepted-exception / needs-correction / deferred states) on a single-user,
local-first personal tool. Persistence + sanitization + evidence-matching for
dispositions already exist in the workspace storage layer but have **no producer
and no consumer** — nothing records a disposition and nothing displays/acts on
one. US-22.1 already delivers the actual value (visibility into why an import is
degraded/withheld); a formal sign-off workflow is speculative (no demonstrated
need) and changes no number or analytic. Epic 22 is therefore complete with
US-22.1 alone. (If acknowledgement value ever becomes real, a lightweight
"dismiss this warning" — no reviewer/rationale ceremony — is the right shape,
not the full schema. The unused disposition plumbing is a candidate for a
separate dead-code cleanup.)

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-12 | US-22.1 | Import Admission Review card — the admission summary now has a visible home. New `ImportAdmissionReviewCard.tsx` (Exposure tab, beside Data Sources): renders the persisted workspace `admissionSummary` (`ImportAdmissionSummaryV1`) — decision (admitted/degraded/withheld) + trust-level badges, then one row per check (residual-cash, NAV, position-MV, symbol identity, description-consistency, ISIN-consistency) with status (✓ Pass / ⚠ Warn / ✗ Fail / — Unavailable — symbol prefix so status isn't colour-only), message, and observed/comparison/signed-delta+currency evidence + affected fields. Presentational only (persisted-import truth class) — no fetch/recompute, survives reload; null summary → explicit unavailable state, never a fabricated all-clear. Threaded the active import source's `admissionSummary` from App.tsx through a new optional `ExposurePanel` prop. Added `--color-status-warn` design token (amber caution, distinct from error/disabled) and registered the card in the design-system audit set. Frontend-only; no backend/schema/goldens change. +7 vitest tests; 242 frontend + backend green; tsc + audit clean. |

---

## Completed Epic: Epic 21 — Testing Strategy & Architecture Hardening

**PRD:** [`docs/product/prd/epic-21-testing-strategy-hardening.md`](product/prd/epic-21-testing-strategy-hardening.md)

### Goal

Make "green" mean green: zero live-network tests (kill the standing "4 known
failures"), a generic JSON-strict response-integrity property test (generalizing
the 2026-06-10 NaN-500 fix), one shared fixtures module instead of ~7 duplicated
mock helpers, deterministic goldens, additive-tolerant assertions, and a faster
parallel suite.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-21.1 | Deterministic suite — no live network in tests | Done |
| US-21.2 | Shared test-fixtures module | Done |
| US-21.3 | Engine response-integrity property test | Done |
| US-21.4 | Golden pipeline determinism | Done |
| US-21.5 | Assertion conventions + suite speed | Done |

Recommended build order: 21.1 → 21.2 → 21.3 → 21.4 → 21.5.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-21.5 | Assertion conventions + suite speed — **closes Epic 21**. (1) `write-tests/SKILL.md` gained an "Assertion conventions" section: assert membership/superset (`expected.items() <= actual.items()`) for intentionally-extensible structures (reserve `==` for closed contracts); pin an implicit default in exactly one dedicated test and capture-and-delta elsewhere. Both rules cite their real Epic-21 breakages (`vendor`/`last_fetch_meta`; admission check; 60d→20d window). (2) Converted the brittle spots: five `last_fetch_meta` exact-dict assertions (`test_market_data.py`) + the import-admission check dict (`test_import_admission.py`) → `.items() <=` superset; drawdown/VaR click-refetch tests capture the default dynamically and assert the delta (VaR gained a dedicated default test); rolling-correlation "insufficient history" selects 20d explicitly. (3) `pytest-xdist` added to `requirements.txt`; `run_all_tests.py` backend step now `-n auto`. **Backend wall-time 135.0s → 39.9s (~70% reduction, 16 cores)** — well past the ≥40% target; network guard + frozen-goldens determinism intact under parallel. (Drift-noise console-cleanup slice landed earlier as `1c7154f`.) 414 backend + 232 frontend green. |
| 2026-06-11 | US-21.4 | Golden pipeline determinism — the dashboard goldens no longer depend on the live FMP cache. Discovered the root churn: `render_dashboard_goldens_text` drove `run_imported_dashboard_history`, which built a live `MarketDataService` and pulled benchmark + per-symbol histories whose *adjusted closes re-adjust over time* (dividends/splits) — so the goldens differed per machine and per fetch, and bare `pytest` needed a warm cache or `SKIP_GOLDEN_FRESHNESS_CHECK=1`. Fix: (1) added a keyword-only `market_data` injection seam to `run_imported_dashboard_history` (production callers unchanged → live service). (2) New `app/scripts/frozen_market_data.py`: `FrozenMarketData` replays a committed JSON fixture and **raises `FrozenMarketDataMiss`** on an absent (symbol, window) — a stale fixture fails loudly instead of degrading to a wrong "unavailable" golden; `RecordingMarketData` wraps a real service to (re)capture. (3) New committed fixture `app/scripts/golden_market_data.json` (24 series + SPY verified-benchmark meta), captured once via the new `export_dashboard_goldens --capture` mode. (4) `render_dashboard_goldens_text` now defaults to the frozen provider → deterministic, network-free; the conftest freshness fixture inherits this (no env var, no warm cache needed). Goldens regenerated once from the frozen capture (one-time content shift from adjusted-price drift; frontend vitest goldens stay green because expected values + fixture regenerate together). +4 `test_golden_pipeline_determinism.py` tests. **414 backend + 232 frontend green offline with zero env vars**; `git status` clean after `run_all_tests.py`. |
| 2026-06-10 | US-21.3 | Engine response-integrity property test. New `test_engine_response_integrity.py`: (1) parametrized strict-JSON check over **8 engine routes** (stress, drawdown, distribution, drift, attribution, correlation/multi, correlation/intra, provenance) — each driven by a standard fixtures portfolio with its own per-engine `MarketDataService` mock; a 200 is the property (starlette's encoder raises on NaN/inf, which WAS both 2026-06-10 bugs). (2) **Self-policing coverage check**: introspects the FastAPI route table — any new `POST /engines/*` route must be parametrized or explicitly waived with a reason (waivers: exposure / diagnostics / dashboard-history, golden-pinned heavier contracts; stale waivers also fail). risk.py audit found the same NaN leak as attribution (`round(coefficients[...])` passes NaN into rolling loadings/R²/residual-vol) → fail-closed isfinite→None guard in `_build_rolling_factor_loadings` + NaN-injection regression in `test_analytics.py`; methodology §Statistical Factor Model gained the degenerate-window→null-never-NaN edge-case rule. +10 tests. 410 backend pass, fully green. |
| 2026-06-10 | US-21.2 | Shared test-fixtures module. New `app/tests/fixtures.py` (+ `app/tests/__init__.py` making the dir a package): `imported_snapshot()` / `position()` (the 422-proof `ImportedPortfolioSnapshot` shape, round-trip-validated against the real schema), `price_rows()` / `price_rows_from_returns()`, and `install_market_data_mock(mocker, target_module, …)` (engine-module-targeted MarketDataService mock with real `last_fetch_meta`). Migrated the three dict-based duplicate sets (`test_correlation_engine`, `test_intra_correlation_engine`, `test_provenance_engine`) to thin wrappers over the shared module; behaviour + counts unchanged. +3 `test_fixtures.py` tests; write-tests skill gained the mandatory-fixtures section. |
| 2026-06-10 | US-21.1 | Deterministic suite landed — **first fully-green backend run (397 passed, 0 failed) since Epic 17**. (1) New conftest autouse fixture `_mock_risk_engines_market_data` mocks `MarketDataService` in the stress / drawdown / distribution engines with the existing deterministic synthetic rows — the 4 "real portfolio" tests now pass offline with original assertions intact. (2) New `pytest.ini`: `pytest-socket` guard (`--disable-socket --allow-hosts=127.0.0.1,::1 --allow-unix-socket`) blocks any real network connection — a test that forgets to mock fails loudly with `SocketConnectBlockedError`; loopback (in-process TestClient / Windows asyncio socketpairs) and file I/O unaffected. `live_data` marker registered and **deselected** by default (`-m "not live_data"`). `pytest-socket` added to requirements. +3 guard tests (`test_network_guard.py`: external blocked, marker deselection pinned, loopback+file-I/O pass). write-tests skill gained a "No live network in tests" policy section. Test-layer only — no production code change. |
| 2026-06-10 | — | Epic created from a testing-architecture review prompted by the attribution NaN-500 (a bug class no test guarded) and by recurring friction in Epics 16–20: 4 live-FMP tests failing offline for weeks, goldens churn requiring `git checkout` before commits, exact-set assertions breaking twice on additive changes, fixture duplication across ~7 files, 10 frontend tests pinned to an implicit default. PRD authored with five-story plan; US-21.1 (deterministic suite + network guard) authored and ticketed. |

---

## Completed Epic: Epic 20 — Market-Data Cache Efficiency & Control

**PRD:** [`docs/product/prd/epic-20-market-data-cache-efficiency.md`](product/prd/epic-20-market-data-cache-efficiency.md)

### Goal

Cut FMP overuse and latency by making the **local** cache smarter (range
normalization, in-memory layer, parallel fetch) and giving the user cache
visibility + a clear button. No Redis (local-first desktop; wouldn't fix the
core redundant-range issue).

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-20.1 | Cache stats + clear (route + UI) | Done |
| US-20.2 | History range normalization (FMP-call reduction) | Done |
| US-20.3 | In-memory layer + parallel fetch (latency) | Done |

Recommended build order: 20.1 → 20.2 → 20.3.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-20.3 | In-memory layer + parallel fetch — the latency win; **closes Epic 20**. (A) `JsonFileCache` gained a process-level in-memory memo (`_MEMORY_CACHE`, lock-guarded, keyed by `(absolute_path, mtime_ns)` → parsed envelope): repeated reads of the same cache file across an analysis's ~7 engines skip the disk read + `json.loads` after the first; self-invalidating on any write (mtime bump), shared across the separate per-engine `JsonFileCache` instances, and cleared per-test by an autouse `_clear_cache_memory` fixture for determinism. (B) `MarketDataService.get_historical_prices_for_symbols` now fetches symbols concurrently via a bounded `ThreadPoolExecutor` (`max_workers=min(8, n)`); the lazy `_yfinance()` build is lock-guarded; per-symbol `last_fetch_meta` writes are race-free; result dict is reassembled in deterministic canonical-symbol order. Pure performance — bytes/TTL/trust/`last_fetch_meta` unchanged; goldens untouched (`FrozenMarketData` bypasses the seam). Measured: repeated read of a ~500KB payload **737ms → 11ms (~65× on the read path)**; 12-symbol fetch at 50ms I/O each **600ms → 102ms (~6×)**. +9 tests (6 `test_cache.py`, 3 `test_market_data.py`); hardened the pre-existing `max_age=0` stale test to a deterministic past-`fetched_at` (the memo made the 0-second boundary timing-flaky). 430 backend + 232 frontend green under `-n auto`; tsc clean; `git status` clean. |
| 2026-06-11 | US-20.2 | History range normalization — the FMP-call reduction. `MarketDataService` now widens every history request to a deterministic calendar-year-quantized superset range (`_canonical_history_range`), fetches that one range (so all requests in the same year-span share a single FMP cache key / call), then slices rows back to the caller's exact window (`_slice_price_rows`). Applied to `get_historical_prices` (FMP candidates + yfinance fallback + proxy + FX + `…_for_symbols`) and the verified-benchmark direct path (`get_direct_verified_benchmark_history`). Output is byte-identical to a direct `(from,to)` fetch — slicing is exact. No schema/methodology/trust change; `last_fetch_meta` unchanged. +8 `test_market_data.py` tests (quantization, slicing, shared-cache-key on overlapping windows, direct-window equivalence, empty-window fail-closed, yfinance-fallback slicing, benchmark canonical sharing + meta parity); 2 benchmark tests + 1 intra-correlation NaN-seam test updated (the latter anchored its synthetic bars to `date.today()` so they land in the engine's requested window — slicing now correctly enforces the window). Goldens untouched (`FrozenMarketData` bypasses the seam). 422 backend + 232 frontend green; tsc clean; `git status` clean after `run_all_tests.py`. |
| 2026-06-10 | hotfix | **Critical: attribution 500 (NaN not JSON-compliant).** A degenerate rolling window made the OLS solve return a non-finite beta → NaN contributions that silently passed the reconciliation check (NaN comparisons are always False) and broke JSON serialization (`ValueError: Out of range float values are not JSON compliant: nan`) → `POST /engines/attribution/run` 500. Surfaced after the attribution time-span widening (more windows → more degenerate ones). Fix in `analytics/attribution.py`: skip any date whose computed `r_p`, residual, betas, f* or contributions are non-finite (fail-closed — omit, never emit NaN). +1 regression test (injects a NaN beta; asserts `json.dumps(..., allow_nan=False)` succeeds). |
| 2026-06-05 | — | Epic created from a cache review. Found the dominant FMP-overuse cause is date-range fragmentation (each engine fetches overlapping ranges → distinct cache keys), plus no in-memory layer, sequential fetches, and no cache route/UI. Decision: enhance the local file cache (range-normalization + memo + parallel + control surface); **no Redis** (local-first; doesn't fix the range issue). Three-story plan; US-20.1 (stats + clear) authored first to also provide the observability used to validate 20.2/20.3. |

---

## Completed Epic: Epic 19 — Instrument Identity Integrity

**PRD:** [`docs/product/prd/epic-19-instrument-identity-integrity.md`](product/prd/epic-19-instrument-identity-integrity.md)

### Goal

Detect and surface ticker→fund mislabels (like the `DFND` case) by cross-checking
the registry's fund name against the broker statement's own description, instead
of silently trusting the registry.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-19.1 | Instrument description-consistency check | Done |
| US-19.2 | ISIN-keyed registry identity | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-19.2 | ISIN-keyed registry identity — **closes Epic 19**. The registry's instrument definitions gained an optional `isin`, seeded with **authoritative values extracted from the committed real statements** for the 16 registry-known UCITS/identity-sensitive lines (e.g. `DFND → IE000U9ODG19` iShares Global Aerospace & Defence — distinct from the portfolio's own `DFNS → IE000YYE6WK5` VanEck Defense, the exact near-miss pair). `detect_instrument_identity_mismatches` now checks ISIN evidence first (definitive ISO 6166 equality, normalized) alongside the US-19.1 description heuristic; `InstrumentIdentityMismatch` gained `kind` (`description`/`isin`) + `statement_isin`/`expected_isin` (TS + contract doc mirrored). Evidence-gated: holdings lacking an ISIN on either side are skipped — absent evidence is never a pass or a failure. Surfaced through both channels: new `instrument_isin_registry_consistency` admission check (`warn`/`degraded`, flag-only) and the Data Sources panel (renders both ISINs). New `test_registry_isin_integrity.py` guard pins registry-seed ⇄ statement agreement (a typo'd seed fails the suite) and proves zero false positives on re-importing the real statements. +9 backend, +3 frontend tests; the analyze-snapshot route's exact check-set assertion converted to superset per the US-21.5 convention. 439 backend + 235 frontend green; tsc clean. |
| 2026-06-05 | US-19.1 | Instrument description-consistency check. New pure detector `app/services/instrument_identity.py` (`detect_instrument_identity_mismatches`) flags registry-known holdings whose broker description is **identity-disjoint** from the registry fund name (conservative token comparison; catches different-issuer mislabels, ignores formatting/share-class noise). Surfaced two ways: a new `instrument_description_registry_consistency` Import Admission check (`warn`/`degraded`), and — because the admission summary isn't rendered today — a visible "⚠ Possible identity mismatch" line on the Exposure **Data Sources panel** (`ProvenanceResult.identity_warnings`, computed in `provenance_engine`). Schema + TS `InstrumentIdentityMismatch`. Flag only — never auto-corrects. +6 detector + 3 admission + 2 engine + 2 panel tests; 2 pre-existing exact-check-set assertions (clean-pass, analyze-snapshot route) updated for the additive check. 227 frontend + backend green (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean; audit 5/5. |
| 2026-06-05 | — | Epic created after the `DFND` mislabel (registry said "VanEck Defense"; user's holding is iShares Global Aerospace & Defence). PRD authored; description-consistency flag chosen over ISIN (providers don't return ISINs for these EU funds). Grounding found the Import Admission Review summary is computed/persisted but not rendered, so US-19.1 surfaces the flag on the visible Data Sources panel (US-18.2) in addition to the persisted admission check. |

---

## Completed Epic: Epic 18 — Secondary Market-Data Provider

**PRD:** [`docs/product/prd/epic-18-secondary-market-data-provider.md`](product/prd/epic-18-secondary-market-data-provider.md)

### Goal

Add **yfinance as a fallback market-data provider** behind `MarketDataService`
(FMP first, Yahoo when FMP returns 402/empty) so European UCITS ETFs stop being
excluded from history-based analytics — with an explicit, **visible data-provenance**
dimension (`fmp` vs `yfinance`) per the traceability guardrail. Verified POC:
7 of 10 currently-excluded UCITS tickers resolve immediately via Yahoo with
adjusted-close data.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-18.1 | yfinance fallback provider + data provenance | Done |
| US-18.2 | Portfolio-level data-sources indicator (one Exposure panel) | Done |
| US-18.3 | Defense-ETF Yahoo symbol mapping (DFND/DEFS/IDFN) | Done |
| US-18.4 | Sanitize non-finite price rows (bugfix) | Done |

Recommended build order: 18.1 → 18.2 → 18.3. **Epic 18 complete** (+ US-18.4 bugfix follow-up).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-10 | US-18.4 | **Critical bugfix: correlation 500s from NaN price bars.** Cache scan found 38 `history_yf` entries with `price: NaN` (2026-06-09 bars for the Yahoo-sourced UCITS) — pandas encodes missing bars as `float('nan')`, which passed `YFinanceClient`'s `is None` check; downstream, `pearson()`'s variance guard passes NaN, so `/engines/correlation/{intra,multi}` 500'd on JSON encode. Two-layer fix: (1) `yfinance_client._fetch` skips non-finite bars at the source; (2) new `MarketDataService._sanitize_price_rows` drops absent/non-finite-price rows on **every** history return path (FMP loop, yfinance fallback, direct-benchmark) — sanitization runs *before* the truthiness check so an all-bad result falls through to the next candidate/provider, and the 38 already-cached poisoned entries are neutralized without a cache clear. +5 tests incl. a route-level regression through the REAL MarketDataService asserting 200. 390 backend pass (only the 4 known offline failures, US-21.1's target). Backend-only. |
| 2026-06-05 | UX fix | **Factor Return Attribution time-span bug + 20d default.** The attribution engine fetched only `_lookback_calendar_days(window)` of history, so the 20d chart spanned just ~2 months (the rolling window was wrongly controlling the *displayed* range). Fixed `attribution_engine.py` to fetch a fixed display span (`ATTRIBUTION_DISPLAY_TRADING_DAYS=252`) **plus** the window, so every window shows the same ~1-year cumulative series; the window now only sets each rolling estimate's length. +1 engine test (mock respects the date range; pins the 20d series spans the full range). Separately, made **20d the default** window on all 20/60/252 charts (FactorAttributionCard, RollingCorrelationChart, FactorDriftSummaryCard, IntraCorrelationHeatmap); updated the affected component tests. 225 frontend + 369 backend pass (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean. |
| 2026-06-05 | US-18.3 (fix 2) | Added missing exchange-suffix candidates for two more UCITS holdings the user still saw excluded: `ICOM` → `("ICOM.L","ICOM")` (iShares Diversified Commodity Swap UCITS ETF, LSE/USD) and `VDST` → `("VDST.L","VDST")` (Vanguard U.S. Treasury 0-1 Year Bond UCITS ETF, LSE/USD) — both verified by yfinance `longName`+currency. Their rules previously had only the bare ticker (404 on both providers). Existing ICOM proxy-fallback test updated for the new candidate order; +1 resolution test. Backend resolution tests green. |
| 2026-06-05 | US-18.3 (fix) | **Correction:** the registry mislabeled `DFND` as "VanEck Defense UCITS ETF"; the user confirmed their `DFND` is the **iShares Global Aerospace & Defence UCITS ETF (LSE, GBP)** = `DFND.L`. US-18.3's original mapping was inverted accordingly: `DFND` → `("DFND.L","DFND")` (the iShares A&D fund); the VanEck lines (`DFNS.L`/`DFEN.DE`/`DFNG.L`) are now the *excluded* wrong-fund symbols. Registry display name fixed to "iShares Global Aerospace & Defence UCITS ETF"; guard test inverted; fmp-data skill table corrected. Lesson: verify ticker→fund identity against the broker statement (ISIN/name), not just the registry label. Backend green (resolution tests pass). |
| 2026-06-05 | US-18.2 | Portfolio-level data-sources indicator. New `app/schemas/provenance.py` + `app/services/provenance_engine.py` + `POST /engines/provenance/run`: probes a short window per holding and reads `MarketDataService.last_fetch_meta` vendor to group holdings into FMP (primary) / Yahoo (secondary) / unpriced — provider identity is window-independent so the probe is cheap (cached). New self-fetching `DataSourcesPanel` on the Exposure tab renders the grouping once at the portfolio level (design decision: single indicator over per-card markers; the intra card keeps its inline marker). TS types + `runProvenanceEngine` adapter; panel added to the design-system audit set. New `docs/contracts/provenance-fields.md`; system-architecture + current-product-state updated. Provenance is a **source label, not a trust claim**. +5 backend (4 engine + 1 route) + 5 frontend (4 panel + 1 adapter); 225 frontend + 367 backend pass (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean; audit 5/5; goldens untouched. **Epic 18 complete.** |
| 2026-06-05 | US-18.3 | Defense-ETF Yahoo symbol mapping. Investigation (yfinance `longName`) showed only `DFND` was a real gap and carried a correctness trap: `DFND.L` is **iShares Global Aerospace & Defence UCITS ETF**, a *different* fund — while the `DFND` rule had only the bare (404ing) `DFND` candidate. Fixed the `DFND` `SymbolResolutionRule` to the real VanEck Defense lines `("DFNS.L","DFEN.DE","DFNG.L","DFND")` (USD first; never `DFND.L`), proxies `ITA/PPA` preserved. `DEFS` (`DEFS.L`) and `IDFN` (`IDFN.L`) were already correct via US-18.1 — the earlier "3 deferred" was a probe artifact (2024 date range predating the 2024/25 fund launches). +3 backend resolution tests incl. a wrong-fund guard pinning that no `DFND` candidate list ever contains `DFND.L`. fmp-data skill UCITS table updated. No methodology/contract/frontend change. Backend green (only the 4 pre-existing FMP-offline failures remain). |
| 2026-06-05 | US-18.1 | yfinance fallback provider + data provenance. New `app/clients/yfinance_client.py` (`YFinanceClient.get_historical_price_light` → FMP-shaped rows with `adjClose`; lazy yfinance import; JsonFileCache namespace `history_yf` incl. negative caching; all errors → `[]`). `MarketDataService.get_historical_prices` gains a yfinance fallback after the FMP candidate loop (same suffixed candidates, never proxies), recording `last_fetch_meta[...]['vendor']` ∈ {`fmp`,`yfinance`}; FMP-first path byte-for-byte unchanged. `IntraCorrelationResult` + TS gained `yahoo_sourced_symbols`; the engine populates it from `last_fetch_meta`; `IntraCorrelationHeatmap` renders a visible "◆ N holdings via Yahoo Finance (secondary source): …" marker. `yfinance` added to `requirements.txt`. New autouse conftest fixture disables the fallback by default so no test hits the network; 5 pre-existing `test_market_data.py` proxy assertions updated for the additive `vendor` key. Docs: system-architecture gained a "Market-data providers and data provenance" subsection; `intra-correlation-fields.md` + current-product-state updated. +11 backend (5 yfinance client + 4 MDS fallback + 2 engine provenance) + 2 frontend; 220 frontend + 359 backend pass (only the 4 pre-existing FMP-dependent stress/drawdown/distribution tests fail offline — unrelated); `npx tsc --noEmit` clean; audit 5/5; goldens untouched. Recovers 7/10 of the user's excluded UCITS ETFs; the 3 defense ETFs (DFND/DEFS/IDFN) are US-18.3. |
| 2026-06-05 | — | Epic created after a user hit "10 holdings excluded: insufficient history" (all European UCITS ETFs FMP's plan 402s). yfinance POC confirmed Yahoo serves the suffixed symbols (VUAA.L, SXRV.DE, …) with adjusted close. PRD authored; three-story plan (fallback provider + provenance → broaden badges → defense-ETF symbol mapping). US-18.1 authored and ticketed. |

---

## Completed Epic: Epic 17 — Intra-Portfolio Correlation

**PRD:** [`docs/product/prd/epic-17-intra-portfolio-correlation.md`](product/prd/epic-17-intra-portfolio-correlation.md)

### Goal

Answer "what is actually diversifying me?" on the Exposure tab with a holdings ×
holdings Pearson correlation heatmap (selectable 20d/60d/252d window) plus
diversification summary stats — reusing the existing synthetic-history machinery
and `pearson()` helper. No new data provider.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-17.1 | Pairwise correlation matrix engine + heatmap | Done |
| US-17.2 | Diversification summary metrics (DR + ENB; introduces numpy) | Done |
| ~~US-17.3~~ | ~~Docs, contracts, roadmap close-out~~ | **Cancelled** (docs reconciled per-story via update-docs) |

Recommended build order: 17.1 → 17.2.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-05 | US-17.2 | Diversification summary metrics added to the Intra-Portfolio Correlation card. `analytics/correlation.py` gained `population_stdev()`, `diversification_ratio()` (Choueifaty & Coignard 2008, pure-Python), and `effective_number_of_bets()` (Meucci 2009, numpy `eigvalsh` imported lazily; null when matrix incomplete / <2 holdings / non-PSD). `intra_correlation_engine.py` computes current-weight-renormalised weights, per-holding σᵢ, and σ_p from the **constant-weight** synthetic portfolio return series `Σwᵢrᵢ` (coherent DR denominator, guarantees DR≥1; deviates from the story's `_build_synthetic_snapshot_history_states` hint for self-consistency with the displayed top-N universe) → populates `diversification_ratio` + `effective_number_of_bets` on `IntraCorrelationResult`. Schema + TS mirror extended; `IntraCorrelationHeatmap` summary strip gained "Diversification Ratio" (2-dp) and "Effective number of bets" (1-dp), each "Unavailable" when null. numpy added to `requirements.txt`. Contract + methodology reconciled (ENB no longer "later story"; σ_p constant-weight definition). +8 backend (6 analytics + 2 engine; route field-presence folded into the existing shape test) + 3 frontend; 218 frontend + 348 backend pass (the 4 pre-existing FMP-dependent stress/drawdown/distribution failures persist — unrelated); `npx tsc --noEmit` clean; audit 5/5; goldens reverted. **Epic 17 complete.** |
| 2026-06-05 | US-17.1 | Pairwise correlation matrix engine + heatmap landed on the Exposure tab. Extended `analytics/correlation.py` with `pairwise_correlation_matrix()` (reuses `pearson()`; symmetric, diagonal 1.0, null below 20-overlap / zero-variance) + `average_pairwise_correlation()`. New `services/intra_correlation_engine.py` (reuses `_returns_from_price_series` + `_lookback_calendar_days`; per-symbol returns over the SPY grid; cash/non-priceable/no-history holdings excluded → `excluded_symbols`; weight-ranked, top-15 cap; most/least pair). New `POST /engines/correlation/intra` on the existing correlation router; new `schemas/intra_correlation.py`. Frontend: TS types + `runIntraCorrelationEngine` adapter; new `IntraCorrelationHeatmap` card (color-blind-safe heatmap — numeric ρ + ▲▲/▲/•/▼/▼▼ glyph over `--color-corr-*`; muted diagonal; "n/a" null cells; summary strip; excluded caption; Synthetic badge; EmptyState), added to the design-system audit set and wired into `ExposurePanel`. Contract `docs/contracts/intra-correlation-fields.md`. +14 backend (6 analytics + 6 engine + 2 route) + 10 frontend (9 card + 1 adapter); 215 frontend green; `npx tsc --noEmit` clean; audit 5/5; goldens reverted. (Pre-existing FMP-dependent stress/drawdown/distribution "real portfolio" tests fail in the offline sandbox — confirmed identical on base, unrelated to this story.) DR + ENB remain US-17.2. |
| 2026-06-05 | — | Epic created from a `quant-research` brief (intra-portfolio correlation). Methodology extended with §Intra-Portfolio Correlation (pairwise Pearson matrix reusing `pearson()`; average pairwise correlation; Diversification Ratio — Choueifaty & Coignard 2008; Effective Number of Bets — Meucci 2009; Markowitz 1952 grounding; numpy approved for the ENB eigendecomposition). PRD authored; three-story plan. US-17.1 authored and ticketed (schema → analytics → service+route → types/adapter → heatmap card → docs). |

---

## Completed Epic: Epic 16 — Factor Drift Visualization

**PRD:** [`docs/product/prd/epic-16-factor-drift-visualization.md`](product/prd/epic-16-factor-drift-visualization.md)

### Goal

Answer "how have my factor exposures *moved*?" on the Exposure tab with a
compact, ranked **Factor Drift Summary** card — per-factor delta (latest
loading − reference loading) over a selectable rolling window, reusing the
rolling loadings the engine already computes. Net-new value, no new backend.
This ships the delta-indicator card parked during Epic 15.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-16.1 | Factor Drift Summary card | Done |

Single-story epic (quick-win follow-up).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-04 | US-16.1 | Factor Drift Summary card landed on the Exposure tab. New `FactorDriftSummaryCard.tsx` (frontend-only — derives the factor model from the Exposure `result` via `buildExposureFactorModel`, no backend): for the selected window it computes per-factor `drift = β_k(latest) − β_k(reference)` over the trimmed `rolling_loadings_<window>` series, ranks factors by `|drift|` desc (ties by label), and renders divergent magnitude bars (positive right of a zero baseline, negative left) with a signed value + ▲/▼ marker so direction survives color-blindness. Factors null at the reference/latest endpoints are excluded (never 0-imputed); fails closed to an EmptyState when the window has insufficient history. Uses Epic 12 primitives (`CardShell`/`TrustBadge`/`WindowSelector`/`EmptyState`) + factor-palette + value tokens (no hex/px); added to the `designSystem.audit.test.ts` scanned set (5/5 audit green). Wired into `ExposurePanel` after the factor attribution card. Methodology §Statistical Factor Model gained a `### Factor Loading Drift` subsection (Ferson & Schadt 1996; Jagannathan & Wang 1996); new `docs/contracts/factor-drift-fields.md`. **Incidental fix**: annotated `decomposedPayload()` return type in `DrawdownAnalyticsCard.test.tsx` to repair a pre-existing (Epic 15) `tsc` narrowing error unrelated to this story. +8 vitest (ranking, delta = latest−reference, null-endpoint exclusion, window re-rank, two EmptyState paths, badge tooltip, color-blind signal). 205 frontend (+8) green; backend unchanged (330); `npx tsc --noEmit` clean; no dashboardGoldens regen. **Epic 16 fully closed.** |
| 2026-06-04 | — | Epic created from the Epic 15 parked backlog candidate ("complementary Factor Drift Summary delta-indicator card"). PRD authored; single frontend-only story (`FactorDriftSummaryCard` on the Exposure tab; ranked per-factor `latest − reference` drift bars; 20d/60d/252d window; Synthetic trust badge; methodology §Factor Loading Drift + `factor-drift-fields.md` contract at close-out). |

---

## Completed Epic: Epic 15 — Position-Level Analytics

**PRD:** [`docs/product/prd/epic-15-position-level-analytics.md`](product/prd/epic-15-position-level-analytics.md)

### Goal

Answer "which positions drove that?" for every Risk-tab metric by
decomposing drawdown episodes into per-position contributions
(arithmetic Brinson under synthetic-history convention) AND
visualize the existing rolling factor loadings on the Exposure tab
so researchers can see how their factor mix has drifted over time.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-15.1 | Drawdown decomposition engine + schema | Done |
| US-15.2 | Drawdown card "Contributors" drawer | Done |
| ~~US-15.3~~ | ~~Factor loading drift chart~~ | **Cancelled** (existing card covers it) |
| US-15.4 | Epic 15 docs close-out | Done |

Recommended build order: 15.1 → 15.2 → 15.3 → 15.4.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-01 | — | Epic created. `quant-research` brief covering arithmetic Brinson-style position decomposition (Brinson Hood Beebower 1986; Goldberg & Mahmoud 2017 §3); methodology extended with `### Drawdown episode decomposition` subsection under §Wealth Index and Drawdown; PRD authored; four-story plan (decomposition engine → drawer UI → factor drift chart → docs close-out). |
| 2026-06-04 | US-15.4 | Epic 15 docs close-out. Extended `docs/contracts/risk-fields.md` with the decomposition fields: 4 new rows on `DrawdownEpisode` (`top_contributors`, `other_contribution_pct`, `decomposition_residual_pct`, `decomposition_trust`); new `EpisodeContributor` field table; "Decomposition trust state semantics" + "Decomposition edge cases" subsections; new "Example response (with decomposition)" snippet showing both synthetic and partial trust variants with realistic 2022 + 2023 drawdown episode JSON. Methodology subsection `### Drawdown episode decomposition` verified against shipped `decompose_drawdown_episode(daily_states, episode, top_n=5)` in `app/analytics/drawdown.py` — function signature, `Implementation:` path, and reconciliation invariant text all match. `current-product-state.md` Risk-tab Drawdown bullet extended with the Contributors drawer description. **Epic 15 fully closed**: 3 Done (US-15.1, US-15.2, US-15.4) + 1 Cancelled (US-15.3 — existing `RollingFactorLoadingsCard` on Dashboard tab already covered the factor-drift use case). 330 backend + 197 frontend stay green (no code changes); `npx tsc --noEmit` clean; no dashboardGoldens regen. |
| 2026-06-04 | US-15.2 | Drawdown card "Contributors" drawer landed. `DrawdownAnalyticsCard`'s episodes table gained a leftmost expand-toggle column; clicking a row reveals a sibling drawer `<tr>` (colSpan=7) with the per-episode contributors sub-table (Symbol / Weight @ Peak / Return / Contribution). Single-open semantics: clicking another row swaps focus. New `ContributorsDrawer` sub-component formats per-cell sign-coloured tabular-nums via design tokens (no hex, no px). "Other" aggregate row renders when `\|other_contribution_pct\| >= 0.01`; "Residual (unexplained)" row renders when `\|residual_pct\| > 0.05` (floating-point noise threshold); both hidden below thresholds. Partial-trust caption ("Partial: N.N% unexplained (some positions missing price history).") appears above the sub-table when `decomposition_trust='partial'`. Toggle disabled (with descriptive aria-label + tooltip) when `decomposition_trust='unavailable'` or `top_contributors=null`. Responsive: `.drawdown-contributor-secondary` CSS class hides Weight + Return columns below 520px viewport (new `@media` rule in `styles.css`). +6 vitest pinning toggle render, expand/collapse, swap-focus, partial caption, disabled state, Other/Residual visibility thresholds. 330 backend + 197 frontend (+6) green; `npx tsc --noEmit` clean; design-system audit 5/5 green; no dashboardGoldens regen. |
| 2026-06-01 | US-15.1 | Drawdown decomposition engine landed. New `decompose_drawdown_episode(daily_states, episode, top_n=5)` in `app/analytics/drawdown.py` implements arithmetic Brinson-style attribution under the synthetic-history convention: `contribution_pct = (V_i(t_peak) / V_p(t_peak)) × (p_i(t_trough) / p_i(t_peak) − 1) × 100`. Iterates `state.positions` only — cash naturally contributes 0 per methodology Contract rule. New `EpisodeContributor` schema + 4 nullable-default fields on `DrawdownEpisode` (`top_contributors`, `other_contribution_pct`, `decomposition_residual_pct`, `decomposition_trust ∈ {'synthetic','partial','unavailable'}`). Wire-up in `drawdown_engine.run_drawdown_engine` decomposes each top-N episode via `model_copy(update=...)`. Reconciliation invariant `|magnitude − (sum_top + other + residual)| < 1e-9` enforced as defensive ValueError post-condition. TS mirror types added (`EpisodeContributor`, `DrawdownDecompositionTrust`, extended `DrawdownEpisode`); all nullable so existing fixtures stay valid. +9 backend tests (7 analytics + 2 engine); 330 backend (+9) + 191 frontend green; `npx tsc --noEmit` clean; no dashboardGoldens regen. |

---

## Completed Epic: Epic 14 — Post-Epic-13 Bug Sweep

**PRD:** [`docs/product/prd/epic-14-post-epic-13-bug-sweep.md`](product/prd/epic-14-post-epic-13-bug-sweep.md)

### Goal

Sweep three independent bugs that surfaced from running the
shipped Epic 13 product: overlay symbol-collision in
"Add Statement", DrawdownAnalyticsCard missing smart-default
window fallback, and Freedom24 unknown-symbol "Other" sector
mis-classification.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-14.1 | Fix overlay symbol collision (sum, don't replace) | Done |
| US-14.2 | DrawdownAnalyticsCard smart-default window fallback | Done |
| US-14.3 | Freedom24 FMP company-profile enrichment for unknown symbols | Done |

Recommended build order: 14.1 → 14.2 → 14.3.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-01 | — | Epic created from post-Epic-13 user-feedback bug sweep. PRD authored; three-story plan (overlay collision → drawdown smart-default → Freedom24 FMP enrichment). |
| 2026-06-01 | US-14.3 | New `app/services/instrument_enrichment.py` with `enrich_imported_instruments(snapshot, market_data)`. Fast-path skips symbols in static `INSTRUMENT_DEFINITIONS` (no FMP call). Slow-path: for unknown symbols with bare-ticker descriptions, calls `MarketDataService.get_company_profile` and populates `description` (= FMP `companyName`) + `instrument_type` (= `"ETF"` when `isEtf=True`, else `"STOCK"`). Asymmetric `instrument_type` rule: FMP can upgrade STOCK→ETF but a non-empty parser declaration always wins. Fail-graceful on FMP `None` or any exception. Wired into Freedom24 parser's `import_statement` with an outer try/except so any FMP failure leaves the import flow intact. Existing description-based `classify_imported_instrument` fallback in `InstrumentRegistry` consumes the enriched description and produces correct sectors (e.g. "Vanguard Total Stock Market ETF" → Broad Market) — verified by a round-trip test. +11 backend pytest (7 enrichment unit + 3 Freedom24 integration + 1 registry round-trip). 321 backend (+11) + 191 frontend tests green; `npx tsc --noEmit` clean; dashboardGoldens.ts unchanged (bundled fixtures use known-registry tickers). **Epic 14 fully closed.** |
| 2026-06-01 | US-14.2 | `DrawdownAnalyticsCard` now auto-falls-back through the window cascade (1260 → 756 → 252 → Max) when the engine returns `trust='unavailable'`, so portfolios with shorter FMP history render on first load instead of forcing the user to manually click each window. New `hasUserOverriddenWindow` state preserves user intent — once they click a WindowSelector button, that window is fetched single-shot regardless of result (no cascade). Snapshot change resets the override flag. Cascade respects existing `let cancelled = false` cleanup so mid-cascade snapshot changes abort cleanly. Network errors stop the cascade (failure isn't window-specific). The displayed window in WindowSelector is derived from `response.window_trading_days` when cascade lands on a different window — avoids re-triggering the effect on `setSelectedWindow`. +4 new vitest pinning: auto-fallback 1260→756 on unavailable; full 4-window exhaustion → EmptyState; user click disables further cascade; happy path doesn't over-fetch. Existing 9 DrawdownAnalyticsCard tests stay green; existing unavailable test updated from `mockResolvedValue` to `mockImplementation` (cascade triggers multiple fetches; Web Response bodies are single-use). 310 backend + 191 frontend (+4) green; `npx tsc --noEmit` clean. |
| 2026-06-01 | US-14.1 | `overlayImportedSnapshot` (in `apps/desktop/src/features/portfolio/portfolioSnapshot.ts`) now SUMS `marketValue` + `quantity` when a symbol appears in both base and imported statements (was REPLACE — silently lost the base statement's dollars on any ticker overlap). Parallel fix for cash balances: sum amounts when the same currency appears in both. Quantity null-handling preserves fail-closed semantics: both-null stays null (no fabricated 0); one-null treats null as 0 in the sum. Two existing US-10.2 overlay tests that accidentally pinned the REPLACE behaviour (`does not duplicate symbols when the same symbol appears in two overlays` and the 3-broker USD cash assertion) updated to assert the SUM, with inline US-14.1 comments. +6 new vitest pinning marketValue sum, quantity sum, both null-cases, sector preservation, and cash-balance sum. 310 backend + 187 frontend (+6) green; `npx tsc --noEmit` clean. No retroactive remediation for users who already overlaid overlapping statements — fix applies to future imports only; they'd need to re-import. |

---

## Completed Epic: Epic 13 — Risk Analytics Tab

**PRD:** [`docs/product/prd/epic-13-risk-analytics-tab.md`](product/prd/epic-13-risk-analytics-tab.md)

### Goal

Add a third tab, **Risk**, alongside Dashboard + Exposure, surfacing three
synthetic-history risk views: stress scenarios (factor-shock projection),
drawdown analytics (underwater curve + top-N episodes with recovery times),
and VaR / distribution analysis (histogram + percentile / tail-risk / shape
table). Two of the three engines already exist in `analytics/risk.py` but
are not surfaced; VaR is new methodology.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-13.1 | Risk tab + Stress Scenarios card | Done |
| US-13.2 | Drawdown Analytics card | Done |
| US-13.3 | VaR & Distribution card | Done |
| US-13.4 | UI density polish + trust-state + a11y verification | Done |
| US-13.5 | Docs close-out | Done |

Stories must be built in order (13.1 → 13.2 → 13.3 → 13.4 → 13.5).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-31 | — | Epic created. `quant-research` brief covering Stress + Drawdown + VaR; methodology extended with §Value-at-Risk and Distribution + drawdown episode identification under §Wealth Index and Drawdown; PRD authored; five-story plan (Stress + tab plumbing → Drawdown → VaR → polish → close-out). |
| 2026-06-01 | US-13.1 | Third nav tab **Risk** wired into `App.tsx` (tab union + `appTabs` array + lazy-loaded panel). New `RiskPanel` mirrors `ExposurePanel` shell with `.risk-shell-stack` flex-column wrapper. New `StressScenariosCard` (3 scenario rows, sorted by abs magnitude desc, horizontal magnitude bar, color-coded pct, `Synthetic` TrustBadge, EmptyState on `trust='unavailable'`). Backend: `app/schemas/stress.py` (`StressEngineRequest` + `StressEngineResponse` wrapper), `app/services/stress_engine.py` (reuses `build_statistical_factor_model` + `build_stress_scenarios`; surfaces `trust='unavailable'` when factor model empty), `app/api/routes/stress.py` (`POST /engines/stress/run`). 268 backend (+5) + 155 frontend (+13) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.2 | Second Risk-tab card: **DrawdownAnalyticsCard** with underwater curve (Recharts AreaChart fill = `--color-value-negative`) and top-5 episodes table (Peak / Trough / Recovery / Magnitude / Duration / Underwater; "Still underwater" italic for `recovery_date=null`). 4-option `WindowSelector` (252d / 756d / 1260d / Max). Self-fetching card with internal `[snapshot, window]` re-fetch. Backend: new `app/analytics/drawdown.py` (pure functions implementing the methodology §Drawdown episode identification greedy forward-walk algorithm), `app/schemas/drawdown.py`, `app/services/drawdown_engine.py` (reuses `_build_synthetic_snapshot_history_states` + `_build_wealth_index`; fails closed when < 20 obs), `app/api/routes/drawdown.py` (`POST /engines/drawdown/run`). `RiskPanel` extended to render both cards in the stack. RiskPanel tests refactored to URL-routed `vi.fn().mockImplementation` so concurrent card mounts work cleanly. 280 backend (+12) + 167 frontend (+12) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.5 | Epic 13 docs close-out. New contract doc `docs/contracts/risk-fields.md` (450 lines) covering all three Risk-tab response shapes (Stress / Drawdown / VaR & Distribution): trust-class preamble, per-field tables (Backend type / TS mirror / UI surface / Nullability / Methodology ref), edge cases, example happy + unavailable JSON per engine. `financial-methodology.md` `Implementation:` subsections for §Stress Scenarios, §Drawdown episode identification, §Value-at-Risk and Distribution updated to cite shipped paths (`analytics/{stress→risk,drawdown,distribution}.py`, `services/{stress,drawdown,distribution}_engine.py`, `api/routes/{stress,drawdown,distribution}.py`) — removed "added in Epic 13" placeholder language. `current-product-state.md` updated: tab count "two → three"; new Risk section with three card bullets; route list expanded with `/engines/{stress,drawdown,distribution}` (now 12 route modules total); analytics module list updated. `CLAUDE.md` updated: "Product: three tabs" + tab table gains Risk row; doc-map adds `risk-fields.md` row; repo-layout `api/routes/`, `analytics/`, `services/` paths list expanded; Active PRD pointer flipped to Epic 13. **Epic 13 fully closed.** 294 backend + 181 frontend stay green; `npx tsc --noEmit` clean. |
| 2026-06-01 | US-13.4 | Density + a11y polish pass on the Risk tab. `RiskPanel` header rewritten from the bulky `<h2 className="panel-label">Risk Analytics</h2>` pattern to ExposurePanel's two-tier hierarchy (`<p className="panel-label">Risk</p>` + plain `<h2>Stress, drawdown, and tail-risk views</h2>`) so the page header no longer competes with the first card's title. `VarDistributionCard` `SectionHeader` slimmed: dropped `textTransform: uppercase` + `letterSpacing: 0.05em` + tightened top margin to `var(--space-sm)` so the three sections read as quiet group labels instead of loud chapter breaks. Trust-tooltip wording aligned across the two history-based cards (Drawdown + VaR/Distribution) — both now open with `"Synthetic: computed from current holdings × historical prices."` followed by a card-specific qualifier; Stress keeps its distinct factor-shock phrasing. Cross-card a11y audit confirmed all three cards inherit CardShell `role="region"` + `aria-labelledby`, both charts have descriptive `ChartShell` ariaLabels, both WindowSelectors pass `ariaLabelFn`, no color-only signal encoding. 2 new density-pin vitest (`risk_panel_header_uses_two_tier_hierarchy_not_bulky_h2`, `section_headers_render_compactly_without_uppercase_or_wide_letter_spacing`). 294 backend + 181 frontend (+2) green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.3 | Third Risk-tab card: **VarDistributionCard** with daily return histogram (Recharts BarChart; loss-tail bars `--color-value-negative`, rest muted; VaR-95 + Mean reference lines) and percentile / tail-risk / distribution-shape table (5/10/50/90/95 percentiles; VaR 95 / CVaR 95 / VaR 99; Mean / Std / Skew / Kurtosis-excess). 3-option `WindowSelector` (60d / 252d / 504d, default 252; no Max — VaR is window-pinned for interpretability). Backend: new `app/analytics/distribution.py` (pure-Python NIST-linear quantile, historical VaR, CVaR/Expected Shortfall, Fisher-Pearson skewness + excess kurtosis, 30-bin auto-fit histogram — no numpy / scipy), `app/schemas/distribution.py`, `app/services/distribution_engine.py` (enforces CVaR≥VaR coherence invariant; raises on violation per Acerbi & Tasche 2002 methodology contract), `app/api/routes/distribution.py` (`POST /engines/distribution/run`). VaR may be negative (no loss days in window) — surfaced as-is per methodology Contract rule; UI styles muted instead of red. `RiskPanel` extended to render all three cards in the stack. URL-routed `makeRoutedFetch` test helper extended for distribution. 294 backend (+14) + 179 frontend (+12) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |

---

## Completed Epic: Epic 12 — UI Polish & Design System

**PRD:** [`docs/product/prd/epic-12-ui-polish-design-system.md`](product/prd/epic-12-ui-polish-design-system.md)

### Goal

Turn the four new Exposure cards (drift, indexed return, rolling correlation,
factor attribution, multi-benchmark correlation) into a production-ready
surface backed by a small design system: tokens, shared primitive components,
accessibility baseline, and a `ui-polish` skill that lets the next analytics
card slot in consistently.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-12.1 | Design tokens + apply to the four Exposure cards | Done |
| US-12.2 | Primitive components + refactor cards | Done |
| US-12.3 | Accessibility + Recharts defaults (ChartShell) | Done |
| US-12.4 | `ui-polish` skill + Epic 12 close-out | Done |

Stories must be built in order (12.1 → 12.2 → 12.3 → 12.4).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-28 | — | Epic created from UX pass over Epic 9/11 cards; PRD authored; four-story plan (tokens → primitives → a11y → skill) |
| 2026-05-28 | US-12.1 | Design tokens (`:root` block: 60+ tokens covering text/surface/border/correlation-sign/factor palette/spacing/typography/radius/border-widths); canonical `.attribution-trust-badge` CSS rule; refactored 5 card files to consume tokens; fixed RollingCorrelationChart dual-axis text overlap (YAxis width 44→64, margin right 56→72); audit regression test (`designSystem.audit.test.ts`, 3 tests) enforces no-hex / no-px in inline styles. 263 backend + 109 frontend green; `npx tsc --noEmit` clean. |
| 2026-05-28 | US-12.2 | Primitive components extracted: `<CardShell>`, `<TrustBadge>`, `<WindowSelector>` (generic), `<EmptyState>`, `<LoadingState>`, `<ErrorState>` at `apps/desktop/src/app/primitives/`; refactored 5 cards to import + use primitives (deleted ~70 lines of duplicated JSX across them); audit test grew 3→4 tests (added "Synthetic" single-source-of-truth check + import-based badge check). New token: `--color-error` / `--color-error-border`. 263 backend + 132 frontend green (+23 frontend); `npx tsc --noEmit` clean. |
| 2026-05-29 | US-12.3 | Chart defaults primitive (`chartDefaults.ts` + `ChartShell.tsx`) + accessibility pass. 3 chart files refactored to use `<ChartShell>` + spread `defaultChartGrid`/`defaultAxisTickStyle`/etc. `CardShell` adds `role="region"` + `aria-labelledby` (via `useId`). `BenchmarkCorrelationTable` ρ column gains sign-symbol prefix (▲▲/▲/•/▼/▼▼) — color no longer sole encoder. `WindowSelector` buttons get `.window-selector-btn:focus-visible` outline. Audit grew 4→5 tests. 263 backend + 142 frontend green (+10 frontend); `npx tsc --noEmit` clean. |
| 2026-05-29 | US-12.4 | `ui-polish` skill authored at `.claude/skills/ui-polish/SKILL.md` (token + primitive + chart-defaults + a11y reference; canonical card pattern code block). New contract doc `docs/contracts/ui-design-system.md` (full token + primitive + audit inventory). `build-story` skill updated to auto-delegate UI slice to ui-polish. `CLAUDE.md` doc map + skills section updated (ui-polish now 8th project skill). Epic 12 closed; no code changes. 263 backend + 142 frontend green; `npx tsc --noEmit` clean. |

---

## Completed Epic: Epic 11 — Factor Return Attribution

**PRD:** [`docs/product/prd/epic-11-factor-return-attribution.md`](product/prd/epic-11-factor-return-attribution.md)

### Goal

Give the researcher a clear answer to "where did my returns come from?" by decomposing portfolio daily returns into per-factor contributions (β × orthogonalized factor return) and a residual, displayed as a cumulative line chart and period attribution table in the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-11.1 | Attribution engine + endpoint | Done |
| US-11.2 | Attribution card (chart + table) | Done |
| US-11.3 | Docs, contracts, roadmap close-out | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-27 | US-11.1 | `analytics/attribution.py` + Pydantic schema + `POST /engines/attribution/run` route + attribution_engine service — 15 backend tests green (239 total) |
| 2026-05-27 | US-11.2 | `FactorAttributionCard` in Exposure tab: cumulative line chart, 20d/60d/252d window selector, period attribution table, Synthetic badge with tooltip, unavailable/loading/error states — 14 frontend tests green (92 total); `npx tsc --noEmit` clean |
| 2026-05-27 | US-11.3 | `docs/contracts/attribution-fields.md` created; `financial-methodology.md` §Factor Return Attribution verified complete; roadmap and story files updated |

---

## Completed Epic: Epic 10 — Multi-broker Import Correctness

**PRD:** [`docs/product/prd/epic-10-multi-broker-import-correctness.md`](product/prd/epic-10-multi-broker-import-correctness.md)

### Goal

Add regression coverage for the three-broker import scenario (IB + Freedom24 + ESPP): backend pytest for `combine_imported_snapshots` + `import_statements` + analytics bootstrap; frontend vitest for the sequential `overlayImportedSnapshot` add-statement flow.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-10.1 | 3-way combine and API-level import tests | Done |
| US-10.2 | Sequential add-statement overlay tests | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-27 | US-10.1 | 3 new backend pytest: 3-way combine, import_statements API, analytics bootstrap — 18 tests green |
| 2026-05-27 | US-10.2 | 3 new frontend vitest: sequential overlay, symbol dedup, sourceFileNames dedup — 3 tests green |

---

## Completed Epic: Epic 9 — Portfolio Correlation & Co-movement Analysis

**PRD:** [`docs/product/prd/epic-9-correlation-analysis.md`](product/prd/epic-9-correlation-analysis.md)

### Goal

Give the portfolio researcher a quantitative view of how their portfolio
co-moves with major market indexes — a day-by-day indexed return chart, a
rolling correlation & beta chart (20d/60d/252d Pearson ρ and β), and a
multi-benchmark snapshot table (ρ, β, R² vs SPY/QQQ/GLD/IEF/VT) — all in
the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-9.1 | Indexed return time-series chart | Done |
| US-9.2 | Rolling correlation and beta chart | Done |
| US-9.3 | Multi-benchmark correlation matrix | Done |
| US-9.4 | Fix rolling factor loadings methodology | Done |
| US-9.5 | Docs, contracts, roadmap close-out | Done |
| US-9.6 | Multi-benchmark correlation follow-ups | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-26 | US-9.4 | Fixed rolling factor model: per-window Gram-Schmidt orthogonalization replaces global GS; Market loading blowup (−4.60) eliminated; 221 backend + 98 frontend tests green |
| 2026-05-28 | — | Epic activated from Parked; US-9.2 revised to frontend-only (rolling_risk fields already computed); US-9.5 added for docs close-out |
| 2026-05-28 | US-9.1 | `DriftBenchmarkPanel` + `IndexedReturnChart` added to Exposure tab; drift engine wired in App.tsx; 5 new frontend tests; 97 frontend + 239 backend tests green |
| 2026-05-28 | US-9.2 | `RollingCorrelationChart` added to Exposure tab (bottom); dual-axis ρ + β chart with 20d/60d/252d window selector; 5 new frontend tests; 102 frontend + 239 backend tests green |
| 2026-05-28 | US-9.3 | `analytics/correlation.py` (pearson/beta/r_squared) + `schemas/correlation.py` + `services/correlation_engine.py` + `POST /engines/correlation/multi` route + `BenchmarkCorrelationTable` in Exposure tab — 22 backend tests green (261 total); 5 frontend tests green (107 total); `npx tsc --noEmit` clean |
| 2026-05-28 | US-9.5 | `docs/contracts/correlation-fields.md` created; `financial-methodology.md` window values corrected (20/60/252); roadmap and story files updated; Epic 9 fully closed |
| 2026-05-28 | US-9.6 | Follow-ups from verify-story on US-9.3: pinned sort + trust-indicator contracts (2 new backend pytest + 2 new frontend vitest); added §Multi-Benchmark Correlation umbrella section to methodology doc; updated `correlation-fields.md` to document opacity-not-column trust rendering — 263 backend + 109 frontend green; npx tsc clean |

---

## Completed Epic: Epic 8 — Reset to Portfolio Analysis Core

**PRD:** [`docs/product/prd/epic-8-reset-to-analysis-core.md`](product/prd/epic-8-reset-to-analysis-core.md)

### Goal
Strip the product to Dashboard + Exposure, clean up the codebase and docs, then add one additive feature: portfolio drift vs index benchmarks in the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-8.1 | Remove workflow tabs from navigation | Done |
| US-8.2 | Strip Workspace and Monitoring frontend | Done |
| US-8.3 | Strip ranking and optimizer frontend | Done |
| US-8.4 | Strip App.tsx workflow state and storage | Done |
| US-8.5 | Remove ranking, construction, and optimizer backend | Done |
| US-8.6 | Remove backtest and monitoring backend | Done |
| US-8.7 | Prune portfolio feature directory | Done |
| US-8.8 | Reset docs and contracts | Done |
| US-8.9 | Add portfolio drift vs index benchmarks | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-25 | US-8.1 | Removed 6 nav tabs; app shows only Dashboard and Exposure |
| 2026-05-25 | US-8.2 | Deleted features/backtest/ (21 files, ~9k lines) |
| 2026-05-25 | US-8.3 | Deleted features/strategy-lab/, generic-ranking/, optimizer/ (38 files, ~25k lines) |
| 2026-05-25 | US-8.4 | Stripped App.tsx from ~3100 to 901 lines; portfolioWorkspaceStorage.ts from ~3300 to 707 lines |
| 2026-05-25 | US-8.5+8.6 | Deleted 4 backend route modules, ~26 service files, 6 schemas, 16+ test files, 7 artifact directories |
| 2026-05-25 | US-8.7 | Deleted 10 dead portfolio components; App.tsx tab type narrowed to dashboard/exposure |
| 2026-05-25 | US-8.8 | Deleted 5 contract docs, 2 old PRDs; rewrote CLAUDE.md, current-product-state.md, epic-roadmap.md |
| 2026-05-25 | US-8.9 | Added drift vs benchmark panel to Exposure tab; new /engines/drift/run endpoint |

---

## Archived Epics

| Epic | Title | Status |
|---|---|---|
| Epic 1 | Imported-portfolio truth & reconciliation | Foundation — superseded by Epic 8 pivot |
| Epic 2 | Ranking & selection methodology | Cancelled — features removed in Epic 8 |
| Epic 3 | Construction & optimizer methodology | Cancelled — features removed in Epic 8 |
| Epic 4 | Monitoring & overlay review | Cancelled — features removed in Epic 8 |
| Epic 5 | Usable Core Flow | Complete — superseded by Epic 8 |
