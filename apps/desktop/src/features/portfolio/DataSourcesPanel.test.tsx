import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ImportedSnapshot, ProvenanceResult } from './types'
import { DataSourcesPanel } from './DataSourcesPanel'

vi.mock('./portfolioAnalysisAdapter', () => ({
  runProvenanceEngine: vi.fn(),
}))

import { runProvenanceEngine } from './portfolioAnalysisAdapter'
const mockRun = vi.mocked(runProvenanceEngine)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const snapshot = { positions: [] } as unknown as ImportedSnapshot

function makeResult(overrides?: Partial<ProvenanceResult>): ProvenanceResult {
  return {
    holdings: [],
    fmp_symbols: ['AAPL', 'MSFT'],
    yahoo_sourced_symbols: [],
    unavailable_symbols: [],
    identity_warnings: [],
    lookback_days: 30,
    ...overrides,
  }
}

describe('DataSourcesPanel', () => {
  it('renders the Yahoo-sourced count and symbols when present', async () => {
    mockRun.mockResolvedValue(makeResult({ yahoo_sourced_symbols: ['VUAA', 'SXRV'], fmp_symbols: ['AAPL'] }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/via Yahoo Finance/i))
    expect(container.textContent).toContain('VUAA')
    expect(container.textContent).toContain('SXRV')
    expect(container.textContent).toMatch(/secondary source/i)
  })

  it('renders the all-FMP quiet state when no secondary source', async () => {
    mockRun.mockResolvedValue(makeResult({ fmp_symbols: ['AAPL', 'MSFT'] }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/via FMP \(primary\)/i))
    expect(container.textContent).not.toMatch(/via Yahoo Finance/i)
  })

  it('lists unpriced holdings when present', async () => {
    mockRun.mockResolvedValue(makeResult({ fmp_symbols: ['AAPL'], unavailable_symbols: ['NOPE'] }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/no price history/i))
    expect(container.textContent).toContain('NOPE')
  })

  it('renders an identity-mismatch warning when present', async () => {
    mockRun.mockResolvedValue(makeResult({
      identity_warnings: [
        { symbol: 'DFND', statement_description: 'iShares Global Aerospace & Defence UCITS ETF', registry_name: 'VanEck Defense UCITS ETF', kind: 'description', statement_isin: null, expected_isin: null },
      ],
    }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/identity mismatch/i))
    expect(container.textContent).toContain('DFND')
    expect(container.textContent).toContain('iShares Global Aerospace & Defence UCITS ETF')
    expect(container.textContent).toContain('VanEck Defense UCITS ETF')
  })

  it('renders an ISIN identity mismatch with both ISINs (US-19.2)', async () => {
    mockRun.mockResolvedValue(makeResult({
      identity_warnings: [
        { symbol: 'VUAA', statement_description: 'VANGUARD S&P 500 UCITS ETF', registry_name: 'Vanguard S&P 500 UCITS ETF', kind: 'isin', statement_isin: 'IE000YYE6WK5', expected_isin: 'IE00BFMXXD54' },
      ],
    }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/identity mismatch \(isin\)/i))
    expect(container.textContent).toContain('VUAA')
    expect(container.textContent).toContain('IE000YYE6WK5')
    expect(container.textContent).toContain('IE00BFMXXD54')
  })

  it('renders description- and isin-kind warnings side by side', async () => {
    mockRun.mockResolvedValue(makeResult({
      identity_warnings: [
        { symbol: 'DFND', statement_description: 'iShares Global Aerospace & Defence UCITS ETF', registry_name: 'VanEck Defense UCITS ETF', kind: 'description', statement_isin: null, expected_isin: null },
        { symbol: 'VUAA', statement_description: 'VANGUARD S&P 500 UCITS ETF', registry_name: 'Vanguard S&P 500 UCITS ETF', kind: 'isin', statement_isin: 'IE000YYE6WK5', expected_isin: 'IE00BFMXXD54' },
      ],
    }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/identity mismatch/i))
    expect(container.textContent).toContain('statement says')
    expect(container.textContent).toContain('statement ISIN')
  })

  it('renders no identity warning when there are none', async () => {
    mockRun.mockResolvedValue(makeResult({ identity_warnings: [] }))
    const { container } = render(<DataSourcesPanel snapshot={snapshot} />)
    await waitFor(() => expect(container.textContent).toMatch(/via FMP \(primary\)/i))
    expect(container.textContent).not.toMatch(/identity mismatch/i)
  })

  it('renders nothing before a snapshot is loaded', () => {
    const { container } = render(<DataSourcesPanel snapshot={null} />)
    expect(container.firstChild).toBeNull()
    expect(mockRun).not.toHaveBeenCalled()
  })
})
