import { describe, expect, it } from 'vitest'

import { sortTooltipPayloadRows } from './RollingFactorLoadingsCard'

describe('RollingFactorLoadingsCard', () => {
  it('sorts rolling factor tooltip rows by highest visible value first', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'market', value: 1.08 },
        { dataKey: 'technology', value: 0.22 },
        { dataKey: 'growth', value: 0.31 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })

  it('breaks equal tooltip values with chart line order', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'technology', value: 0.31 },
        { dataKey: 'growth', value: 0.31 },
        { dataKey: 'market', value: 1.08 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })
})
