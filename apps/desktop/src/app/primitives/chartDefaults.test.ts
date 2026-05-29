import { describe, expect, it } from 'vitest'
import {
  defaultAxisTickStyle,
  defaultChartGrid,
  defaultMinTickGap,
  defaultTooltipContentStyle,
} from './chartDefaults'

describe('chartDefaults', () => {
  it('defaults_export_token_strings', () => {
    // Catches a regression where someone hard-codes a hex value
    expect(defaultChartGrid.stroke).toBe('var(--color-border-subtle)')
    expect(defaultAxisTickStyle.fontSize).toBe('var(--font-chart-tick)')
    expect(defaultAxisTickStyle.fill).toBe('var(--color-text-muted)')
  })

  it('defaultMinTickGap_is_40', () => {
    expect(defaultMinTickGap).toBe(40)
  })

  it('defaultTooltipContentStyle_uses_tokens', () => {
    // Every property value must reference a CSS variable, not a hex / px literal.
    for (const [key, value] of Object.entries(defaultTooltipContentStyle)) {
      expect(value.startsWith('var(--'), `${key} should start with var(--`).toBe(true)
    }
  })
})
