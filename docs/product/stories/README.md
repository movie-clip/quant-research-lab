# User Stories

One file per user story. A story is a vertical slice of user value, not a
technical feature. Delivery model: see [`../prd/README.md`](../prd/README.md).

## Naming

`US-<epic>.<n>-<slug>.md` — e.g. `US-3.1-inverse-volatility-weighting-policy.md`.

## Lifecycle

| Status | Meaning |
|---|---|
| **Backlog** | Story defined (statement + acceptance criteria + rough test plan). Not yet ticketed. |
| **Next phase** | Pulled into the active phase and broken into ordered tickets. |
| **In progress** | An agent is delivering it via the `build-story` skill. |
| **Done** | Every acceptance criterion met, full test plan passing, docs updated. |

## Index

### Epic 25 — Dashboard Performance & Risk Summary (active)

PRD: [`prd/epic-25-dashboard-performance-risk-summary.md`](../prd/epic-25-dashboard-performance-risk-summary.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-25.1](US-25.1-dashboard-performance-benchmark-card.md) | Performance & benchmark comparison card | TWR index chart vs benchmark + summary strip (Portfolio Value/TWR/MWR/Net Contributions), sourced from existing `range_metrics`/`performance_series` | Done |
| [US-25.2](US-25.2-dashboard-monthly-returns-grid.md) | Monthly returns grid card | Grid from `range_metrics[*].monthly_returns`; whole-card hide when `monthly_returns_reliable = false` | Next phase |
| [US-25.3](US-25.3-dashboard-risk-metrics-card.md) | Risk metrics card (volatility, drawdown, concentration) | Sourced from the already-fetched `DiagnosticsResult`, not the withheld dashboard-history path | Next phase |
| [US-25.4](US-25.4-epic-25-docs-closeout.md) | Docs close-out | Reconcile `dashboard-fields.md` + `current-product-state.md`; backfill HHI + MWR formula sections in `financial-methodology.md` | Next phase |

Recommended build order: 25.1 → 25.2 → 25.3 → 25.4.

---

### Epic 24 — Codebase Improvement (active)

PRD: [`prd/epic-24-codebase-improvement.md`](../prd/epic-24-codebase-improvement.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-24.1](US-24.1-fix-hardcoded-year-ledger-filters.md) | Fix the hardcoded calendar-year ledger filters (latent bugs) | Remove the `year == 2025` filters in `activity.py` / `reconciliation.py` so non-2025 statements work; 2025 goldens unchanged | Done |
| [US-24.2](US-24.2-extract-risk-model-rubric-constants.md) | Extract the risk-model scoring rubric & thresholds into named constants | Lift `risk.py` mapping-score weights / hard-caps / thresholds / regime cutoffs + the coverage threshold into documented constants; behaviour-neutral (goldens unchanged) | Done |
| [US-24.3](US-24.3-dedupe-shared-analytics-constants.md) | De-duplicate the shared analytics constants & lookback helper | One shared `app/core/constants.py` for `lookback_calendar_days` / `MIN_DAILY_OBSERVATIONS` / `DEFAULT_BENCHMARK_SYMBOL`; behaviour-neutral (goldens unchanged) | Done |
| [US-24.4](US-24.4-harden-freedom24-importer-parsing.md) | Harden the Freedom24 importer parsing + extract its hardcodes | Fail-safe positional parsing (skip malformed → no crash); extract format hardcodes to named constants; correct the (non-real) ISIN-gap; FF2026 fixture pinned | Done |

---

### Epic 23 — Dead-Code Cleanup & Codebase Review (complete)

PRD: [`prd/epic-23-dead-code-cleanup-and-review.md`](../prd/epic-23-dead-code-cleanup-and-review.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-23.1](US-23.1-detection-tooling-and-register.md) | Detection tooling + tech-debt register + removal protocol | Dev-only dead-code tooling (vulture/ruff, knip, `noUnusedLocals` staged) + `docs/tech-debt-register.md` + removal protocol | Done |
| [US-23.2](US-23.2-backend-sweep-analytics-schemas-domain.md) | Backend sweep — analytics, schemas, domain, instruments | Remove confirmed-dead pure-logic code; catalog smells; no formula change | Done |
| [US-23.3](US-23.3-backend-sweep-services-routes-clients.md) | Backend sweep — services, routes, clients, core, importers | Remove dead wiring/routes/clients; catalog smells; routes stay reachable | Done |
| [US-23.4](US-23.4-frontend-sweep-app-and-features.md) | Frontend sweep — app & features | Remove dead files/types/helpers; catalog smells (disposition → US-23.9; DashboardPerformanceChart → US-23.6) | Done |
| [US-23.5](US-23.5-contract-schema-type-docs-drift.md) | Contract & schema↔type↔docs drift reconciliation | Three-way audit + reconcile drift so deletions don't break a documented seam | Done |
| [US-23.6](US-23.6-tests-fixtures-golden-hygiene.md) | Tests, fixtures & golden-pipeline hygiene | Migrate to shared fixtures, remove dead/skip tests; keep guard + goldens invariants | Done |
| [US-23.7](US-23.7-scripts-docs-reconciliation-closeout.md) | Scripts, tooling & docs reconciliation | Sweep `scripts/`; reconcile docs; consolidate register → seed Epic 24 | Done |
| [US-23.8](US-23.8-enforce-dead-code-gate.md) | Enforce the dead-code floor in the canonical test gate | Wire knip + ruff + vulture zero-findings into `run_all_tests.py` (the tail; no ESLint) so dead code can't re-accumulate | Done |
| [US-23.9](US-23.9-remove-disposition-plumbing.md) | Remove the unused disposition plumbing (cross-seam) | Carved from US-23.4: remove the no-producer/no-consumer disposition subsystem (FE persistence + BE schema), gated by the workspace round-trip tests | Done |

---

### Epic 22 — Import Admission Review UI (completed)

PRD: [`prd/epic-22-import-admission-review-ui.md`](../prd/epic-22-import-admission-review-ui.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-22.1](US-22.1-import-admission-review-card.md) | Import Admission Review card | Render the persisted `admissionSummary` (decision + trust + per-check rows) as an Exposure-tab card — frontend-only | Done |
| US-22.2 | Admission review disposition workflow | Record a disposition per flagged check (accept-exception/needs-correction/deferred) with rationale | Won't do — not needed for a single-user local-first tool (2026-06-12) |

---

### Epic 21 — Testing Strategy & Architecture Hardening (completed)

PRD: [`prd/epic-21-testing-strategy-hardening.md`](../prd/epic-21-testing-strategy-hardening.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-21.1](US-21.1-deterministic-test-suite.md) | Deterministic suite — no live network in tests | Mock the 4 FMP-dependent "real portfolio" tests + autouse network guard with `live_data` marker | Done |
| [US-21.2](US-21.2-shared-test-fixtures.md) | Shared test-fixtures module | `app/tests/fixtures.py` (snapshot builders + market-data mock installer); migrate the 3 dict-based duplicate sets | Done |
| [US-21.3](US-21.3-response-integrity-property-test.md) | Engine response-integrity property test | Parametrized JSON-strict check over 8 engine routes + self-policing route-table coverage; `risk.py` non-finite audit | Done |
| [US-21.4](US-21.4-golden-pipeline-determinism.md) | Golden pipeline determinism | Goldens from a committed frozen fixture set — no live FMP, no env var, no per-machine churn | Done |
| [US-21.5](US-21.5-assertion-conventions-suite-speed.md) | Assertion conventions + suite speed | Additive-tolerant assertion rules in write-tests skill; pytest-xdist parallel run | Done |

Recommended build order: 21.1 → 21.2 → 21.3 → 21.4 → 21.5.

---

### Epic 20 — Market-Data Cache Efficiency & Control (completed)

PRD: [`prd/epic-20-market-data-cache-efficiency.md`](../prd/epic-20-market-data-cache-efficiency.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-20.1](US-20.1-cache-stats-and-clear.md) | Cache stats + clear (route + UI) | `GET /cache/stats` + `POST /cache/clear`; Market-data cache card on the Exposure tab | Done |
| [US-20.2](US-20.2-history-range-normalization.md) | History range normalization | One widened superset fetch per symbol, sliced per request — the FMP-call reduction | Done |
| [US-20.3](US-20.3-in-memory-layer-parallel-fetch.md) | In-memory layer + parallel fetch | Process memo over the file cache + parallel multi-symbol fetch | Done |

Recommended build order: 20.1 → 20.2 → 20.3.

---

### Epic 19 — Instrument Identity Integrity (completed)

PRD: [`prd/epic-19-instrument-identity-integrity.md`](../prd/epic-19-instrument-identity-integrity.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-19.1](US-19.1-instrument-description-consistency.md) | Instrument description-consistency check | Backend detector + admission check + Data Sources panel warning for ticker↔description mismatches | Done |
| [US-19.2](US-19.2-isin-keyed-registry-identity.md) | ISIN-keyed registry identity | Statement-sourced ISIN seeds in the registry + definitive ISIN-mismatch detection | Done |

Recommended build order: 19.1 → 19.2.

---

### Epic 18 — Secondary Market-Data Provider (complete)

PRD: [`prd/epic-18-secondary-market-data-provider.md`](../prd/epic-18-secondary-market-data-provider.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-18.1](US-18.1-yfinance-fallback-provider.md) | yfinance fallback provider + data provenance | Backend — `YFinanceClient` + `MarketDataService` fallback + provenance; provenance marker on the Intra-Portfolio Correlation card | Done |
| [US-18.2](US-18.2-portfolio-provenance-indicator.md) | Portfolio-level data-sources indicator | One Exposure-tab "Data sources" panel (FMP vs Yahoo vs unpriced) via a dedicated provenance engine | Done |
| [US-18.3](US-18.3-defense-etf-symbol-mapping.md) | Defense-ETF Yahoo symbol mapping | `DFND` → real VanEck Defense lines (not the look-alike `DFND.L`); DEFS/IDFN already correct | Done |
| [US-18.4](US-18.4-sanitize-nonfinite-price-rows.md) | Sanitize non-finite price rows (bugfix) | Yahoo NaN bars skipped at the client + seam-level row sanitization in `MarketDataService` (fixes correlation 500s) | Done |

Recommended build order: 18.1 → 18.2 → 18.3.

---

### Epic 17 — Intra-Portfolio Correlation (complete)

PRD: [`prd/epic-17-intra-portfolio-correlation.md`](../prd/epic-17-intra-portfolio-correlation.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-17.1](US-17.1-pairwise-correlation-heatmap.md) | Pairwise correlation matrix engine + heatmap | Full-stack — `pairwise_correlation_matrix()` + `average_pairwise_correlation()` in `analytics/correlation.py`; `intra_correlation_engine.py`; `POST /engines/correlation/intra`; `IntraCorrelationHeatmap` card on the Exposure tab | Done |
| [US-17.2](US-17.2-diversification-summary-metrics.md) | Diversification summary metrics | Full-stack — `diversification_ratio()` + `effective_number_of_bets()` (numpy) in `analytics/correlation.py`; engine wiring; summary-strip additions on `IntraCorrelationHeatmap` | Done |
| ~~US-17.3~~ | ~~Docs, contracts, roadmap close-out~~ | Cancelled — docs reconciled per-story via update-docs | Cancelled |

Recommended build order: 17.1 → 17.2.

---

### Epic 16 — Factor Drift Visualization (complete)

PRD: [`prd/epic-16-factor-drift-visualization.md`](../prd/epic-16-factor-drift-visualization.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-16.1](US-16.1-factor-drift-summary-card.md) | Factor Drift Summary card | Frontend-only — `FactorDriftSummaryCard` on the Exposure tab: ranked per-factor delta (latest − reference) bars, 20d/60d/252d window, Synthetic badge, unavailable state | Done |

Single-story epic (quick-win follow-up). No build-order constraints.

---

### Epic 15 — Position-Level Analytics (complete)

PRD: [`prd/epic-15-position-level-analytics.md`](../prd/epic-15-position-level-analytics.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-15.1](US-15.1-drawdown-decomposition-engine.md) | Drawdown decomposition engine + schema | Backend — `decompose_drawdown_episode()` in `analytics/drawdown.py`; extend `DrawdownEpisode` Pydantic schema; wire into `drawdown_engine` | Done |
| [US-15.2](US-15.2-drawdown-contributors-drawer.md) | Drawdown card "Contributors" drawer | Frontend — expandable per-episode drawer in `DrawdownAnalyticsCard.tsx` | Done |
| ~~US-15.3~~ | ~~Factor loading drift chart~~ | **Cancelled 2026-06-04**: existing `RollingFactorLoadingsCard` on Dashboard tab already covers the use case | Cancelled |
| [US-15.4](US-15.4-epic-15-docs-closeout.md) | Epic 15 docs close-out | Docs — `risk-fields.md` decomposition fields, methodology verify, current-product-state Risk-tab extension | Done |

Recommended build order: 15.1 → 15.2 → 15.3 → 15.4.

---

### Epic 14 — Post-Epic-13 Bug Sweep (complete)

PRD: [`prd/epic-14-post-epic-13-bug-sweep.md`](../prd/epic-14-post-epic-13-bug-sweep.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-14.1](US-14.1-fix-overlay-symbol-collision.md) | Fix overlay symbol collision (sum, don't replace) | Frontend — `overlayImportedSnapshot` in `portfolioSnapshot.ts` | Done |
| [US-14.2](US-14.2-drawdown-smart-default-window.md) | DrawdownAnalyticsCard smart-default window fallback | Frontend — cycle 1260→756→252→Max on `trust='unavailable'` | Done |
| [US-14.3](US-14.3-freedom24-fmp-enrichment.md) | Freedom24 FMP company-profile enrichment for unknown symbols | Backend — new shared `enrich_imported_instruments` helper + Freedom24 parser wire-up | Done |

Recommended build order: 14.1 → 14.2 → 14.3.

---

### Epic 13 — Risk Analytics Tab (complete)

PRD: [`prd/epic-13-risk-analytics-tab.md`](../prd/epic-13-risk-analytics-tab.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-13.1](US-13.1-risk-tab-and-stress-card.md) | Risk tab + Stress Scenarios card | Full-stack — `App.tsx` tab union extended + `RiskPanel.tsx` scaffold + `StressScenariosCard.tsx` + `POST /engines/stress/run` route + service | Done |
| [US-13.2](US-13.2-drawdown-analytics-card.md) | Drawdown Analytics card | Full-stack — `analytics/drawdown.py` (episode identification) + `POST /engines/drawdown/run` + `DrawdownAnalyticsCard.tsx` (underwater curve + top-N table) | Done |
| [US-13.3](US-13.3-var-distribution-card.md) | VaR & Distribution card | Full-stack — `analytics/distribution.py` + `POST /engines/distribution/run` + `VarDistributionCard.tsx` (histogram + percentile/tail/shape table) | Done |
| [US-13.4](US-13.4-risk-tab-polish-and-a11y.md) | UI density polish + trust-state + a11y verification | Frontend — RiskPanel header rewrite, VarDistributionCard section header slim-down, cross-card audit, density tests | Done |
| [US-13.5](US-13.5-epic-13-docs-closeout.md) | Docs close-out | Docs — `risk-fields.md`, methodology verification, roadmap, `current-product-state.md`, `CLAUDE.md` | Done |

Stories must be built in order (13.1 → 13.2 → 13.3 → 13.4 → 13.5).

---

### Epic 12 — UI Polish & Design System (complete)

PRD: [`prd/epic-12-ui-polish-design-system.md`](../prd/epic-12-ui-polish-design-system.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-12.1](US-12.1-design-tokens-and-card-polish.md) | Design tokens + apply to the four Exposure cards | Frontend — `styles.css` :root tokens + refactor 5 card files + fix rolling-correlation axis overlap + audit test | Done |
| [US-12.2](US-12.2-primitive-components.md) | Primitive components + refactor cards | Frontend — `<CardShell>`, `<WindowSelector>`, `<TrustBadge>`, `<EmptyState>`, `<LoadingState>`, `<ErrorState>` + refactor 5 cards | Done |
| [US-12.3](US-12.3-accessibility-and-chart-defaults.md) | Accessibility + Recharts defaults (ChartShell) | Frontend — ARIA, focus-visible, color-blind-safe, `<ChartShell>` wrapper + contrast audit | Done |
| [US-12.4](US-12.4-ui-polish-skill-and-closeout.md) | `ui-polish` skill + Epic 12 close-out | `.claude/skills/ui-polish/SKILL.md` + `docs/contracts/ui-design-system.md` + roadmap close | Done |

Stories must be built in order (12.1 → 12.2 → 12.3 → 12.4).

---

### Epic 11 — Factor Return Attribution (complete)

PRD: [`prd/epic-11-factor-return-attribution.md`](../prd/epic-11-factor-return-attribution.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-11.1](US-11.1-attribution-engine-endpoint.md) | Attribution engine + endpoint | Backend — analytics function, Pydantic schema, FastAPI route, pytest | Done |
| [US-11.2](US-11.2-attribution-card-chart-table.md) | Attribution card (chart + table) | Frontend — FactorAttributionCard, vitest | Done |
| [US-11.3](US-11.3-attribution-docs-closeout.md) | Docs, contracts, roadmap close-out | Docs — attribution-fields.md, methodology verification, slice log | Done |

Stories must be built in order (11.1 → 11.2 → 11.3). US-11.2 depends on the endpoint from US-11.1.

---

### Epic 10 — Multi-broker Import Correctness (complete)

PRD: [`prd/epic-10-multi-broker-import-correctness.md`](../prd/epic-10-multi-broker-import-correctness.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-10.1](US-10.1-three-broker-combine-tests.md) | 3-way combine and API-level import tests | Backend pytest — combine + import_statements + analytics | Done |
| [US-10.2](US-10.2-add-statement-overlay-tests.md) | Sequential add-statement overlay tests | Frontend vitest — overlayImportedSnapshot 3-step flow | Done |

---

### Epic 9 — Portfolio Correlation & Co-movement Analysis (complete)

PRD: [`prd/epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-9.1](US-9.1-indexed-return-chart.md) | Indexed return time-series chart | Frontend — chart of existing `daily_series` data (no backend work) | Done |
| [US-9.2](US-9.2-rolling-correlation-chart.md) | Rolling correlation and beta chart | Frontend — chart of existing `rolling_risk` data (no backend work) | Done |
| [US-9.3](US-9.3-multi-benchmark-correlation-matrix.md) | Multi-benchmark correlation matrix | Full-stack — new `correlation.py` analytics + `POST /engines/correlation/multi` + frontend table | Done |
| [US-9.4](US-9.4-fix-rolling-factor-loadings-methodology.md) | Fix rolling factor loadings methodology | Backend bugfix — per-window orthogonalization + ridge floor | Done |
| [US-9.5](US-9.5-correlation-docs-closeout.md) | Docs, contracts, roadmap close-out | Docs — `correlation-fields.md`, methodology verification, slice log | Done |
| [US-9.6](US-9.6-correlation-followups.md) | Multi-benchmark correlation follow-ups | Tests + docs — sort regression, trust-indicator pinning, umbrella methodology section | Done |

Stories must be built in order (9.1 → 9.2 → 9.3 → 9.5). US-9.4 is a Done bugfix independent of 9.1–9.3.

---

### Epic 8 — Reset to Analysis Core (complete)

PRD: [`prd/epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-8.1](US-8.1-remove-workflow-tabs.md) | Remove workflow tabs from navigation | Frontend — nav only | Done |
| [US-8.2](US-8.2-strip-backtest-frontend.md) | Strip Workspace and Monitoring frontend | Frontend — features/backtest/ | Done |
| [US-8.3](US-8.3-strip-ranking-optimizer-frontend.md) | Strip ranking and optimizer frontend | Frontend — features/strategy-lab/, features/generic-ranking/, features/optimizer/ | Done |
| [US-8.4](US-8.4-strip-app-state.md) | Strip App.tsx workflow state and storage | Frontend — App.tsx, workspace storage | Done |
| [US-8.5](US-8.5-strip-ranking-construction-optimizer-backend.md) | Remove ranking, construction, and optimizer backend | Backend — routes, services, schemas | Done |
| [US-8.6](US-8.6-strip-backtest-monitoring-backend.md) | Remove backtest and monitoring backend | Backend — routes, services, schemas | Done |
| [US-8.7](US-8.7-prune-portfolio-feature-dir.md) | Prune portfolio feature directory | Frontend — features/portfolio/ dead code | Done |
| [US-8.8](US-8.8-reset-docs-and-contracts.md) | Reset docs and contracts | Docs — contracts, PRDs, roadmap | Done |
| [US-8.9](US-8.9-add-drift-vs-benchmark.md) | Add portfolio drift vs index benchmarks | Backend + Frontend — new Exposure feature | Done |

Stories must be built in order (8.1 → 8.2 → ... → 8.9). Each leaves a compilable, test-green codebase. Story 8.9 (the one additive story) goes last.

---

### Epic 5 — Usable Core Flow (complete — superseded by Epic 8 pivot)

| Story | Title | Status |
|---|---|---|
| [US-5.1](US-5.1-fix-app-navigation-order.md) | Fix app navigation order | Done |
| [US-5.2](US-5.2-workspace-candidate-ux.md) | Make Workspace candidate selection self-explanatory | Done |
| [US-5.3](US-5.3-fix-review-in-construction.md) | Fix "Review in Construction" end-to-end | Done |
| [US-5.4](US-5.4-clear-replay-comparison-output.md) | Clear replay comparison output | Done |

### Epic 3 — Construction & Optimizer Methodology (cancelled — features removed in Epic 8)

| Story | Title | Status |
|---|---|---|
| [US-3.1](US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | Cancelled |
| [US-3.2](US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | Cancelled |
| [US-3.3](US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | Cancelled |

To implement a story, invoke the `build-story` skill and point it at the file.
To author a new story from a feature idea, invoke the `write-story` skill.
