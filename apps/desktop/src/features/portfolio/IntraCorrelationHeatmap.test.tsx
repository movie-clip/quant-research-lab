import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ImportedSnapshot, IntraCorrelationResult } from './types'
import { IntraCorrelationHeatmap } from './IntraCorrelationHeatmap'

vi.mock('./portfolioAnalysisAdapter', () => ({
  runIntraCorrelationEngine: vi.fn(),
}))

import { runIntraCorrelationEngine } from './portfolioAnalysisAdapter'
const mockRun = vi.mocked(runIntraCorrelationEngine)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const snapshot = { positions: [] } as unknown as ImportedSnapshot

function makeResult(overrides?: Partial<IntraCorrelationResult>): IntraCorrelationResult {
  return {
    symbols: ['AAA', 'BBB', 'CCC'],
    matrix: [
      [1.0, 0.82, null],
      [0.82, 1.0, -0.10],
      [null, -0.10, 1.0],
    ],
    average_pairwise_correlation: 0.36,
    most_correlated_pair: { symbol_a: 'AAA', symbol_b: 'BBB', correlation: 0.82 },
    least_correlated_pair: { symbol_a: 'BBB', symbol_b: 'CCC', correlation: -0.10 },
    diversification_ratio: 1.42,
    effective_number_of_bets: 2.3,
    excluded_symbols: [],
    yahoo_sourced_symbols: [],
    lookback_days: 60,
    trust: 'synthetic',
    ...overrides,
  }
}

describe('IntraCorrelationHeatmap', () => {
  it('renders the grid labelled with the response symbols', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    // Each symbol appears as both a column and a row header (≥ 2 occurrences).
    await waitFor(() => expect(screen.getAllByText('AAA').length).toBeGreaterThanOrEqual(2))
    expect(screen.getAllByText('BBB').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('CCC').length).toBeGreaterThanOrEqual(2)
  })

  it('renders diagonal cells as 1.00', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(screen.getAllByText('1.00').length).toBe(3))
  })

  it('renders off-diagonal cells with numeric rho and a sign glyph', async () => {
    mockRun.mockResolvedValue(makeResult())
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('▲▲ 0.82'))
    // symmetric matrix → two cells carry 0.82 (plus the summary strip's
    // most-correlated callout), so at least two occurrences.
    expect(screen.getAllByText(/0\.82/).length).toBeGreaterThanOrEqual(2)
  })

  it('renders a null pair as n/a, not 0', async () => {
    mockRun.mockResolvedValue(makeResult())
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(screen.getAllByText('n/a').length).toBe(2))
    expect(container.textContent).not.toContain('0.00')
  })

  it('re-fetches with the selected window', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(mockRun).toHaveBeenCalledWith(snapshot, 20))

    fireEvent.click(screen.getByRole('button', { name: '252d window' }))
    await waitFor(() => expect(mockRun).toHaveBeenCalledWith(snapshot, 252))
  })

  it('renders the diversification summary strip', async () => {
    mockRun.mockResolvedValue(makeResult())
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('Avg pairwise ρ'))
    expect(container.textContent).toContain('0.36')
    expect(container.textContent).toContain('AAA · BBB')
    expect(container.textContent).toContain('BBB · CCC')
  })

  it('discloses excluded holdings when present', async () => {
    mockRun.mockResolvedValue(makeResult({ excluded_symbols: ['DDD'] }))
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/1 holding excluded/i))
    expect(container.textContent).toContain('DDD')
  })

  it('shows the Synthetic badge with tooltip', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    const badge = await screen.findByText('Synthetic')
    expect(badge.getAttribute('title')).toBe(
      'Pairwise correlations are computed from current holdings applied to historical prices. Not verified broker return basis.',
    )
  })

  it('renders the diversification ratio and effective number of bets', async () => {
    mockRun.mockResolvedValue(makeResult())
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('Diversification Ratio'))
    expect(container.textContent).toContain('1.42')
    expect(container.textContent).toContain('Effective number of bets')
    expect(container.textContent).toContain('2.3')
  })

  it('renders Unavailable for diversification ratio when null', async () => {
    mockRun.mockResolvedValue(makeResult({ diversification_ratio: null }))
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('Diversification Ratio'))
    // The DR value reads "Unavailable", not a fabricated 0.
    expect(container.textContent).not.toContain('1.42')
    expect(container.textContent).toContain('Unavailable')
  })

  it('renders Unavailable for effective number of bets when null', async () => {
    mockRun.mockResolvedValue(makeResult({ effective_number_of_bets: null }))
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('Effective number of bets'))
    expect(container.textContent).not.toContain('2.3')
    expect(container.textContent).toContain('Unavailable')
  })

  it('renders the via-Yahoo provenance marker when holdings are Yahoo-sourced', async () => {
    mockRun.mockResolvedValue(makeResult({ yahoo_sourced_symbols: ['VUAA', 'SXRV'] }))
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/via Yahoo Finance/i))
    expect(container.textContent).toContain('VUAA')
    expect(container.textContent).toContain('SXRV')
    expect(container.textContent).toMatch(/secondary source/i)
  })

  it('omits the provenance marker when no holdings are Yahoo-sourced', async () => {
    mockRun.mockResolvedValue(makeResult({ yahoo_sourced_symbols: [] }))
    const { container } = render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toContain('Diversification Ratio'))
    expect(container.textContent).not.toMatch(/via Yahoo Finance/i)
  })

  it('renders an EmptyState when trust is unavailable', async () => {
    mockRun.mockResolvedValue(makeResult({ trust: 'unavailable', symbols: [], matrix: [], average_pairwise_correlation: null, most_correlated_pair: null, least_correlated_pair: null }))
    render(<IntraCorrelationHeatmap snapshot={snapshot} />)
    await waitFor(() => expect(screen.getByText('Not enough priceable holdings for a correlation matrix.')).toBeTruthy())
    expect(screen.queryByText('AAA')).toBeNull()
  })
})
