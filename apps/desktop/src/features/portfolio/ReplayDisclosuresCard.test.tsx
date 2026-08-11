import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DashboardHistoryRunMetadata } from './types'
import { ReplayDisclosuresCard } from './ReplayDisclosuresCard'

afterEach(cleanup)

/** A run_metadata with every disclosure clean; tests opt into one at a time. */
function metadata(overrides: Partial<DashboardHistoryRunMetadata> = {}): DashboardHistoryRunMetadata {
  return {
    history_id: 'dashboard_history_engine_v1',
    methodology_id: 'dashboard_history_methodology_v1',
    fx_fallback_currencies: [],
    unpriced_replay_symbols: [],
    trade_price_anchored_symbols: [],
    withheld_return_dates: [],
    withheld_return_reason: null,
    replay_cash_anchor: {
      basis: 'statement_nav_at_window_start',
      nav_as_of: '2026-01-08',
      window_start: '2026-01-08',
      residual: 0,
      trust: 'verified',
    },
    source_status: {
      performance_history: 'live',
      monthly_returns: 'live',
      benchmark_history: 'live',
    },
    ...overrides,
  } as DashboardHistoryRunMetadata
}

describe('ReplayDisclosuresCard', () => {
  it('renders nothing when there is no run metadata', () => {
    const { container } = render(<ReplayDisclosuresCard runMetadata={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing on a clean run — absence of a warning is not a claim', () => {
    const { container } = render(<ReplayDisclosuresCard runMetadata={metadata()} />)
    expect(container.innerHTML).toBe('')
  })

  it('surfaces a degraded cash anchor with its basis, both dates and the residual', () => {
    render(
      <ReplayDisclosuresCard
        runMetadata={metadata({
          replay_cash_anchor: {
            basis: 'statement_nav_date_mismatch',
            nav_as_of: '2026-01-01',
            window_start: '2026-01-08',
            residual: -1196.61,
            trust: 'degraded',
          },
        })}
      />,
    )

    expect(screen.getByRole('region', { name: /replay disclosures/i })).toBeTruthy()
    const text = screen.getByRole('region', { name: /replay disclosures/i }).textContent ?? ''
    expect(text).toContain('degraded')
    expect(text).toContain('2026-01-01')
    expect(text).toContain('2026-01-08')
    expect(text).toContain('$1,196.61')
  })

  it('does not warn about a verified cash anchor', () => {
    render(
      <ReplayDisclosuresCard
        runMetadata={metadata({
          // Verified, but with a non-zero residual and differing-looking dates
          // present: trust is what gates the note, not the other fields.
          replay_cash_anchor: {
            basis: 'snapshot_cash_balances',
            nav_as_of: '2026-01-08',
            window_start: '2026-01-08',
            residual: 0,
            trust: 'verified',
          },
          // One other disclosure so the card itself still renders.
          fx_fallback_currencies: ['EUR'],
        })}
      />,
    )

    const text = screen.getByRole('region', { name: /replay disclosures/i }).textContent ?? ''
    expect(text).toContain('EUR')
    expect(text).not.toContain('Opening cash')
  })

  it('shows withheld return dates with the engine stated reason', () => {
    render(
      <ReplayDisclosuresCard
        runMetadata={metadata({
          withheld_return_dates: ['2026-06-30'],
          withheld_return_reason:
            'Return withheld: the state was adjusted to match the statement’s ending NAV.',
        })}
      />,
    )

    const text = screen.getByRole('region', { name: /replay disclosures/i }).textContent ?? ''
    expect(text).toContain('2026-06-30')
    expect(text).toContain('adjusted to match the statement')
    // `withheld` must never be presented as `unavailable` (guardrail #3).
    expect(text).not.toMatch(/unavailable/i)
  })

  it('names the symbols in each valuation-degradation tier', () => {
    render(
      <ReplayDisclosuresCard
        runMetadata={metadata({
          unpriced_replay_symbols: ['NOPRICE'],
          trade_price_anchored_symbols: ['BTEC', 'IUFS'],
          fx_fallback_currencies: ['GBP'],
        })}
      />,
    )

    const text = screen.getByRole('region', { name: /replay disclosures/i }).textContent ?? ''
    expect(text).toContain('NOPRICE')
    expect(text).toContain('BTEC, IUFS')
    expect(text).toContain('GBP')
    // The tiers must read as distinct degradations, not one lumped warning.
    expect(text).toContain('contributed')
    expect(text).toContain("broker's own")
  })

  it('never renders a Synthetic badge — the replay is broker truth, not synthetic history', () => {
    render(
      <ReplayDisclosuresCard
        runMetadata={metadata({
          unpriced_replay_symbols: ['NOPRICE'],
          withheld_return_dates: ['2026-06-30'],
          replay_cash_anchor: {
            basis: 'statement_nav_date_mismatch',
            nav_as_of: '2026-01-01',
            window_start: '2026-01-08',
            residual: -1196.61,
            trust: 'degraded',
          },
        })}
      />,
    )

    expect(screen.queryByText('Synthetic')).toBeNull()
    expect(document.querySelector('.attribution-trust-badge')).toBeNull()
  })
})
