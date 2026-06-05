import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FactorAttributionResponse, ImportedSnapshot } from './types'
import { FactorAttributionCard } from './FactorAttributionCard'

// Mock the adapter module so tests don't make real HTTP calls.
vi.mock('./portfolioAnalysisAdapter', () => ({
  runAttributionEngine: vi.fn(),
}))

import { runAttributionEngine } from './portfolioAnalysisAdapter'
const mockRunAttributionEngine = vi.mocked(runAttributionEngine)

// ── Fixtures ──────────────────────────────────────────────────────────────────

const MINIMAL_SNAPSHOT: ImportedSnapshot = {
  statement: {
    importer: 'interactive_brokers',
    account_id: null,
    base_currency: 'USD',
    statement_period: '2025-01-01 - 2025-12-31',
    page_count: null,
  },
  statements: [],
  positions: [],
  instruments: [],
  cash_balances: [],
  ledger_entries: [],
}

function makeAvailableAttribution(overrides?: Partial<FactorAttributionResponse>): FactorAttributionResponse {
  return {
    attribution_status: 'available',
    window: 60,
    cumulative_series: [
      {
        date: '2025-03-01',
        contributions: [
          { factor_key: 'market', cumul_contribution: 0.025 },
          { factor_key: 'growth', cumul_contribution: 0.012 },
        ],
        cumul_unexplained: -0.003,
        cumul_portfolio_return: 0.034,
      },
      {
        date: '2025-04-01',
        contributions: [
          { factor_key: 'market', cumul_contribution: 0.030 },
          { factor_key: 'growth', cumul_contribution: 0.015 },
        ],
        cumul_unexplained: -0.001,
        cumul_portfolio_return: 0.044,
      },
    ],
    period_attribution: [
      {
        factor_key: 'market',
        factor_label: 'Market',
        avg_beta: 0.82,
        factor_return_pct: 3.66,
        contribution_pct: 3.00,
      },
      {
        factor_key: 'growth',
        factor_label: 'Growth',
        avg_beta: 0.21,
        factor_return_pct: 7.14,
        contribution_pct: 1.50,
      },
    ],
    total_portfolio_return_pct: 4.40,
    total_unexplained_pct: -0.10,
    methodology_note:
      'Arithmetic (not compounded). Sum of daily factor contributions + unexplained equals arithmetic portfolio return.',
    ...overrides,
  }
}

function makeUnavailableAttribution(): FactorAttributionResponse {
  return {
    attribution_status: 'unavailable',
    window: 60,
    cumulative_series: [],
    period_attribution: [],
    total_portfolio_return_pct: null,
    total_unexplained_pct: null,
    methodology_note:
      'Arithmetic (not compounded). Sum of daily factor contributions + unexplained equals arithmetic portfolio return.',
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('FactorAttributionCard', () => {
  describe('idle / no snapshot', () => {
    it('renders prompt to import portfolio when snapshot is null', () => {
      mockRunAttributionEngine.mockResolvedValue(makeAvailableAttribution())
      render(<FactorAttributionCard snapshot={null} />)

      expect(screen.getByText(/import a portfolio/i)).toBeDefined()
      expect(mockRunAttributionEngine).not.toHaveBeenCalled()
    })
  })

  describe('loading state', () => {
    it('shows loading indicator while attribution is in flight', () => {
      // Never resolves during this test — keep the card in loading state.
      mockRunAttributionEngine.mockReturnValue(new Promise(() => {}))
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)

      expect(screen.getByText(/computing attribution/i)).toBeDefined()
    })
  })

  describe('available attribution', () => {
    beforeEach(() => {
      mockRunAttributionEngine.mockResolvedValue(makeAvailableAttribution())
    })

    it('renders the card header with "Factor Return Attribution" label', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText('Factor Return Attribution')).toBeDefined()
    })

    it('renders a Synthetic badge', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText('Synthetic')).toBeDefined()
    })

    it('exposes Synthetic badge tooltip via title attribute', async () => {
      // After US-12.2 the badge is the canonical <TrustBadge /> primitive,
      // which uses the native HTML `title` attribute (consistent with other
      // cards). The previous custom hover-tooltip span was removed.
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      const badge = screen.getByText('Synthetic')
      expect(badge.getAttribute('title')).toMatch(
        /returns are reconstructed from current holdings and historical factor proxy prices/i,
      )
    })

    it('renders factor labels from period_attribution', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText('Market')).toBeDefined()
      expect(screen.getByText('Growth')).toBeDefined()
    })

    it('renders "Unexplained / idiosyncratic" row (not "Alpha")', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText(/unexplained \/ idiosyncratic/i)).toBeDefined()
      // Ensure "alpha" does not appear anywhere in the rendered output.
      expect(screen.queryByText(/alpha/i)).toBeNull()
    })

    it('renders the Total Portfolio footer row', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText(/total portfolio \(arithmetic\)/i)).toBeDefined()
    })

    it('renders the "arithmetic (not compounded)" methodology note', async () => {
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText(/arithmetic.*not compounded/i)).toBeDefined()
    })
  })

  describe('unavailable attribution', () => {
    it('shows "Not enough history" message when status is unavailable', async () => {
      mockRunAttributionEngine.mockResolvedValue(makeUnavailableAttribution())
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText(/not enough history/i)).toBeDefined()
      // No chart data rows or factor labels should appear.
      expect(screen.queryByText('Market')).toBeNull()
    })
  })

  describe('error state', () => {
    it('shows error message when the engine call throws', async () => {
      mockRunAttributionEngine.mockRejectedValue(new Error('Attribution engine failed'))
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText(/attribution unavailable/i)).toBeDefined()
      expect(screen.getByText(/attribution engine failed/i)).toBeDefined()
    })
  })

  describe('window selector', () => {
    it('shows three window options: 20d, 60d, 252d', async () => {
      mockRunAttributionEngine.mockResolvedValue(makeAvailableAttribution())
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(screen.getByText('20d')).toBeDefined()
      expect(screen.getByText('60d')).toBeDefined()
      expect(screen.getByText('252d')).toBeDefined()
    })

    it('re-calls the adapter with window=252 when 252d is clicked', async () => {
      mockRunAttributionEngine.mockResolvedValue(makeAvailableAttribution())
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      fireEvent.click(screen.getByText('252d'))

      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(2))
      expect(mockRunAttributionEngine).toHaveBeenLastCalledWith(MINIMAL_SNAPSHOT, 252)
    })

    it('defaults to window=20', async () => {
      mockRunAttributionEngine.mockResolvedValue(makeAvailableAttribution())
      render(<FactorAttributionCard snapshot={MINIMAL_SNAPSHOT} />)
      await waitFor(() => expect(mockRunAttributionEngine).toHaveBeenCalledTimes(1))

      expect(mockRunAttributionEngine).toHaveBeenCalledWith(MINIMAL_SNAPSHOT, 20)
    })
  })
})
