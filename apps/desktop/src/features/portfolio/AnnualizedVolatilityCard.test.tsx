import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { AnnualizedVolatilityCard } from './AnnualizedVolatilityCard'
import type { RiskTabAnnualizedVolatility } from './types'

afterEach(cleanup)

/** A percentage figure rendered to displayed precision, e.g. `18.27%`. */
const PCT_FIGURE = /\d+\.\d{2}%/

function synthetic(overrides: Partial<RiskTabAnnualizedVolatility> = {}): RiskTabAnnualizedVolatility {
  return {
    annualized_volatility_pct: 18.27,
    trust: 'synthetic',
    observations: 180,
    minimum_observations: 60,
    ...overrides,
  }
}

function withheld(overrides: Partial<RiskTabAnnualizedVolatility> = {}): RiskTabAnnualizedVolatility {
  return {
    annualized_volatility_pct: null,
    trust: 'withheld',
    observations: 12,
    minimum_observations: 60,
    ...overrides,
  }
}

function unavailable(overrides: Partial<RiskTabAnnualizedVolatility> = {}): RiskTabAnnualizedVolatility {
  return {
    annualized_volatility_pct: null,
    trust: 'unavailable',
    observations: 0,
    minimum_observations: 60,
    ...overrides,
  }
}

describe('AnnualizedVolatilityCard', () => {
  describe('synthetic (published)', () => {
    it('renders the figure to displayed precision with a Synthetic trust badge', () => {
      const { container } = render(<AnnualizedVolatilityCard volatility={synthetic()} />)

      expect(screen.getByText('18.27%')).toBeTruthy()
      // AC 3: the published figure carries the Synthetic treatment.
      expect(screen.getByText('Synthetic')).toBeTruthy()
      expect(container.querySelector('.attribution-trust-badge')?.textContent).toBe('Synthetic')
    })

    it('formats to two decimals even when the wire value has more precision', () => {
      render(<AnnualizedVolatilityCard volatility={synthetic({ annualized_volatility_pct: 13.336666 })} />)

      expect(screen.getByText('13.34%')).toBeTruthy()
    })

    it('keeps a genuinely computed zero as 0.00% (never withheld)', () => {
      // Human ruling: zero-variance at N >= floor publishes 0.00%.
      render(<AnnualizedVolatilityCard volatility={synthetic({ annualized_volatility_pct: 0 })} />)

      expect(screen.getByText('0.00%')).toBeTruthy()
      expect(screen.getByText('Synthetic')).toBeTruthy()
    })

    it('makes a methodology reference reachable from the surface (AC 12)', () => {
      const { container } = render(<AnnualizedVolatilityCard volatility={synthetic({ observations: 180 })} />)

      const helper = container.querySelector('.helper')?.textContent ?? ''
      // Points at the documented formula section...
      expect(helper).toContain('Annualized realized volatility')
      // ...and names the publication floor.
      expect(helper).toContain('60')
      expect(helper).toContain('180')
      // The trust badge's tooltip also carries the formula (a second reach).
      expect(container.querySelector('.attribution-trust-badge')?.getAttribute('title')).toMatch(
        /standard deviation/i,
      )
    })
  })

  describe('withheld (1..59 observations)', () => {
    it('shows a withheld empty state that names the 60-day requirement and "N of 60"', () => {
      render(<AnnualizedVolatilityCard volatility={withheld({ observations: 12 })} />)

      expect(screen.getByText('Annualized volatility withheld')).toBeTruthy()
      // AC 8: the "{N} of {min}" copy so a researcher reads a deliberate threshold.
      expect(screen.getByText(/12 of 60 paired/)).toBeTruthy()
      expect(screen.getByText(/fewer than 60 paired trading days/)).toBeTruthy()
      expect(screen.getByText(/Dashboard shows an unfloored estimate/)).toBeTruthy()
    })

    it('renders no number, no zero, no dash and no trust badge (AC 7, AC 11)', () => {
      const { container } = render(<AnnualizedVolatilityCard volatility={withheld()} />)

      expect(container.textContent).not.toMatch(PCT_FIGURE)
      expect(screen.queryByText('0.00%')).toBeNull()
      expect(container.textContent).not.toContain('—')
      expect(screen.queryByText('Synthetic')).toBeNull()
      expect(container.querySelector('.attribution-trust-badge')).toBeNull()
      // The published-state stat row is absent entirely.
      expect(screen.queryByText('Portfolio volatility (annualized)')).toBeNull()
    })
  })

  describe('unavailable (0 observations)', () => {
    it('shows an unavailable empty state with copy distinct from withheld (AC 10)', () => {
      render(<AnnualizedVolatilityCard volatility={unavailable()} />)

      expect(screen.getByText('Annualized volatility unavailable')).toBeTruthy()
      expect(screen.getByText(/No paired portfolio and benchmark return history/)).toBeTruthy()
      // Never collapsed to / rendered as the withheld state.
      expect(screen.queryByText('Annualized volatility withheld')).toBeNull()
      expect(screen.queryByText(/fewer than 60 paired trading days/)).toBeNull()
    })

    it('renders no number and no trust badge', () => {
      const { container } = render(<AnnualizedVolatilityCard volatility={unavailable()} />)

      expect(container.textContent).not.toMatch(PCT_FIGURE)
      expect(container.textContent).not.toContain('—')
      expect(container.querySelector('.attribution-trust-badge')).toBeNull()
    })
  })

  describe('withheld vs unavailable are visibly distinct (AC 10)', () => {
    it('renders different titles and different detail copy', () => {
      const { container: w } = render(<AnnualizedVolatilityCard volatility={withheld()} />)
      const withheldText = w.textContent ?? ''
      cleanup()
      const { container: u } = render(<AnnualizedVolatilityCard volatility={unavailable()} />)
      const unavailableText = u.textContent ?? ''

      expect(withheldText).not.toBe(unavailableText)
      expect(withheldText).toContain('withheld')
      expect(unavailableText).toContain('unavailable')
    })
  })

  describe('loading (null prop)', () => {
    it('renders a LoadingState while the diagnostics fetch is in flight', () => {
      const { container } = render(<AnnualizedVolatilityCard volatility={null} />)

      expect(screen.getByText('Computing annualized volatility…')).toBeTruthy()
      expect(container.querySelector('.attribution-trust-badge')).toBeNull()
      expect(container.textContent).not.toMatch(PCT_FIGURE)
    })
  })
})
