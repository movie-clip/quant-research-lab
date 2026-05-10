---
name: portfolio-analytics
description: Use when work touches portfolio risk, performance, volatility, drawdown, factor analytics, or the import/engine contract layers that assemble those outputs. Triggers on changes to return construction, drawdown basis, benchmark-relative analytics, factor exposure payloads, or restore/open paths that affect analytics input selection.
---

# Portfolio Analytics

Protect the portfolio analytics stack from regressions in methodology, benchmark handling, schema discipline, and validation coverage.

## Common trigger paths

- `services/quant-engine/app/analytics/*.py`
- `services/quant-engine/app/services/import_engine.py`
- `services/quant-engine/app/schemas/reconciliation.py`
- `services/quant-engine/app/schemas/imports.py`
- `apps/desktop/src/features/portfolio/types.ts`
- `apps/desktop/src/features/portfolio/*.tsx` (when analytics payloads consumed directly)
- `apps/desktop/src/app/App.tsx` (when restore/open affects analytics input)

## Non-negotiable rules

### 1. Cash-flow-neutral analytics basis
Portfolio risk and volatility must use cash-flow-neutral return logic. Don't use raw NAV deltas when external deposits/withdrawals can distort the metric. Drawdown must be derived from a compounded return index (return-consistent wealth path), not naive raw NAV deltas.

### 2. Benchmark separation must stay explicit
Portfolio return, benchmark return, and active return remain conceptually separate in payloads and methodology. Never collapse benchmark-relative metrics into absolute metrics. Preserve or extend explicit benchmark fields rather than replacing portfolio-only fields.

### 3. No interpretation prose in payloads
Acceptable: concise methodological description ("compounded return over rolling 252-day window"). Not acceptable: advisory or interpretive language ("this indicates the portfolio is risky"). UI surfaces show methodology, not opinions.

### 4. Preserve methodology and assumptions fields
If a payload exposes methodology or assumptions fields, keep them present and structurally consistent unless there's a strong reason to improve them. Prefer additive changes over silent removal.

### 5. No silent fallback widening
If analytics-adjacent restore/open paths fail to build the intended analytics input, do not silently fall back to a weaker engine unless that fallback is an explicit shipped contract. Invalid imported diagnostics, dashboard history, or factor-model inputs should fail clearly. If a fallback is intentional, document it and cover with regression tests.

### 6. Regression coverage required
Any meaningful analytics change must update regression tests for the affected methodology. Cover the applicable subset of: volatility, drawdown, benchmark-relative metrics, cash-flow neutrality, rolling windows, multi-statement import effects.

## Analytics invariants checklist

- Portfolio return series is cash-flow-neutral
- Drawdown is derived from a return-consistent wealth path
- Benchmark return series is explicit and aligned by date
- Active return logic is explicit where relevant
- Rolling metrics respect window sufficiency rules
- Methodology text matches implementation
- Assumptions fields still exist and remain accurate
- Frontend types still match backend payloads
- Restore/open flows do not silently swap analytics input sources

## Common failure modes

- Deposits or withdrawals causing fake volatility spikes
- Withdrawals creating fake drawdowns
- Benchmark volatility / tracking error disappearing from payloads
- Frontend types drifting from backend schema after analytics payload changes
- UI copy reintroducing interpretation instead of neutral methodology
- Import window logic accidentally using malformed or stale date ranges
- Restore/open code swallowing analytics-input failures and falling back to generic engines without explicit contract coverage

## Validation commands

```bash
# Default analytics regression set
cd services/quant-engine
python -m pytest app/tests/test_analytics.py app/tests/test_importer.py app/tests/test_routes.py app/tests/test_mocked_flows.py
```

If frontend types or payload shapes changed:

```bash
cd apps/desktop
npx vitest run src/features/portfolio/ExposurePanel.test.tsx src/features/portfolio/DashboardPanel.test.tsx src/features/portfolio/DiagnosticsPanel.test.tsx src/app/App.test.tsx
```

## Reporting

When closing analytics work, explicitly state:
- what analytics basis changed or remained preserved
- whether methodology/assumptions fields changed
- which regression cases were covered
- which validation commands passed
