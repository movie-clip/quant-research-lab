import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture } from '../../test/portfolioFixtures'
import { ExposurePanel } from './ExposurePanel'
import { composeExposureView } from './portfolioAnalysisAdapter'
import type { ExposureAnalysis } from './types'

const mockExposureView: ExposureAnalysis = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())

afterEach(() => {
  cleanup()
})

describe('ExposurePanel', () => {
  it('renders empty state without analysis', () => {
    render(<ExposurePanel result={null} />)

    expect(screen.getAllByText('Look-Through Exposure Core').length).toBeGreaterThan(0)
  })

  it('renders snapshot selector options when provided', () => {
    const onSnapshotSelect = vi.fn()

    render(
      <ExposurePanel
        result={mockExposureView}
        snapshotOptions={[{ id: 'draft', label: 'Working Draft' }, { id: 'node-1', label: 'Base Import' }]}
        selectedSnapshotId="draft"
        onSnapshotSelect={onSnapshotSelect}
      />,
    )

    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })
    expect(screen.getByText('Look-Through Exposure Core').closest('article')?.className.includes('exposure-panel')).toBe(true)
    expect(onSnapshotSelect).toHaveBeenCalledWith('node-1')
  })

  it('renders a header exit CTA back to the imported snapshot when provided', () => {
    const onSnapshotSelect = vi.fn()

    render(
      <ExposurePanel
        result={mockExposureView}
        snapshotOptions={[{ id: 'draft', label: 'Working Draft' }, { id: 'node-1', label: 'Base Import' }]}
        selectedSnapshotId="draft"
        snapshotExitOption={{ id: 'node-1', label: 'Return to imported snapshot' }}
        onSnapshotSelect={onSnapshotSelect}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Return to imported snapshot' }))

    expect(onSnapshotSelect).toHaveBeenCalledWith('node-1')
  })

  it('renders the look-through summary first with explicit live coverage messaging', () => {
    render(<ExposurePanel result={mockExposureView} />)

    expect(screen.getByText('Look-Through Exposure Core').closest('article')?.className.includes('exposure-panel')).toBe(true)
    expect(screen.getByLabelText('Exposure Dense Insight Strip')).toBeTruthy()
    expect(screen.getByText('Look-through coverage is 100.00% of the portfolio.')).toBeTruthy()
    expect(screen.getByText('Technology leads sector mix at 40.00%.')).toBeTruthy()
    expect(screen.getByText('Active share is 62.00% versus SPY.')).toBeTruthy()
    expect(screen.getByText('Look-Through Summary')).toBeTruthy()
    expect(screen.getByText('Coverage state')).toBeTruthy()
    expect(screen.getByText('live')).toBeTruthy()
    expect(screen.getByText('Covered market value')).toBeTruthy()
    expect(screen.getByText('Coverage ratio')).toBeTruthy()
    expect(screen.getByText('Top Constituents')).toBeTruthy()
    expect(screen.getByText('Basis: imported snapshot truth plus resolved ETF constituents.')).toBeTruthy()
    expect(screen.getByText('Look-through coverage 100.00% ($50000.00 of $50000.00).')).toBeTruthy()
  })

  it('renders sector composition from look-through-aware composition when available', () => {
    render(<ExposurePanel result={mockExposureView} />)

    expect(screen.getAllByText('Sector Composition').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Basis: sector mix uses look-through composition.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Technology').length).toBeGreaterThan(0)
    expect(screen.getByText('40.00%')).toBeTruthy()
    expect(screen.getByText('Health Care')).toBeTruthy()
  })

  it('renders current-state concentration facts only', () => {
    render(<ExposurePanel result={mockExposureView} />)

    expect(screen.getByText('Concentration Pack')).toBeTruthy()
    expect(screen.getByText('Current-state concentration')).toBeTruthy()
    expect(screen.getByText('Composition only')).toBeTruthy()
    expect(screen.getByText('available')).toBeTruthy()
    expect(screen.getByText('Top 1 position')).toBeTruthy()
    expect(screen.getAllByText('24.00%').length).toBeGreaterThan(0)
    expect(screen.getByText('Top 5 positions')).toBeTruthy()
    expect(screen.getByText('Position HHI')).toBeTruthy()
    expect(screen.getByText('Sector HHI')).toBeTruthy()
    expect(screen.getByText('Top Positions')).toBeTruthy()
    expect(screen.getByText('Top Sectors')).toBeTruthy()
  })

  it('renders ranked compact concentration lists with five visible rows max', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          current_state_concentration: {
            ...mockExposureView.current_state_concentration,
            top_positions: [
              { name: 'AAPL', market_value: 10000, weight: 0.2 },
              { name: 'JPM', market_value: 9000, weight: 0.18 },
              { name: 'MSFT', market_value: 8000, weight: 0.16 },
              { name: 'GOOG', market_value: 7000, weight: 0.14 },
              { name: 'AMZN', market_value: 6000, weight: 0.12 },
              { name: 'META', market_value: 5000, weight: 0.1 },
            ],
            top_sectors: [
              { name: 'Technology', market_value: 18000, weight: 0.36 },
              { name: 'Financials', market_value: 12000, weight: 0.24 },
              { name: 'Health Care', market_value: 7000, weight: 0.14 },
              { name: 'Industrials', market_value: 5000, weight: 0.1 },
              { name: 'Energy', market_value: 4000, weight: 0.08 },
              { name: 'Utilities', market_value: 3000, weight: 0.06 },
            ],
          },
        }}
      />,
    )

    expect(screen.getAllByText('1').length).toBeGreaterThan(1)
    expect(screen.getAllByText('AMZN').length).toBeGreaterThan(0)
    expect(screen.queryByText('META')).toBeNull()
    expect(screen.getByText('Energy')).toBeTruthy()
    expect(screen.queryByText('Utilities')).toBeNull()
  })

  it('marks concentration availability partial when only part of the pack is present', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          current_state_concentration: {
            ...mockExposureView.current_state_concentration,
            top_positions: [],
            top_sectors: [],
            top_5_position_weight: null,
            top_3_sector_weight: null,
            position_hhi: null,
            sector_hhi: null,
          },
        }}
      />,
    )

    expect(screen.getAllByText('partial').length).toBeGreaterThan(0)
    expect(screen.queryByText('Top 5 positions')).toBeNull()
    expect(screen.queryByText('Position HHI')).toBeNull()
  })

  it('renders benchmark-relative positioning as current-state composition only', () => {
    render(<ExposurePanel result={mockExposureView} />)

    const positioningSection = screen.getByText('Benchmark-Relative Positioning').closest('section') as HTMLElement
    expect(screen.getByText('Benchmark-Relative Positioning')).toBeTruthy()
    expect(screen.getByText('Current-state active bets only.')).toBeTruthy()
    expect(screen.getByText('Portfolio in benchmark')).toBeTruthy()
    expect(screen.getByText('Active share')).toBeTruthy()
    expect(screen.getByText('Top Overweights')).toBeTruthy()
    expect(within(positioningSection).getByText('AAPL')).toBeTruthy()
    expect(within(positioningSection).getByText('17.00% active')).toBeTruthy()
    expect(screen.queryByText(/partly aligned/i)).toBeNull()
  })

  it('keeps partial look-through trust inline and does not imply full resolution', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          lookthrough: {
            ...mockExposureView.lookthrough,
            covered_market_value: 5000,
            coverage_ratio: 0.1,
            uncovered_positions: ['VUAA'],
          },
          exposure_availability: {
            lookthrough_status: 'partial',
            lookthrough_confidence: 'medium',
            benchmark_overlap_status: 'unavailable',
            benchmark_overlap_confidence: 'low',
            note: 'Look-through exposure is partial because some holdings could not be resolved, and benchmark overlap is unavailable because benchmark composition could not be loaded.',
          },
        }}
      />,
    )

    expect(screen.getAllByText('partial').length).toBeGreaterThan(0)
    expect(screen.getByText('Look-through coverage is 10.00% (partial).')).toBeTruthy()
    expect(screen.getByText('Basis: imported snapshot truth plus resolved ETF constituents; unresolved ETFs stay partial.')).toBeTruthy()
    expect(screen.getByText('Look-through coverage 10.00% ($5000.00 of $50000.00).')).toBeTruthy()
    expect(screen.getByText(/Limitation: partial look-through leaves VUAA unresolved/)).toBeTruthy()
    expect(screen.getByText('Limitation: partial look-through can still shift sector mix.')).toBeTruthy()
    expect(screen.queryByText(/benchmark overlap is unavailable/i)).toBeNull()
  })

  it('suppresses benchmark-relative availability notes inside Look-Through Exposure Core', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            note: 'Benchmark-relative overlap is unavailable because benchmark composition could not be loaded. Current look-through exposure is still shown.',
          },
        }}
      />,
    )

    const lookthroughSection = screen.getByText('Look-Through Summary').closest('section')
    expect(lookthroughSection).toBeTruthy()
    const sliceText = lookthroughSection?.textContent ?? ''

    expect(sliceText.includes('Benchmark-relative overlap is unavailable')).toBe(false)
    expect(sliceText.includes('benchmark composition could not be loaded')).toBe(false)
  })

  it('marks benchmark-relative positioning unavailable instead of implying neutrality', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          market_overlap: {
            ...mockExposureView.market_overlap,
            active_share: null,
            portfolio_in_benchmark_weight: null,
            top_overweights: [],
            top_underweights: [],
          },
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            benchmark_overlap_status: 'unavailable',
            benchmark_overlap_confidence: 'low',
          },
        }}
      />,
    )

    expect(screen.getByText('Benchmark-relative positioning unavailable')).toBeTruthy()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.queryByText('0.00% active')).toBeNull()
  })

  it('shows degraded benchmark-relative trust when benchmark holdings support is incomplete', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          run_metadata: {
            ...mockExposureView.run_metadata!,
            source_status: {
              ...mockExposureView.run_metadata!.source_status,
              benchmark_holdings: 'degraded',
            },
          },
        }}
      />,
    )

    expect(screen.getAllByText('degraded').length).toBeGreaterThan(0)
    expect(screen.getByText('Benchmark-relative positioning is degraded versus SPY.')).toBeTruthy()
  })

  it('orders benchmark-relative cues deterministically and suppresses invalid rows', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          market_overlap: {
            ...mockExposureView.market_overlap,
            top_overweights: [
              { symbol: 'MSFT', name: 'Microsoft', portfolio_weight: 0.18, benchmark_weight: 0.06, active_weight: 0.12 },
              { symbol: 'AAPL', name: 'Apple', portfolio_weight: 0.24, benchmark_weight: 0.07, active_weight: 0.17 },
              { symbol: 'NVDA', name: 'NVIDIA', portfolio_weight: null as unknown as number, benchmark_weight: 0.05, active_weight: 0.11 },
            ],
            top_underweights: [
              { symbol: 'AMZN', name: 'Amazon', portfolio_weight: 0.0, benchmark_weight: 0.04, active_weight: -0.04 },
              { symbol: 'GOOG', name: 'Alphabet', portfolio_weight: 0.01, benchmark_weight: 0.04, active_weight: -0.03 },
            ],
          },
        }}
      />,
    )

    const overweightRows = screen.getAllByText(/active$/).map((node) => node.textContent)
    expect(overweightRows[0]).toBe('17.00% active')
    expect(overweightRows[1]).toBe('12.00% active')
    expect(screen.queryByText('NVDA')).toBeNull()
    const activeRows = screen.getAllByText(/active$/).map((node) => node.textContent)
    expect(activeRows).toContain('4.00% active')
    expect(activeRows).toContain('3.00% active')
  })

  it('falls back to holdings truth for sectors when look-through sectors are unavailable', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          lookthrough_sector_exposure: [],
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            lookthrough_status: 'unavailable',
          },
        }}
      />,
    )

    expect(screen.getAllByText('Basis: sector mix uses imported snapshot truth only.').length).toBeGreaterThan(0)
    expect(screen.getByText('Look-through coverage unavailable for sector mix.')).toBeTruthy()
    expect(screen.getByText('Limitation: sector mix does not include constituent ETF unpacking.')).toBeTruthy()
  })

  it('withholds sector and concentration modules when inputs are unavailable', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          lookthrough: {
            ...mockExposureView.lookthrough,
            covered_market_value: 0,
            coverage_ratio: 0,
            top_constituents: [],
          },
          overview: {
            ...mockExposureView.overview,
            sector_allocation: [],
          },
          lookthrough_sector_exposure: [],
          current_state_concentration: {
            ...mockExposureView.current_state_concentration,
            top_positions: [],
            top_sectors: [],
            top_1_position_weight: null,
            top_3_position_weight: null,
            top_5_position_weight: null,
            top_sector_weight: null,
            top_3_sector_weight: null,
            position_hhi: null,
            sector_hhi: null,
            effective_holdings: null,
          },
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            lookthrough_status: 'unavailable',
          },
        }}
      />,
    )

    expect(screen.getByText('Top constituents unavailable')).toBeTruthy()
    expect(screen.getByText('Sector composition unavailable')).toBeTruthy()
    expect(screen.getByText('Concentration read unavailable')).toBeTruthy()
  })
})
