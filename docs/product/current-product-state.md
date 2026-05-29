# Current Product State

*Canonical shipped-state inventory. Updated: 2026-05-25 (after Epic 8).*

---

## What the product is

A local-first portfolio research tool. The researcher imports broker statements, and the product computes deterministic analytics displayed on two tabs.

---

## Two tabs

### Dashboard
Shows portfolio performance history:
- Time-weighted return for the full history and selected sub-windows
- Benchmark comparison (vs SPY default, selectable)
- Monthly returns grid
- Risk metrics: max drawdown, volatility, Sharpe-equivalent
- Investor economics (withheld when return-basis trust is insufficient)
- Factor model snapshot (rolling factor loadings)

Requires a history context (imported price history or synthetic from current holdings).

### Exposure
Shows current portfolio composition:
- **vs Market drift panel** (top): rolling portfolio return vs benchmark for 1m, 3m, 6m, 12m, and since-import windows. Benchmark selectable; default SPY. Synthetic-history Trust badge.
- **Rolling correlation & beta chart**: dual-axis (ρ left, β right), 20d/60d/252d window selector. Synthetic-history Trust badge.
- Current state concentration (top positions, asset class split)
- **Factor return attribution card**: cumulative chart + period attribution table; 20d/60d/252d window. Synthetic-history Trust badge.
- **Multi-benchmark correlation table**: ρ / β / R² vs SPY, QQQ, GLD, IEF, VT; rows sorted by |ρ| desc, unavailable last. Synthetic-history Trust badge.

The visual surface uses design tokens from `apps/desktop/src/app/styles.css` (`:root` block — colors, spacing, typography, radius) and shared primitives in `apps/desktop/src/app/primitives/` (`CardShell`, `TrustBadge`, `WindowSelector`, `EmptyState`, `LoadingState`, `ErrorState`, `ChartShell`, `chartDefaults`). Accessibility baseline: every card is a `role="region"` with `aria-labelledby`; every chart has `role="img"` + descriptive `aria-label`; `WindowSelector` buttons have a token-styled `:focus-visible` outline; the multi-benchmark correlation ρ column uses both color *and* a sign-symbol prefix (▲▲ / ▲ / • / ▼ / ▼▼) so it's distinguishable for color-blind users. The `designSystem.audit.test.ts` regression test enforces the design-system contract.

**For agents building new Exposure-tab cards**: the `ui-polish` skill (`.claude/skills/ui-polish/SKILL.md`) is the canonical guidance — token inventory, primitive prop signatures, canonical card pattern code block, accessibility checklist, anti-patterns. Auto-invoked by `build-story` on frontend tickets. The long-lived contract doc is `docs/contracts/ui-design-system.md`.

---

## Import workflow

The researcher imports statements via the Import flow:
- Supported importers: Interactive Brokers (IBKR), Freedom24, ESPP
- Import produces an `ImportedPortfolioSnapshot` with positions, ledger, reconciliation checks
- Multiple statements can be stacked as snapshot nodes; the researcher selects which to analyze
- Import Admission Review: a local review of data quality issues (non-financial, desktop-only)

---

## Backend

6 route modules:
- `exposure.py` — portfolio exposure analysis
- `dashboard_history.py` — portfolio performance history
- `diagnostics.py` — factor model and risk diagnostics (called internally by Exposure)
- `imports.py` — broker statement import
- `market_data.py` — historical prices and ETF holdings
- `health.py` — health check

~13 service files, all under `services/quant-engine/app/services/`.

---

## Trust semantics (always-on)

| Level | Meaning |
|---|---|
| `verified` | Engine can make the documented trust claim for that path |
| `degraded` | Outputs computed but trust downgraded; stronger claims suppressed |
| `withheld` | Investor-economics outputs suppressed pending return-basis justification |
| `unavailable` | Required inputs or trustworthy path do not exist |

Never collapse `withheld` into `unavailable`. Never fabricate or silently fallback.

---

## What is intentionally not in the product

- Workspace / ranking / construction / optimizer — removed in Epic 8
- Backtest tab — removed in Epic 8
- Monitoring / alert workflows — removed in Epic 8
- Trade execution of any kind — never planned
