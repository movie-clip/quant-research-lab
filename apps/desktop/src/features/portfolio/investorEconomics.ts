import type { InvestorEconomicsStatus } from './types'

export function investorEconomicsBaseReason(status: InvestorEconomicsStatus | null | undefined) {
  if (status?.status !== 'withheld') return null
  if (status.reason === 'withheld_unverified_total_return_equivalence') {
    return 'Investor-economics outputs are withheld because total-return equivalence is unverified.'
  }
  return null
}
