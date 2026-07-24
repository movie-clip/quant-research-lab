# Current Product State

*Canonical shipped-state inventory. Updated: 2026-07-04 (after Epic 25).*

---

## What the product is

A local-first portfolio research tool. The researcher imports broker statements, and the product computes deterministic analytics displayed on three tabs.

---

## Three tabs

### Dashboard
Shows portfolio performance history:
- **Performance & Benchmark card** (Epic 25 / US-25.1): indexed portfolio-vs-benchmark
  line chart (base 100) + summary strip (Portfolio Value, Time-Weighted Return,
  Money-Weighted Return, Net Contributions) for a selectable range; return-basis
  label per path (Verified / Price-return only / Unverified proxy / Unavailable)
- **Monthly Returns grid** (Epic 25 / US-25.2): signed monthly return cells for the
  same selected range; whole-card hidden (not zero-filled) when the reconstructed
  series is marked unreliable
- **Risk Summary card** (Epic 25 / US-25.3): portfolio/benchmark/downside volatility,
  tracking error, current/max drawdown, factor & position HHI, top-N factor/
  position risk share, and Information Ratio + Active Return vs benchmark
  (US-25.5) — sourced from the Diagnostics engine (not the withheld
  dashboard-history `max_drawdown_pct` path, which stays withheld under the
  investor-economics policy below)
- **Rolling Factor Analysis card**: rolling factor loadings snapshot
- **Sector composition donut** and **Benchmark Positioning card**: current holdings
  composition and benchmark-relative positioning

Investor economics (TWR/benchmark/excess) is withheld by policy when
return-basis trust is insufficient; only the narrow exact-slice allowlist in
`docs/contracts/dashboard-fields.md` is admitted even then. The Risk Summary
card is unaffected by this withholding — it sources drawdown from the
separate Diagnostics path instead.

Requires a history context (imported price history or synthetic from current holdings).

*(Epic 25 restored this surface after finding that several prior UI refactors
had progressively removed it from `DashboardPanel.tsx` without a corresponding
docs update — the backend fields were fully computed, tested, and golden-pinned
throughout, but had no rendering component. See
`docs/product/prd/epic-25-dashboard-performance-risk-summary.md`.)*

### Exposure
Shows current portfolio composition:
- **vs Market drift panel** (top): rolling portfolio return vs benchmark for 1m, 3m, 6m, 12m, and since-import windows (since-import anchors at the statement-period start). Benchmark selectable; default SPY. Self-fetching card — renders on Exposure-tab open with no interaction (US-30.3). Synthetic-history Trust badge.
- **Rolling correlation & beta chart**: dual-axis (ρ left, β right), 20d/60d/252d window selector. Synthetic-history Trust badge.
- Current state concentration (top positions, asset class split)
- **Factor return attribution card**: cumulative chart + period attribution table; 20d/60d/252d window. Synthetic-history Trust badge.
- **Factor Drift Summary card** (Epic 16): ranked per-factor drift (`latest − reference` rolling loading) over a 20d/60d/252d window, rendered as divergent magnitude bars (positive right of baseline, negative left) with signed value + ▲/▼ direction marker. Reuses the engine's existing `rolling_loadings_<window>` series — no backend. Factors null at the window endpoints are excluded (never zero-imputed); fails closed to an EmptyState on insufficient history. Synthetic-history Trust badge.
- **Multi-benchmark correlation table**: ρ / β / R² vs SPY, QQQ, GLD, IEF, VT; rows sorted by |ρ| desc, unavailable last. Synthetic-history Trust badge.
- **Intra-portfolio correlation heatmap** (Epic 17): holdings × holdings pairwise Pearson correlation matrix over a 20d/60d/252d window (top-15 holdings by weight), plus a diversification summary (average pairwise ρ, most/least-correlated pair, **Diversification Ratio** — Choueifaty & Coignard 2008, and **Effective Number of Bets** — Meucci 2009, via numpy eigvalsh — both US-17.2; null/"Unavailable" when inputs insufficient). Every cell prints the numeric ρ + a ▲▲/▲/•/▼/▼▼ sign glyph over the `--color-corr-*` palette (color-blind-safe); the diagonal is a muted 1.00; sub-threshold pairs render "n/a" (never 0); holdings without sufficient price history are excluded and disclosed. Cash/non-priceable positions excluded. Synthetic-history Trust badge; EmptyState when fewer than 2 priceable holdings have history.

The visual surface uses design tokens from `apps/desktop/src/app/styles.css` (`:root` block — colors, spacing, typography, radius) and shared primitives in `apps/desktop/src/app/primitives/` (`CardShell`, `TrustBadge`, `WindowSelector`, `EmptyState`, `LoadingState`, `ErrorState`, `ChartShell`, `chartDefaults`). Accessibility baseline: every card is a `role="region"` with `aria-labelledby`; every chart has `role="img"` + descriptive `aria-label`; `WindowSelector` buttons have a token-styled `:focus-visible` outline; the multi-benchmark correlation ρ column uses both color *and* a sign-symbol prefix (▲▲ / ▲ / • / ▼ / ▼▼) so it's distinguishable for color-blind users. The `designSystem.audit.test.ts` regression test enforces the design-system contract.

**For agents building new Exposure-tab cards**: the `ui-polish` skill (`.claude/skills/ui-polish/SKILL.md`) is the canonical guidance — token inventory, primitive prop signatures, canonical card pattern code block, accessibility checklist, anti-patterns. Auto-invoked by `build-story` on frontend tickets. The long-lived contract doc is `docs/contracts/ui-design-system.md`.

### Risk
Shows pre-decision risk-budget views (Epic 13):
- **Stress Scenarios card**: three predefined factor-shock scenarios (Broad Market Selloff, Rates Down Risk-On, Inflation Reacceleration) with projected portfolio % impact. Sorted by absolute magnitude desc; horizontal magnitude bar per row; color-coded ±% (red/green/muted). Point-in-time — no window selector. Synthetic-history Trust badge.
- **Drawdown Analytics card**: underwater drawdown curve (Recharts AreaChart) plus top-5 historical drawdown episodes table (Peak / Trough / Recovery / Magnitude / Duration / Underwater). `recovery_date=null` renders as italic "Still underwater". 4-option window selector: 252d / 756d / 1260d / Max (engine cap 3000 calendar days). Synthetic-history Trust badge. Each episode row expands into a **Contributors drawer** (Epic 15 / US-15.2) showing per-position decomposition under arithmetic Brinson attribution — Symbol / Weight @ Peak / Return / Contribution columns sorted by absolute contribution; "Other" aggregate row for positions ranked 6+; "Residual (unexplained)" row when partial data; partial-trust caption surfaces the unexplained share when some positions had missing prices; toggle disabled when decomposition is unavailable (e.g. peak state missing).
- **VaR & Distribution card**: daily return histogram (Recharts BarChart; loss-tail bars colored red, rest muted; VaR-95 and Mean reference lines) plus a 3-section table — Percentiles (5/10/50/90/95) / Tail Risk (VaR 95, CVaR 95, VaR 99) / Distribution shape (Mean, Std, Skew, Kurtosis-excess). VaR / CVaR cells red when positive (real loss), muted when negative or null. 3-option window selector: 60d / 252d / 504d (default 252; no "Max" — VaR is interpretable only relative to a fixed lookback). Synthetic-history Trust badge.

The Risk tab uses the same Epic 12 design-system primitives as Exposure (`CardShell`, `TrustBadge`, `WindowSelector`, `ChartShell`, `chartDefaults`, state primitives). All three cards self-fetch via `useEffect` on `[snapshot, window]` and surface `trust='unavailable'` with EmptyState when the factor model is empty (Stress) or fewer than 20 daily observations are available (Drawdown, VaR). The CVaR ≥ VaR invariant is enforced by the engine (raises on violation per Acerbi & Tasche 2002). Contract doc: `docs/contracts/risk-fields.md`.

---

## Import workflow

The researcher imports statements via the Import flow:
- Supported importers: Interactive Brokers (IBKR — Activity-Statement CSV is the canonical current format, imported end-to-end since US-28.2; PDF chain remains for legacy 2022–2025 statements), Freedom24 (PDF), ESPP (PDF)
- The desktop file picker accepts `.pdf` and `.csv`; the golden pipeline and `scripts/refresh_statement.py` key off `docs/IB2026.csv`
- Import produces an `ImportedPortfolioSnapshot` with positions, ledger, reconciliation checks
- Multiple statements can be stacked as snapshot nodes; the researcher selects which to analyze
- Import Admission Review: a local review of data quality issues (non-financial, desktop-only)

---

## Backend

12 route modules:
- `exposure.py` — portfolio exposure analysis
- `dashboard_history.py` — portfolio performance history
- `diagnostics.py` — factor model and risk diagnostics (called internally by Exposure)
- `drift.py` — portfolio drift vs benchmark (Exposure top panel)
- `attribution.py` — factor return attribution
- `correlation.py` — multi-benchmark correlation matrix
- `stress.py` — stress scenario projections (Risk tab, Epic 13)
- `drawdown.py` — drawdown analytics + episodes (Risk tab, Epic 13)
- `distribution.py` — VaR / CVaR / return distribution (Risk tab, Epic 13)
- `imports.py` — broker statement import
- `market_data.py` — historical prices and ETF holdings
- `health.py` — health check

~16 service files, all under `services/quant-engine/app/services/`, plus pure-analytics modules under `services/quant-engine/app/analytics/` (incl. `drawdown.py` and `distribution.py` added in Epic 13).

**Market-data providers (Epic 18):** price history is served behind `MarketDataService` with two providers tried in priority order — **FMP (primary)** then **Yahoo Finance via `yfinance` (secondary fallback)**, the latter used only when FMP returns nothing (e.g. European UCITS ETFs FMP's plan 402s). Provenance (`fmp` vs `yfinance`) is recorded per symbol and surfaced visibly. The Exposure tab shows a portfolio-level **"Data sources" panel** (US-18.2) grouping holdings into FMP (primary) / Yahoo Finance (secondary) / unpriced via the `POST /engines/provenance/run` engine; the Intra-Portfolio Correlation card also keeps an inline "via Yahoo Finance" marker (US-18.1). The panel also surfaces **instrument identity-mismatch warnings** (Epic 19 / US-19.1): when a registry-known ticker's fund name is identity-disjoint from the broker statement's own description (a possible mislabel, e.g. the DFND case), it shows a "⚠ Possible identity mismatch" line. The same check is emitted as the `instrument_description_registry_consistency` Import Admission check. Detection is conservative (flag only on disjoint identity; never auto-corrects). The `DFND` (VanEck Defense) symbol resolves to the real Yahoo lines `DFNS.L`/`DFEN.DE`/`DFNG.L` — never the look-alike `DFND.L` (a different fund) (US-18.3). yfinance is a real second source, never a proxy substitute.

**Cache control (Epic 20 / US-20.1):** the local JSON file cache (FMP + Yahoo) is inspectable and clearable in-app via `GET /cache/stats` + `POST /cache/clear`, surfaced as a "Market-data cache" card on the Exposure tab (entry counts per namespace + a Clear button). Reduces FMP overuse on top of the existing TTL/negative-cache/in-flight-dedup layer.

**Import Admission Review card (Epic 22 / US-22.1):** the Exposure tab renders the full Import Admission Review (`ImportAdmissionSummaryV1`) as a card — the overall **decision** (admitted / degraded / withheld) and **trust level** badges, plus one row per admission check (residual-cash, NAV, position-market-value, symbol identity, description-consistency, ISIN-consistency) showing its status (pass / warn / fail / unavailable, with a symbol prefix so status isn't colour-only), human-readable message, and observed/comparison/delta evidence + affected fields. Presentational only — rendered from the persisted workspace `admissionSummary` (a persisted-import artifact), never re-fetched or recomputed; survives reload. An import with no review shows an explicit unavailable state, never a fabricated "all clear". The existing Data Sources identity-warning line is unchanged.

---

## Trust semantics (always-on)

| Level | Meaning |
|---|---|
| `verified` | Engine can make the documented trust claim for that path |
| `degraded` | Outputs computed but trust downgraded; stronger claims suppressed |
| `withheld` | Investor-economics outputs suppressed pending return-basis justification |
| `unavailable` | Required inputs or trustworthy path do not exist |

Never collapse `withheld` into `unavailable`. Never fabricate or silently fallback.

**Replay coverage disclosures** (imported ledger-replay path). The replay
reconstructs the positions held on each day of the statement window, so it
values symbols the portfolio no longer holds. Two degradations are surfaced
rather than absorbed:

| Disclosure | Meaning |
|---|---|
| `statement_anchored_symbols` (US-30.2) | Held symbol with no fetchable price history — valued flat at its statement close price (broker-truth-adjacent) |
| `run_metadata.unpriced_replay_symbols` (US-31.2) | Symbol held on a day with **no** price history **and** no statement anchor — contributed 0 to that day's market value |

The second is the weaker case and the newer one: before US-31.2 those symbols
were never fetched at all, so a since-sold position silently contributed $0 to
the replayed NAV for the whole window.

---

## What is intentionally not in the product

- Workspace / ranking / construction / optimizer — removed in Epic 8
- Backtest tab — removed in Epic 8
- Monitoring / alert workflows — removed in Epic 8
- Trade execution of any kind — never planned
