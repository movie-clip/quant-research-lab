import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CacheStats } from './types'
import { CacheControlCard } from './CacheControlCard'

vi.mock('./portfolioAnalysisAdapter', () => ({
  getCacheStats: vi.fn(),
  clearCache: vi.fn(),
}))

import { getCacheStats, clearCache } from './portfolioAnalysisAdapter'
const mockStats = vi.mocked(getCacheStats)
const mockClear = vi.mocked(clearCache)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function stats(overrides?: Partial<CacheStats>): CacheStats {
  return {
    enabled: true,
    cache_dir: '/data/raw/fmp-cache',
    total_entries: 42,
    namespaces: [
      { namespace: 'history', entries: 30 },
      { namespace: 'history_yf', entries: 12 },
    ],
    ...overrides,
  }
}

describe('CacheControlCard', () => {
  it('renders cache stats from the adapter', async () => {
    mockStats.mockResolvedValue(stats())
    const { container } = render(<CacheControlCard />)
    await waitFor(() => expect(container.textContent).toContain('42 cached entries'))
    expect(container.textContent).toContain('history: 30')
    expect(container.textContent).toContain('history_yf: 12')
  })

  it('clears the cache then re-fetches stats', async () => {
    mockStats.mockResolvedValueOnce(stats()).mockResolvedValueOnce(stats({ total_entries: 0, namespaces: [] }))
    mockClear.mockResolvedValue({ removed: 42, namespace: null })
    const { container } = render(<CacheControlCard />)
    await waitFor(() => expect(container.textContent).toContain('42 cached entries'))

    fireEvent.click(screen.getByRole('button', { name: /clear market-data cache/i }))

    await waitFor(() => expect(mockClear).toHaveBeenCalledWith(null))
    await waitFor(() => expect(container.textContent).toMatch(/Removed 42 cached files/i))
    expect(container.textContent).toContain('Cache is empty.')
  })

  it('shows an error state when stats fail', async () => {
    mockStats.mockRejectedValue(new Error('boom'))
    render(<CacheControlCard />)
    await waitFor(() => expect(screen.getByText('Cache unavailable')).toBeTruthy())
  })

  it('shows an error when clearing fails', async () => {
    mockStats.mockResolvedValue(stats())
    mockClear.mockRejectedValue(new Error('cache locked'))
    const { container } = render(<CacheControlCard />)
    await waitFor(() => expect(container.textContent).toContain('42 cached entries'))

    fireEvent.click(screen.getByRole('button', { name: /clear market-data cache/i }))
    await waitFor(() => expect(screen.getByText('Cache unavailable')).toBeTruthy())
  })
})
