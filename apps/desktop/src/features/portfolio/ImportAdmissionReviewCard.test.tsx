import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ImportAdmissionSummaryV1 } from './types'
import { ImportAdmissionReviewCard } from './ImportAdmissionReviewCard'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

type Check = ImportAdmissionSummaryV1['checks'][number]

function check(overrides: Partial<Check> & Pick<Check, 'check_id' | 'status'>): Check {
  return {
    severity: 'info',
    trust_impact: 'none',
    message: `${overrides.check_id} message`,
    affected_fields: [],
    observed: null,
    comparison: null,
    delta: null,
    currency: null,
    ...overrides,
  }
}

function makeSummary(overrides?: Partial<ImportAdmissionSummaryV1>): ImportAdmissionSummaryV1 {
  return {
    schema_version: 'import_admission_summary_v1',
    decision: 'admitted',
    trust_level: 'verified',
    checks: [check({ check_id: 'residual_cash_comparability', status: 'pass' })],
    provenance: {
      importer: 'interactive_brokers',
      statement_ids: [],
      source_names: [],
      generated_at: '2026-06-12T00:00:00Z',
      tolerance_policy: 'absolute_currency_delta_lte_0.01_same_currency_only',
    },
    ...overrides,
  }
}

describe('ImportAdmissionReviewCard', () => {
  it('renders the decision and trust-level badges', () => {
    render(<ImportAdmissionReviewCard summary={makeSummary({ decision: 'degraded', trust_level: 'degraded' })} />)
    expect(screen.getByText(/Decision: Degraded/i)).toBeTruthy()
    expect(screen.getByText(/Trust: Degraded/i)).toBeTruthy()
  })

  it('renders one row per check', () => {
    const summary = makeSummary({
      checks: [
        check({ check_id: 'residual_cash_comparability', status: 'pass' }),
        check({ check_id: 'nav_market_value_comparability', status: 'fail' }),
        check({ check_id: 'instrument_isin_registry_consistency', status: 'warn' }),
      ],
    })
    const { container } = render(<ImportAdmissionReviewCard summary={summary} />)
    expect(container.querySelectorAll('li').length).toBe(3)
  })

  it('renders observed/comparison/delta evidence for a fail check', () => {
    const summary = makeSummary({
      decision: 'withheld',
      trust_level: 'withheld',
      checks: [
        check({
          check_id: 'nav_market_value_comparability',
          status: 'fail',
          message: 'NAV does not reconcile.',
          observed: { label: 'parsed_nav', value: 300 },
          comparison: { label: 'statement_nav', value: 325 },
          delta: -25,
          currency: 'USD',
        }),
      ],
    })
    const { container } = render(<ImportAdmissionReviewCard summary={summary} />)
    const text = container.textContent ?? ''
    expect(text).toContain('parsed_nav: 300.00')
    expect(text).toContain('statement_nav: 325.00')
    expect(text).toContain('-25.00 USD')
    expect(text).toContain('NAV does not reconcile.')
  })

  it('renders the message and affected fields for a warn check', () => {
    const summary = makeSummary({
      decision: 'degraded',
      trust_level: 'degraded',
      checks: [
        check({
          check_id: 'instrument_isin_registry_consistency',
          status: 'warn',
          message: 'ISIN mismatch for VUAA.',
          affected_fields: ['instruments.symbol', 'instruments.isin'],
        }),
      ],
    })
    const { container } = render(<ImportAdmissionReviewCard summary={summary} />)
    const text = container.textContent ?? ''
    expect(text).toContain('ISIN mismatch for VUAA.')
    expect(text).toContain('Fields: instruments.symbol, instruments.isin')
    expect(screen.getByText(/⚠ Warn/)).toBeTruthy()
  })

  it('renders an unavailable empty state when there is no summary (no fabricated all-clear)', () => {
    const { container } = render(<ImportAdmissionReviewCard summary={null} />)
    expect(screen.getByText(/Import Admission Review unavailable/i)).toBeTruthy()
    // never claims everything passed / admitted
    expect(container.textContent).not.toMatch(/admitted|pass|verified/i)
  })

  it('labels each status with text, not color alone', () => {
    const summary = makeSummary({
      checks: [
        check({ check_id: 'a_pass', status: 'pass' }),
        check({ check_id: 'b_warn', status: 'warn' }),
        check({ check_id: 'c_fail', status: 'fail' }),
        check({ check_id: 'd_unavailable', status: 'unavailable' }),
      ],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)
    expect(screen.getByText(/✓ Pass/)).toBeTruthy()
    expect(screen.getByText(/⚠ Warn/)).toBeTruthy()
    expect(screen.getByText(/✗ Fail/)).toBeTruthy()
    expect(screen.getByText(/— Unavailable/)).toBeTruthy()
  })

  it('makes no network call on render', () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    render(<ImportAdmissionReviewCard summary={makeSummary()} />)
    expect(fetchSpy).not.toHaveBeenCalled()
    vi.unstubAllGlobals()
  })
})
