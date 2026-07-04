import { cleanup, render, screen, waitFor } from '@testing-library/react'
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

  // US-27.1: the outer region renders immediately, but the chart content
  // itself is deferred by one animation frame so ResponsiveContainer's
  // mount-time measurement doesn't race a same-commit DOM insertion of
  // other new cards (the root cause of the "blank chart until reload" bug).
  it('defers_chart_content_by_one_frame', () => {
    render(<ChartShell ariaLabel="deferred">{stubChart}</ChartShell>)
    const region = screen.getByRole('img', { name: 'deferred' })
    expect(region.querySelector('svg, .recharts-responsive-container')).toBeNull()
  })

  it('renders_chart_content_after_the_deferred_frame', async () => {
    render(<ChartShell ariaLabel="deferred-2">{stubChart}</ChartShell>)
    const region = screen.getByRole('img', { name: 'deferred-2' })
    await waitFor(() => {
      expect(region.children.length).toBeGreaterThan(0)
    })
  })
})
