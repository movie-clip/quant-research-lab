# Epic Roadmap

*Living execution snapshot. Updated: 2026-06-04 (Epic 16 complete).*

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
