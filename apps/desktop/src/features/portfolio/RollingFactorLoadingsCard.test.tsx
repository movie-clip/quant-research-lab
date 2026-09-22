import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedStatisticalFactorModelFixture } from '../../test/portfolioFixtures'
import { buildExposureFactorModel, composeExposureView } from './portfolioAnalysisAdapter'
import { RollingFactorLoadingsCard, sortTooltipPayloadRows } from './RollingFactorLoadingsCard'
import type { DiagnosticsEngineResponse, StatisticalFactorModel } from './types'

afterEach(() => { cleanup() })

// The card's default selected window is 60d, so these cases drive the 60d
// window's `status` — via `createImportedStatisticalFactorModelFixture`'s
// override param — rather than clicking the window toggle.
//
// `factorModelOverrides` layers additional overrides onto the same base
// fixture (e.g. `insufficient_history`) for the model-level `partial` cases,
// still going through the real adapter chain (`composeExposureView` /
// `buildExposureFactorModel`) rather than hand-building a response literal.
function buildFactorModel(
  windowStatusOverrides?: Partial<Record<20 | 60 | 252, string>>,
  factorModelOverrides?: Partial<StatisticalFactorModel>,
) {
  const exposure = createExposureEngineFixture()
  const diagnostics: DiagnosticsEngineResponse = {
    ...createDiagnosticsEngineFixture(),
    statistical_factor_model: {
      ...createImportedStatisticalFactorModelFixture(windowStatusOverrides),
      ...factorModelOverrides,
    },
  }
  const view = composeExposureView(exposure, diagnostics)
  return { view, factorModel: buildExposureFactorModel(view) }
}

describe('RollingFactorLoadingsCard', () => {
  it('sorts rolling factor tooltip rows by highest visible value first', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'market', value: 1.08 },
        { dataKey: 'technology', value: 0.22 },
        { dataKey: 'growth', value: 0.31 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })

  it('breaks equal tooltip values with chart line order', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'technology', value: 0.31 },
        { dataKey: 'growth', value: 0.31 },
        { dataKey: 'market', value: 1.08 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })

  it('does not render a Degraded badge when both window- and model-level status are ok', () => {
    // Base fixture's model-level status is 'partial' (FINDING 1's fix now
    // reads it), so the true "no degrade signal at either level" case must
    // also override the model status, not just the window's.
    const { view, factorModel } = buildFactorModel({ 60: 'ok' }, { status: 'ok', insufficient_history: [] })
    render(<RollingFactorLoadingsCard result={view} factorModel={factorModel} />)
    expect(screen.queryByText('Degraded')).toBeNull()
  })

  // `windows[].status == "partial"` is unreachable from the real engine
  // (services/quant-engine/app/analytics/risk.py:1107 vs :1644-1648 — see
  // 05-quant-audit.md § FINDING 3): a window only ever reaches "partial" via
  // a below-threshold predicate that a below-threshold rolling-loadings point
  // can never simultaneously satisfy. This case is not asserting a state the
  // engine can produce; it pins the card's defensive branch for that value so
  // the branch does not silently rot if it is ever exercised by a future
  // engine change, while the model-level `partial` cases below cover the
  // degrade signal the engine actually emits today (FINDING 1).
  it('renders a Degraded badge for the defensive window-level partial branch (not a reachable engine state)', () => {
    // Base fixture already carries `partial` for the 60d window.
    const { view, factorModel } = buildFactorModel()
    render(<RollingFactorLoadingsCard result={view} factorModel={factorModel} />)
    expect(screen.getByText('Degraded')).toBeTruthy()
  })

  it('renders a Degraded badge when the selected window status is degraded_unverified_return_basis', () => {
    const { view, factorModel } = buildFactorModel({ 60: 'degraded_unverified_return_basis' })
    render(<RollingFactorLoadingsCard result={view} factorModel={factorModel} />)
    expect(screen.getByText('Degraded')).toBeTruthy()
  })

  it('renders a Degraded badge naming the missing factors when model-level status is partial and insufficient_history lists them for the selected window', () => {
    // Window-level status is 'ok' so the badge falls through to the
    // model-level `partial` check (base fixture's model status is already
    // 'partial'); insufficient_history carries an entry for the 60d window.
    const { view, factorModel } = buildFactorModel(
      { 60: 'ok' },
      { insufficient_history: [{ window_days: 60, required_observations: 60, available_observations: 60, missing_factors: ['growth'] }] },
    )
    render(<RollingFactorLoadingsCard result={view} factorModel={factorModel} />)
    const badge = screen.getByText('Degraded')
    expect(badge.getAttribute('title')).toContain('Growth')
  })

  // FINDING 4 (08-quant-audit.md): a short-history-only fit with all 16 factor
  // proxies present must not show Degraded. Model-level `partial` fires from
  // `insufficient_history` for *either* a missing proxy or too few shared
  // observations (risk.py:1119), and those causes are indistinguishable in
  // `status` alone. The badge is now gated on the selected window's own
  // `missing_factors` (RollingFactorLoadingsCard.tsx:216), not on model
  // status, so a window with no matching missing-factors entry renders no
  // badge — the generic fallback tooltip this case used to pin has no
  // reachable caller left (CR-4).
  it('does not render a Degraded badge for a short-history-only fixture with all factor proxies present', () => {
    // Base fixture's insufficient_history only carries the 252d window with
    // an empty `missing_factors`, so the 60d window (status forced to 'ok')
    // has no matching missing-factors entry and falls through to no badge.
    const { view, factorModel } = buildFactorModel({ 60: 'ok' })
    render(<RollingFactorLoadingsCard result={view} factorModel={factorModel} />)
    expect(screen.queryByText('Degraded')).toBeNull()
  })
})
