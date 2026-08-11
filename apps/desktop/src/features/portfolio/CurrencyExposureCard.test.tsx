import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { CurrencyExposureSummary } from './types'
import { CurrencyExposureCard } from './CurrencyExposureCard'

afterEach(cleanup)

function exposure(overrides: Partial<CurrencyExposureSummary> = {}): CurrencyExposureSummary {
  return {
    base_currency: 'USD',
    total_base_market_value: 61238.53,
    weights: [
      { currency: 'USD', market_value: 48000, weight: 0.7838 },
      { currency: 'EUR', market_value: 10238.53, weight: 0.1672 },
      { currency: 'GBP', market_value: 3000, weight: 0.049 },
    ],
    non_base_weight: 0.2162,
    ...overrides,
  }
}

function cardText(): string {
  return screen.getByRole('region', { name: /currency exposure/i }).textContent ?? ''
}

describe('CurrencyExposureCard', () => {
  it('renders nothing when there is no currency exposure', () => {
    const { container } = render(<CurrencyExposureCard exposure={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('lists each currency in weight order with the base currency marked', () => {
    render(<CurrencyExposureCard exposure={exposure()} />)

    const text = cardText()
    expect(text).toContain('USD')
    expect(text).toContain('(base)')
    expect(text).toContain('EUR')
    expect(text).toContain('GBP')
    // Engine order is preserved (weight desc) — the component does not re-sort.
    expect(text.indexOf('USD')).toBeLessThan(text.indexOf('EUR'))
    expect(text.indexOf('EUR')).toBeLessThan(text.indexOf('GBP'))
  })

  it('shows the non-base total — the headline the researcher came for', () => {
    render(<CurrencyExposureCard exposure={exposure()} />)
    expect(cardText()).toContain('21.62%')
  })

  it('renders an em dash, never 0, when there is no base currency', () => {
    render(
      <CurrencyExposureCard
        exposure={exposure({ base_currency: null, non_base_weight: null })}
      />,
    )

    const text = cardText()
    expect(text).toContain('—')
    expect(text).toContain('no baseline')
    // 0% would read as "no currency risk", which the data does not support.
    expect(text).not.toContain('0.00%')
  })

  it('discloses static-rate and unconverted currencies', () => {
    render(
      <CurrencyExposureCard
        exposure={exposure()}
        fxStaticRateCurrencies={['EUR']}
        fxFallbackCurrencies={['GBP']}
      />,
    )

    const text = cardText()
    expect(text).toContain('period-end')
    expect(text).toContain('No FX rate available for GBP')
    expect(text).toContain('least reliable')
  })

  it('renders no Synthetic badge — snapshot analytics, not synthetic history', () => {
    render(<CurrencyExposureCard exposure={exposure()} />)

    expect(screen.queryByText('Synthetic')).toBeNull()
    expect(document.querySelector('.attribution-trust-badge')).toBeNull()
  })
})
