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
