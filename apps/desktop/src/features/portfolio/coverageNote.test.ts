import { describe, expect, it } from 'vitest'

import { coverageNote } from './coverageNote'

describe('coverageNote (US-27.7)', () => {
  it('returns null for full coverage / absent disclosure', () => {
    expect(coverageNote(null)).toBeNull()
    expect(coverageNote(undefined)).toBeNull()
    expect(
      coverageNote({
        requested_start_date: '2025-01-02',
        effective_start_date: '2025-01-02',
        limiting_symbol: null,
        excluded_symbols: [],
      }),
    ).toBeNull()
  })

  it('names the limiting symbol when the window is truncated', () => {
    const note = coverageNote({
      requested_start_date: '2025-01-02',
      effective_start_date: '2025-03-01',
      limiting_symbol: 'BBB',
      excluded_symbols: [],
    })
    expect(note).toBe("History coverage starts 2025-03-01 — limited by BBB's first available quote")
  })

  it('lists excluded holdings, combined with truncation when both apply', () => {
    const note = coverageNote({
      requested_start_date: '2025-01-02',
      effective_start_date: '2025-03-01',
      limiting_symbol: 'BBB',
      excluded_symbols: ['CCC', 'DDD'],
    })
    expect(note).toContain('limited by BBB')
    expect(note).toContain('excluded (no usable price history): CCC, DDD')
  })
})
