import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LineChart } from 'recharts'
import { ChartShell } from './ChartShell'

afterEach(() => { cleanup() })

// ChartShell expects a single Recharts chart child. Use a tiny LineChart so
// ResponsiveContainer is happy in jsdom (the project's setup.tsx shims it).
const stubChart = <LineChart data={[]} />

describe('ChartShell', () => {
  it('renders_with_default_height', () => {
    render(<ChartShell ariaLabel="x">{stubChart}</ChartShell>)
    const region = screen.getByRole('img', { name: 'x' })
    expect(region.style.height).toBe('260px')
  })

  it('renders_with_custom_height', () => {
    render(<ChartShell ariaLabel="x" height={320}>{stubChart}</ChartShell>)
    const region = screen.getByRole('img', { name: 'x' })
    expect(region.style.height).toBe('320px')
  })

  it('passes_aria_label_to_outer_region', () => {
    render(<ChartShell ariaLabel="my chart">{stubChart}</ChartShell>)
    expect(screen.getByRole('img', { name: 'my chart' })).toBeTruthy()
  })
})
