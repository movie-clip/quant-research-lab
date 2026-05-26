import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
    expect(screen.getByText('Look-Through Summary')).toBeTruthy()
    expect(screen.getByText('Coverage state')).toBeTruthy()
    expect(screen.getByText('live')).toBeTruthy()
    expect(screen.getByText('Covered market value')).toBeTruthy()
    expect(screen.getByText('Coverage ratio')).toBeTruthy()
    expect(screen.getByText('Top Constituents')).toBeTruthy()
    expect(screen.getByText('Basis: imported snapshot truth plus resolved ETF constituents.')).toBeTruthy()
    expect(screen.getByText('Look-through coverage 100.00% ($50000.00 of $50000.00).')).toBeTruthy()
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
    expect(screen.getByText('Basis: imported snapshot truth plus resolved ETF constituents; unresolved ETFs stay partial.')).toBeTruthy()
    expect(screen.getByText('Look-through coverage 10.00% ($5000.00 of $50000.00).')).toBeTruthy()
    expect(screen.getByText(/Limitation: partial look-through leaves VUAA unresolved/)).toBeTruthy()
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
    expect(screen.getByText('Concentration read unavailable')).toBeTruthy()
  })
})
