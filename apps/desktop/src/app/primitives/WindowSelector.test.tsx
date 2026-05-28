import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WindowSelector } from './WindowSelector'

afterEach(() => { cleanup() })

describe('WindowSelector', () => {
  it('renders_one_button_per_option', () => {
    render(<WindowSelector options={[20, 60, 252] as const} value={60} onChange={() => undefined} />)
    expect(screen.getAllByRole('button').length).toBe(3)
  })

  it('marks_active_option_with_aria_pressed', () => {
    render(<WindowSelector options={[20, 60, 252] as const} value={60} onChange={() => undefined} />)
    const buttons = screen.getAllByRole('button')
    const active = buttons.find((b) => b.getAttribute('aria-pressed') === 'true')
    const inactive = buttons.filter((b) => b.getAttribute('aria-pressed') === 'false')
    expect(active?.textContent).toBe('60')
    expect(inactive.length).toBe(2)
  })

  it('click_triggers_onChange_with_option_value', () => {
    const onChange = vi.fn()
    render(<WindowSelector options={[20, 60, 252] as const} value={60} onChange={onChange} />)
    fireEvent.click(screen.getAllByRole('button')[0]!)  // 20d button
    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange).toHaveBeenCalledWith(20)
  })

  it('applies_default_labelFn_when_omitted', () => {
    render(<WindowSelector options={[20, 60, 252] as const} value={60} onChange={() => undefined} />)
    expect(screen.getByText('20')).toBeTruthy()
    expect(screen.getByText('60')).toBeTruthy()
    expect(screen.getByText('252')).toBeTruthy()
  })

  it('applies_custom_labelFn_when_provided', () => {
    render(
      <WindowSelector
        options={[20, 60, 252] as const}
        value={60}
        onChange={() => undefined}
        labelFn={(w) => `${w}d`}
      />,
    )
    expect(screen.getByText('20d')).toBeTruthy()
    expect(screen.getByText('60d')).toBeTruthy()
    expect(screen.getByText('252d')).toBeTruthy()
  })
})
