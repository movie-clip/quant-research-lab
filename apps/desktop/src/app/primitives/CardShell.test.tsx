import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { CardShell } from './CardShell'

afterEach(() => { cleanup() })

describe('CardShell', () => {
  it('renders_title_in_panel_label', () => {
    render(<CardShell title="Rolling Correlation">body</CardShell>)
    const label = screen.getByText('Rolling Correlation')
    expect(label.className).toContain('panel-label')
  })

  it('renders_badge_slot_when_provided', () => {
    render(
      <CardShell title="X" badge={<span data-testid="my-badge">B</span>}>
        body
      </CardShell>,
    )
    expect(screen.getByTestId('my-badge')).toBeTruthy()
  })

  it('renders_actions_slot_when_provided', () => {
    render(
      <CardShell title="X" actions={<button type="button">Click me</button>}>
        body
      </CardShell>,
    )
    expect(screen.getByRole('button', { name: 'Click me' })).toBeTruthy()
  })

  it('omits_badge_slot_when_not_provided', () => {
    render(<CardShell title="X">body</CardShell>)
    // No badge → no extra <span> after the .panel-label inside the title block
    expect(screen.queryByTestId('my-badge')).toBeNull()
  })

  it('renders_children_in_body', () => {
    render(
      <CardShell title="X">
        <div data-testid="body-child">child content</div>
      </CardShell>,
    )
    expect(screen.getByTestId('body-child')).toBeTruthy()
  })
})
