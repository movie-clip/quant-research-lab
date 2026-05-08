# portfolio-analytics-guard

## Purpose

Protect the portfolio analytics stack from subtle regressions in methodology, benchmark handling, schema discipline, and validation coverage.

Use this skill whenever work touches portfolio risk, performance, volatility, drawdown, factor analytics, or the import / engine contract layers that assemble those outputs.

## Trigger Paths

Use this skill whenever a change affects analytics methodology, analytics payload semantics, benchmark-relative fields, or import/engine behavior that feeds portfolio analytics outputs.

### Responsibility-Based Triggers

Apply this skill if the change touches any of these responsibilities, even if the file path is new or not listed below:

- return construction or wealth-path construction
- drawdown basis or volatility methodology
- benchmark-relative or active-return analytics
- factor exposure payloads or analytics summary fields
- import-window logic or importer-derived analytics inputs
- methodology text, assumptions fields, or analytics-facing docs
- app-level restore/open paths that can widen or silently substitute analytics inputs

### Vocabulary-Based Triggers

Apply this skill if the change introduces or modifies analytics vocabulary such as:

- `cash-flow-neutral`, `drawdown`, `wealth path`, `volatility`
- `benchmark`, `benchmark_return`, `active return`, `tracking error`
- `factor exposure`, `top_constituents`, `sector_position_breakdown`
- `methodology`, `assumptions`, `analysis window`, `rolling window`
- `imported diagnostics`, `dashboard history`, `exposure factor model`

If responsibility-based or vocabulary-based triggers match, use this skill even when the file path is not listed below.

### Common Trigger Paths

Common high-signal paths include:

- `services/quant-engine/app/analytics/*.py`
- `services/quant-engine/app/services/import_engine.py`
- `services/quant-engine/app/schemas/reconciliation.py`
- `services/quant-engine/app/schemas/imports.py`
- `apps/desktop/src/features/portfolio/types.ts`
- `apps/desktop/src/features/portfolio/*.tsx` when analytics payloads are consumed directly
- `apps/desktop/src/app/App.tsx` when restore/open logic can affect analytics input selection or fallback behavior

Apply it proactively for any related test updates in:

- `services/quant-engine/app/tests/test_analytics.py`
- `services/quant-engine/app/tests/test_importer.py`
- `services/quant-engine/app/tests/test_routes.py`
- `services/quant-engine/app/tests/test_mocked_flows.py`
- `apps/desktop/src/features/portfolio/*.test.tsx`
- `apps/desktop/src/app/App.test.tsx`
- helper modules and fixtures that build analytics-facing payloads or imported diagnostics/dashboard-history inputs

## Non-Negotiable Rules

### 1. Cash-Flow-Neutral Analytics Basis

- Portfolio risk and volatility calculations must use cash-flow-neutral return logic.
- Do not use raw changes in portfolio value when external deposits or withdrawals can distort the metric.
- Drawdown must be based on a compounded return index or equivalent return-consistent wealth path, not naive raw NAV deltas when cash flows are present.

### 2. Benchmark Separation Must Stay Explicit

- Keep portfolio return, benchmark return, and active return conceptually separate in payloads and methodology.
- Do not collapse benchmark-relative metrics into absolute metrics.
- Preserve or extend explicit benchmark fields rather than replacing portfolio-only fields.

### 3. No Interpretation Prose

- Avoid educational, advisory, or interpretive language in analytics payloads and UI-facing methodology text.
- Acceptable: concise methodological description.
- Not acceptable: commentary about what the user should conclude or how to interpret a risk number.

### 4. Preserve Methodology and Assumptions Fields

- If the payload currently exposes methodology or assumptions fields, keep them present and structurally consistent unless there is a strong reason to improve them.
- Prefer additive changes over silent removal or semantic drift.
- If methodology changes, update the text to describe the new basis precisely.

### 4a. No Silent Fallback Widening

- If analytics-adjacent restore/open paths fail to build the intended analytics input, do not silently fall back to a weaker or generic engine unless that fallback is already an explicit shipped contract.
- Invalid imported diagnostics, dashboard history, or factor-model inputs should fail clearly in the affected flow rather than widening semantics invisibly.
- If a fallback is intentional and shipped, document it explicitly and cover it with regression tests.

### 5. Regression Coverage Is Required

- Any meaningful analytics change must include or update regression tests for the affected methodology.
- At minimum, verify coverage for the applicable subset of:
  - volatility
  - drawdown
  - benchmark-relative metrics
  - cash-flow neutrality
  - rolling windows
  - multi-statement import effects on analytics windows

## Preferred Workflow

1. Identify whether the change affects:
   - return construction
   - performance path construction
   - drawdown basis
   - rolling volatility
   - benchmark alignment
   - factor exposure payloads
   - import-derived analysis windowing
2. Inspect the existing methodology text and schema fields before changing code.
3. Preserve existing field names unless there is a clear schema improvement reason.
4. Update tests in the same pass as the analytics change.
5. Validate both backend logic and any frontend type impact.

## Analytics Invariants Checklist

Before finishing, check all that apply:

- Portfolio return series is cash-flow-neutral.
- Drawdown is derived from a return-consistent wealth path.
- Benchmark return series is explicit and aligned by date.
- Active return logic is explicit where relevant.
- Rolling metrics respect window sufficiency rules.
- Methodology text matches implementation.
- Assumptions fields still exist and remain accurate.
- Frontend types still match backend payloads.
- Restore/open flows do not silently swap analytics input sources or widen semantics.

## Common Failure Modes To Catch

- Deposits or withdrawals causing fake volatility spikes.
- Withdrawals creating fake drawdowns.
- Benchmark volatility or tracking error disappearing from payloads.
- Frontend types drifting from backend schema after analytics payload changes.
- UI copy reintroducing interpretation instead of neutral methodology.
- Import window logic accidentally using malformed or stale date ranges.
- Restore/open code swallowing analytics-input failures and falling back to generic engines without explicit contract coverage.
- Analytics-adjacent files touched indirectly without verifying that no methodology or input-source behavior changed.

## Validation Commands

Run the smallest sufficient set, but default to:

```bash
python -m pytest app/tests/test_analytics.py app/tests/test_importer.py app/tests/test_routes.py app/tests/test_mocked_flows.py
```

If payload or frontend types changed, also run:

```bash
npm test -- --run src/features/portfolio/ExposurePanel.test.tsx src/features/portfolio/DashboardPanel.test.tsx src/features/portfolio/DiagnosticsPanel.test.tsx src/app/App.test.tsx
npm run build
```

## Expected Final Report Format

When closing work under this skill, explicitly state:

- what analytics basis changed or remained preserved
- whether methodology/assumptions fields changed
- which regression cases were covered
- which validation commands passed

## Manual Use In Current Environment

Because runtime skill loading is not yet wired up for this repo, invoke this skill manually in either of these ways:

1. Ask OpenCode: `Follow .opencode/skills/portfolio-analytics-guard.md for this change.`
2. Paste the relevant sections into the session prompt before starting analytics work.

## Future Automation Hook

When repo-level skill loading becomes available, register this file under the skill name:

- `portfolio-analytics-guard`
