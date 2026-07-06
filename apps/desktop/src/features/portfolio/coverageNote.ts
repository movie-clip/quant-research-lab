/**
 * coverageNote — one-line disclosure for SyntheticHistoryCoverage (US-27.7).
 *
 * The synthetic/broker history builders never fabricate a price before a
 * symbol's first quote; when that shortens the effective window or excludes
 * holdings, the affected cards must say so (methodology §Synthetic history
 * coverage rule). Returns null when there is nothing to disclose (full
 * coverage), so callers can render nothing.
 */
import type { SyntheticHistoryCoverage } from './types'

export function coverageNote(coverage: SyntheticHistoryCoverage | null | undefined): string | null {
  if (!coverage) return null
  const parts: string[] = []
  if (
    coverage.limiting_symbol &&
    coverage.effective_start_date &&
    coverage.requested_start_date &&
    coverage.effective_start_date > coverage.requested_start_date
  ) {
    parts.push(
      `History coverage starts ${coverage.effective_start_date} — limited by ${coverage.limiting_symbol}'s first available quote`,
    )
  }
  if (coverage.excluded_symbols && coverage.excluded_symbols.length > 0) {
    parts.push(`excluded (no usable price history): ${coverage.excluded_symbols.join(', ')}`)
  }
  if (parts.length === 0) return null
  return parts.join('; ')
}
