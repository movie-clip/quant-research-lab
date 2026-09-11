import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsEngineFixture } from '../../test/portfolioFixtures'
import type { DiagnosticsEngineResponse } from './types'
import { RiskSummaryCard } from './RiskSummaryCard'

// US-45.1 (T-45.1.2): whole-card fold/expand toggle on RiskSummaryCard.
// Default-expanded, aria-expanded/aria-controls convention mirrors
// DrawdownAnalyticsCard.tsx's row-level toggle (see DrawdownAnalyticsCard.test.tsx).

afterEach(() => {
  cleanup()
})

function getToggle() {
  // The button's accessible name flips with state (per RiskSummaryCard.tsx),
  // matching the DrawdownAnalyticsCard convention — match on the stable prefix.
  return screen.getByRole('button', { name: /(Collapse|Expand) Risk Summary/i })
}

describe('RiskSummaryCard — fold/expand (US-45.1)', () => {
  it('AC1: defaults to expanded and shows all detail rows on first render', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    const toggle = getToggle()
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText('Portfolio Volatility')).toBeTruthy()
    expect(screen.getByText('Max Drawdown')).toBeTruthy()
    expect(screen.getByText('Factor HHI')).toBeTruthy()
  })

  it('AC2/AC3: a single toggle collapses the card and hides the stat rows', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    // Single control — exactly one toggle button on the card.
    expect(screen.getAllByRole('button', { name: /Risk Summary/i })).toHaveLength(1)

    fireEvent.click(getToggle())

    expect(screen.queryByText('Portfolio Volatility')).toBeNull()
    expect(screen.queryByText('Tracking Error')).toBeNull()
    expect(screen.queryByText('Downside Volatility')).toBeNull()
    expect(screen.queryByText('Benchmark Volatility')).toBeNull()
    expect(screen.queryByText('Current Drawdown')).toBeNull()
    expect(screen.queryByText('Max Drawdown')).toBeNull()
    expect(screen.queryByText('Factor HHI')).toBeNull()
    expect(screen.queryByText('Position HHI')).toBeNull()
    expect(screen.queryByText('Top-1 Factor Risk Share')).toBeNull()
    expect(screen.queryByText('Top-3 Factor Risk Share')).toBeNull()
    expect(screen.queryByText('Top-1 Position Risk Share')).toBeNull()
    expect(screen.queryByText('Top-5 Position Risk Share')).toBeNull()
  })

  it('AC2/AC3: collapsing the conditional relative-risk rows also hides them', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.relative_risk = { ...diagnostics.relative_risk, information_ratio: 0.42, active_return_pct: 3.5 }
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('Information Ratio')).toBeTruthy()
    fireEvent.click(getToggle())
    expect(screen.queryByText('Information Ratio')).toBeNull()
    expect(screen.queryByText('Active Return (vs benchmark)')).toBeNull()
  })

  it('AC2: activating the toggle a second time re-expands and restores the rows', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    fireEvent.click(getToggle())
    expect(screen.queryByText('Portfolio Volatility')).toBeNull()

    fireEvent.click(getToggle())
    expect(screen.getByText('Portfolio Volatility')).toBeTruthy()
    expect(screen.getByText('Max Drawdown')).toBeTruthy()
  })

  it('AC4: collapsed state still renders the title and trust label, no stat rows', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.run_metadata.section_trust.risk_contribution_path = 'verified_adjusted_close'
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    fireEvent.click(getToggle())

    expect(screen.getByText('Risk Summary')).toBeTruthy()
    expect(
      screen.getByText('Risk contribution basis (adjusted-close price provenance only): Verified'),
    ).toBeTruthy()
    expect(screen.queryByText('Portfolio Volatility')).toBeNull()
  })

  it('AC5: aria-expanded reflects state through both transitions', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    const toggle = getToggle()
    expect(toggle.getAttribute('aria-expanded')).toBe('true')

    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: /Risk Summary/i }).getAttribute('aria-expanded')).toBe('false')

    fireEvent.click(screen.getByRole('button', { name: /Risk Summary/i }))
    expect(screen.getByRole('button', { name: /Risk Summary/i }).getAttribute('aria-expanded')).toBe('true')
  })

  it('AC5: aria-controls on the toggle points at the rendered detail region id', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    const toggle = getToggle()
    const controlsId = toggle.getAttribute('aria-controls')
    expect(controlsId).toBeTruthy()
    expect(document.getElementById(controlsId!)).toBeTruthy()
  })

  it('AC8: the unavailable empty state renders no toggle control', () => {
    render(<RiskSummaryCard diagnosticsAnalysis={null} />)

    expect(screen.getByText('Risk metrics unavailable')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Risk Summary/i })).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('AC8: the unavailable state message is unchanged when a sub-section is missing', () => {
    const partialDiagnostics = {
      ...createDiagnosticsEngineFixture(),
      volatility_summary: undefined,
      drawdown_summary: undefined,
      risk_concentration_summary: undefined,
    } as unknown as DiagnosticsEngineResponse
    render(<RiskSummaryCard diagnosticsAnalysis={partialDiagnostics} />)

    expect(screen.getByText('Risk metrics unavailable')).toBeTruthy()
    expect(screen.getByText(/Import a portfolio with usable history/)).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('AC7: values and trust label while expanded are unchanged by this story', () => {
    // Regression guard for AC7: pins the same figures DashboardPanel.test.tsx's
    // pre-existing US-25.3 tests already assert, expanded is still the default.
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.volatility_summary.benchmark_volatility_pct = null
    render(<RiskSummaryCard diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('18.20%')).toBeTruthy()
    expect(screen.getByText('7.20%')).toBeTruthy()
    const benchmarkVolLabel = screen.getByText('Benchmark Volatility')
    const row = benchmarkVolLabel.closest('.benchmark-card-metric')
    expect(row ? within(row as HTMLElement).getByText('n/a') : null).toBeTruthy()
  })
})
