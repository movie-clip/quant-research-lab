import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { GenericRankingRequestForm } from './GenericRankingRequestForm'
import { SCORE_CONFIG_PRESETS, SCORE_CONFIG_PRESET_LABELS } from './scoreConfigPresets'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('GenericRankingRequestForm', () => {
  it('shows a validation error when submitting with empty symbols in custom_list mode', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    // custom_list is the default universe kind; symbols textarea should be visible
    expect(screen.getByText('Symbols (comma-separated)')).toBeTruthy()

    // Clear the symbols field (it's empty by default) and click Run Ranking
    fireEvent.click(screen.getByText('Run Ranking'))

    expect(screen.getByText('Validation error')).toBeTruthy()
    expect(screen.getByText('At least one symbol is required for this universe kind.')).toBeTruthy()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows a validation error when submitting with whitespace-only symbols', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    const textarea = screen.getByPlaceholderText('e.g. AAPL, MSFT, GOOGL')
    fireEvent.change(textarea, { target: { value: '  ,  ,  ' } })
    fireEvent.click(screen.getByText('Run Ranking'))

    expect(screen.getByText('At least one symbol is required for this universe kind.')).toBeTruthy()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('calls onSubmit with valid symbols in custom_list mode', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    const textarea = screen.getByPlaceholderText('e.g. AAPL, MSFT, GOOGL')
    fireEvent.change(textarea, { target: { value: 'AAPL, MSFT, GOOGL' } })
    fireEvent.click(screen.getByText('Run Ranking'))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const request = onSubmit.mock.calls[0]?.[0]
    expect(request.universe_spec.explicit_symbols).toEqual(['AAPL', 'MSFT', 'GOOGL'])
    expect(request.universe_spec.universe_kind).toBe('custom_list')
  })

  it('shows factor weight table for the default preset and updates when a different preset is selected', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    // Default preset is the first one
    const firstPreset = SCORE_CONFIG_PRESETS[0]
    expect(firstPreset).toBeDefined()
    if (!firstPreset) return

    const firstPresetLabel = SCORE_CONFIG_PRESET_LABELS[firstPreset.score_config_id] ?? firstPreset.score_config_id
    expect(screen.getByText(firstPresetLabel)).toBeTruthy()

    // Factors from the first preset should be visible
    for (const factor of firstPreset.factors) {
      expect(screen.getByText(factor.factor_id)).toBeTruthy()
    }

    // Now switch to the second preset
    const secondPreset = SCORE_CONFIG_PRESETS[1]
    expect(secondPreset).toBeDefined()
    if (!secondPreset) return

    const presetSelect = screen.getByRole('combobox')
    fireEvent.change(presetSelect, { target: { value: secondPreset.score_config_id } })

    const secondPresetLabel = SCORE_CONFIG_PRESET_LABELS[secondPreset.score_config_id] ?? secondPreset.score_config_id
    expect(screen.getByText(secondPresetLabel)).toBeTruthy()

    // Factors from the second preset should now be visible
    for (const factor of secondPreset.factors) {
      expect(screen.getByText(factor.factor_id)).toBeTruthy()
    }

    // Factors unique to the first preset (not in second) should no longer be visible
    const firstOnlyFactors = firstPreset.factors.filter(
      (f) => !secondPreset.factors.some((sf) => sf.factor_id === f.factor_id),
    )
    for (const factor of firstOnlyFactors) {
      expect(screen.queryByText(factor.factor_id)).toBeNull()
    }
  })

  it('calls onSubmit with the correct score_config when the second preset is selected', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    const secondPreset = SCORE_CONFIG_PRESETS[1]
    expect(secondPreset).toBeDefined()
    if (!secondPreset) return

    // Switch preset
    const presetSelect = screen.getByRole('combobox')
    fireEvent.change(presetSelect, { target: { value: secondPreset.score_config_id } })

    // Fill symbols
    const textarea = screen.getByPlaceholderText('e.g. AAPL, MSFT, GOOGL')
    fireEvent.change(textarea, { target: { value: 'AAPL' } })

    fireEvent.click(screen.getByText('Run Ranking'))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const request = onSubmit.mock.calls[0]?.[0]
    expect(request.score_config.score_config_id).toBe(secondPreset.score_config_id)
    expect(request.score_config.factors).toEqual(secondPreset.factors)
  })

  it('does not show symbols textarea for broad_equity_screen universe kind', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    const broadRadio = screen.getByDisplayValue('broad_equity_screen')
    fireEvent.click(broadRadio)

    expect(screen.queryByPlaceholderText('e.g. AAPL, MSFT, GOOGL')).toBeNull()
    expect(screen.getByText('Min Market Cap (USD)')).toBeTruthy()
    expect(screen.getByText('Min ADV (USD)')).toBeTruthy()
  })

  it('submits without validation error for broad_equity_screen with no symbols', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={false} />)

    const broadRadio = screen.getByDisplayValue('broad_equity_screen')
    fireEvent.click(broadRadio)

    fireEvent.click(screen.getByText('Run Ranking'))

    expect(screen.queryByText('At least one symbol is required for this universe kind.')).toBeNull()
    expect(onSubmit).toHaveBeenCalledTimes(1)
    const request = onSubmit.mock.calls[0]?.[0]
    expect(request.universe_spec.universe_kind).toBe('broad_equity_screen')
    expect(request.universe_spec.explicit_symbols).toEqual([])
  })

  it('disables the Run Ranking button when loading', () => {
    const onSubmit = vi.fn()
    render(<GenericRankingRequestForm onSubmit={onSubmit} loading={true} />)

    const button = screen.getByText('Running...') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.className.includes('button-loading')).toBe(true)
  })
})
