import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { admissionCheck, constituentOf, esppAdmission, ibAdmission, ibPlusEsppAdmission, rolledUpAdmission } from '../../test/combinedImportFixtures'
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

describe('ImportAdmissionReviewCard roll-up (US-46.3 AC 1, 8, 10)', () => {
  function badgesIn(scope: HTMLElement) {
    return {
      decision: within(scope).getByText(/^Decision: /).textContent,
      trust: within(scope).getByText(/^Trust: /).textContent,
    }
  }

  function cardHeader() {
    return screen.getByText('Import Admission Review').parentElement as HTMLElement
  }

  it('shows the portfolio label as degraded / degraded for IB2026 + ESPP2026, not admitted / verified', () => {
    render(<ImportAdmissionReviewCard summary={ibPlusEsppAdmission()} />)

    const header = cardHeader()
    expect(within(header).getByText('Decision: Degraded')).toBeTruthy()
    expect(within(header).getByText('Trust: Degraded')).toBeTruthy()
    expect(within(header).queryByText(/Admitted|Verified/)).toBeNull()
  })

  it('renders the rule and the combined-snapshot labels the engine delivered', () => {
    render(<ImportAdmissionReviewCard summary={ibPlusEsppAdmission()} />)

    expect(screen.getByText(/weakest of each statement's own admission/i)).toBeTruthy()
    const combined = screen.getByText('Combined snapshot check').parentElement as HTMLElement
    expect(badgesIn(combined)).toEqual({ decision: 'Decision: Degraded', trust: 'Trust: Degraded' })
  })

  it('renders each constituent statement with its own labels and checks, alongside the portfolio label (AC 8)', () => {
    render(<ImportAdmissionReviewCard summary={ibPlusEsppAdmission()} />)

    const ib = screen.getByRole('group', { name: /IB2026\.csv/ })
    const espp = screen.getByRole('group', { name: /ESPP2026\.pdf/ })
    expect(badgesIn(ib)).toEqual({ decision: 'Decision: Degraded', trust: 'Trust: Degraded' })
    expect(badgesIn(espp)).toEqual({ decision: 'Decision: Admitted', trust: 'Trust: Verified' })
    expect(within(ib).getByText(/Open positions lack imported instrument identity for: SBIO\./)).toBeTruthy()
    expect(within(espp).queryByText(/Open positions lack imported instrument identity/)).toBeNull()
  })

  it('keeps the combined snapshot checks separate from the constituent checks', () => {
    render(<ImportAdmissionReviewCard summary={ibPlusEsppAdmission()} />)

    expect(screen.getByText('Combined snapshot checks')).toBeTruthy()
    const combinedCheck = screen.getByText(/Combined snapshot NAV comparability could not be verified\./)
    expect(combinedCheck.closest('[role="group"]')).toBeNull()
  })

  it('marks a carried constituent as an earlier review, distinct from a statement', () => {
    const summary = rolledUpAdmission({
      topLabel: { decision: 'degraded', trustLevel: 'degraded' },
      combinedSnapshotLabel: { decision: 'admitted', trustLevel: 'verified' },
      constituents: [constituentOf('statement', esppAdmission()), constituentOf('carried', ibAdmission())],
      sourceNames: ['ESPP2026.pdf', 'IB2026.csv'],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)

    const carried = screen.getByRole('group', { name: /Earlier review \(carried\).*IB2026\.csv/ })
    expect(badgesIn(carried)).toEqual({ decision: 'Decision: Degraded', trust: 'Trust: Degraded' })
    expect(screen.getByRole('group', { name: /^Statement 1: ESPP2026\.pdf/ })).toBeTruthy()
  })

  it('renders the engine label verbatim and never lowers it to match the constituents', () => {
    // Every constituent and the combined snapshot say admitted / verified, the engine's top label says
    // withheld. The card must show what it was given: ranking is the engine's job.
    const summary = rolledUpAdmission({
      topLabel: { decision: 'withheld', trustLevel: 'withheld' },
      combinedSnapshotLabel: { decision: 'admitted', trustLevel: 'verified' },
      constituents: [constituentOf('statement', esppAdmission())],
      sourceNames: ['ESPP2026.pdf'],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)

    expect(within(cardHeader()).getByText('Decision: Withheld')).toBeTruthy()
    expect(within(cardHeader()).getByText('Trust: Withheld')).toBeTruthy()
  })

  it('renders the engine label verbatim and never raises it to match the constituents', () => {
    const summary = rolledUpAdmission({
      topLabel: { decision: 'admitted', trustLevel: 'verified' },
      combinedSnapshotLabel: { decision: 'admitted', trustLevel: 'verified' },
      constituents: [constituentOf('statement', ibAdmission())],
      sourceNames: ['IB2026.csv'],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)

    expect(within(cardHeader()).getByText('Decision: Admitted')).toBeTruthy()
    expect(within(cardHeader()).getByText('Trust: Verified')).toBeTruthy()
  })

  it('keeps withheld and unavailable trust distinct in the constituent rows', () => {
    const withheld = { ...ibAdmission(), decision: 'withheld' as const, trust_level: 'withheld' as const }
    const unavailable = { ...esppAdmission(), decision: 'withheld' as const, trust_level: 'unavailable' as const }
    const summary = rolledUpAdmission({
      topLabel: { decision: 'withheld', trustLevel: 'unavailable' },
      combinedSnapshotLabel: { decision: 'withheld', trustLevel: 'withheld' },
      constituents: [constituentOf('statement', withheld), constituentOf('statement', unavailable)],
      sourceNames: ['IB2026.csv', 'ESPP2026.pdf'],
      combinedChecks: [admissionCheck('nav_market_value_comparability', 'unavailable')],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)

    expect(badgesIn(screen.getByRole('group', { name: /IB2026\.csv/ })).trust).toBe('Trust: Withheld')
    expect(badgesIn(screen.getByRole('group', { name: /ESPP2026\.pdf/ })).trust).toBe('Trust: Unavailable')
  })

  it('renders a single statement exactly as before when there is no roll-up (AC 10)', () => {
    render(<ImportAdmissionReviewCard summary={ibAdmission()} />)

    expect(screen.queryByRole('group')).toBeNull()
    expect(screen.queryByText(/weakest of/i)).toBeNull()
    expect(screen.queryByText('Combined snapshot checks')).toBeNull()
  })

  it('treats a null roll-up like an absent one (ESPP2026 alone stays admitted / verified)', () => {
    render(<ImportAdmissionReviewCard summary={{ ...esppAdmission(), rollup: null }} />)

    expect(screen.queryByRole('group')).toBeNull()
    expect(screen.getByText('Decision: Admitted')).toBeTruthy()
    expect(screen.getByText('Trust: Verified')).toBeTruthy()
  })

  it('shows an empty state for a constituent with no recorded checks, never an all-clear', () => {
    const noChecks = { ...esppAdmission(), checks: [] }
    const summary = rolledUpAdmission({
      topLabel: { decision: 'degraded', trustLevel: 'degraded' },
      combinedSnapshotLabel: { decision: 'degraded', trustLevel: 'degraded' },
      constituents: [constituentOf('statement', noChecks)],
      sourceNames: ['ESPP2026.pdf'],
    })
    render(<ImportAdmissionReviewCard summary={summary} />)

    const group = screen.getByRole('group', { name: /ESPP2026\.pdf/ })
    expect(within(group).getByText('No admission checks were recorded for this statement.')).toBeTruthy()
    expect(within(group).queryByText(/Pass/)).toBeNull()
  })
})
