import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CurrencyRiskResult, ImportedSnapshot } from './types'
import { CurrencyRiskCard } from './CurrencyRiskCard'
import * as adapter from './portfolioAnalysisAdapter'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const snapshot = { statement: { base_currency: 'USD' }, positions: [] } as unknown as ImportedSnapshot

function result(overrides: Partial<CurrencyRiskResult> = {}): CurrencyRiskResult {
  return {
    trust: 'synthetic',
    window_days: 60,
    observations: 58,
    local_variance_share: 0.86,
    currency_variance_share: 0.13,
    interaction_variance_share: 0.01,
    local_standalone_vol_pct: 14.2,
    currency_standalone_vol_pct: 6.4,
    local_fx_correlation: 0.21,
    per_currency: [
      { currency: 'EUR', base_weight: 0.16, contribution: 0.09 },
      { currency: 'GBP', base_weight: 0.05, contribution: 0.04 },
    ],
    excluded_symbols: [],
    excluded_weight: 0,
    ...overrides,
  }
}

function mockRun(payload: CurrencyRiskResult) {
  return vi.spyOn(adapter, 'runCurrencyRiskEngine').mockResolvedValue(payload)
}

function cardText(): string {
  return screen.getByRole('region', { name: /currency risk contribution/i }).textContent ?? ''
}

describe('CurrencyRiskCard', () => {
  it('renders the three shares and the stat row', async () => {
    mockRun(result())
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(cardText()).toContain('86.0%'))
    const text = cardText()
    expect(text).toContain('Securities')
    expect(text).toContain('Currency')
    expect(text).toContain('Interaction')
    expect(text).toContain('13.0%')
    expect(text).toContain('1.0%')
    expect(text).toContain('6.40%')
    expect(text).toContain('0.21')
  })

  it('carries a Synthetic badge — current holdings applied to historical prices', async () => {
    mockRun(result())
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('Synthetic')).toBeTruthy())
  })

  it('renders a negative share as negative, with its explanation', async () => {
    mockRun(result({ currency_variance_share: -0.08, local_variance_share: 1.07 }))
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(cardText()).toContain('-8.0%'))
    // Never clamped to zero, and the reader is told what it means.
    expect(cardText()).toContain('against')
    expect(cardText()).not.toContain('0.0%')
  })

  it('renders an em dash, never 0, for null statistics', async () => {
    mockRun(result({ local_fx_correlation: null, currency_standalone_vol_pct: null }))
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(cardText()).toContain('—'))
  })

  it('shows the engine reason when the decomposition is unavailable', async () => {
    mockRun(
      result({
        trust: 'unavailable',
        local_variance_share: null,
        currency_variance_share: null,
        interaction_variance_share: null,
        note: 'Needs at least 20 overlapping days of price and FX history; found 7.',
      }),
    )
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(cardText()).toContain('found 7'))
    // The share rows must not render at all in the unavailable state — a
    // partial card would imply a decomposition the engine refused to make.
    const text = cardText()
    expect(text).not.toContain('Securities vol')
    expect(text).not.toContain('sum to 100%')
    expect(screen.getByText('Unavailable')).toBeTruthy()
  })

  it('names excluded holdings and their weight', async () => {
    mockRun(result({ excluded_symbols: ['LQQ', 'BTEC'], excluded_weight: 0.07 }))
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(cardText()).toContain('LQQ, BTEC'))
    const text = cardText().replace(/\s+/g, ' ')
    expect(text).toContain('7.0%')
    // The disclosure must say what the exclusion COSTS the reader, not merely
    // list symbols — an excluded holding's currency risk is simply absent.
    expect(text).toContain('currency risk is not represented')
  })

  it('re-fetches when the window changes', async () => {
    const spy = mockRun(result())
    render(<CurrencyRiskCard snapshot={snapshot} />)

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy).toHaveBeenLastCalledWith(snapshot, 60)

    fireEvent.click(screen.getByRole('button', { name: /252d/i }))

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2))
    expect(spy).toHaveBeenLastCalledWith(snapshot, 252)
  })
})
