import { describe, expect, it } from 'vitest'

import { overlayImportedSnapshot } from './portfolioSnapshot'
import type { PortfolioSnapshot } from './workspaceTypes'

function createBaseSnapshot(): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: '2025-01-01 - 2025-12-31',
      importedAt: '2026-04-10T00:00:00Z',
      sourceFileNames: ['IB2025.pdf'],
    },
    positions: [
      { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'MSFT', marketValue: 8000, quantity: 8, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ],
    cashBalances: [
      { currency: 'USD', amount: 1000 },
      { currency: 'EUR', amount: 50 },
    ],
    metadata: {
      benchmarkSymbol: 'SPY',
      notes: 'base',
      tags: ['imported'],
    },
  }
}

function createImportedOverlaySnapshot(): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: '2026-01-01 - 2026-04-08',
      importedAt: '2026-04-10T00:05:00Z',
      sourceFileNames: ['IB2026.pdf'],
    },
    positions: [
      { symbol: 'AAPL', marketValue: 12000, quantity: 12, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'NVDA', marketValue: 9000, quantity: 6, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ],
    cashBalances: [
      { currency: 'USD', amount: 400 },
    ],
    metadata: {
      benchmarkSymbol: 'QQQ',
      notes: null,
      tags: [],
    },
  }
}

describe('overlayImportedSnapshot', () => {
  it('overlays imported positions and cash while preserving untouched holdings', () => {
    const merged = overlayImportedSnapshot(createBaseSnapshot(), createImportedOverlaySnapshot())

    expect(merged.positions).toEqual([
      { symbol: 'AAPL', marketValue: 12000, quantity: 12, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'MSFT', marketValue: 8000, quantity: 8, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'NVDA', marketValue: 9000, quantity: 6, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ])
    expect(merged.cashBalances).toEqual([
      { currency: 'EUR', amount: 50 },
      { currency: 'USD', amount: 400 },
    ])
  })

  it('merges imported metadata and source file names', () => {
    const merged = overlayImportedSnapshot(createBaseSnapshot(), createImportedOverlaySnapshot())

    expect(merged.importedMeta).toEqual({
      importer: 'interactive_brokers',
      statementPeriod: '2026-01-01 - 2026-04-08',
      importedAt: '2026-04-10T00:05:00Z',
      sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'],
    })
    expect(merged.metadata).toEqual({
      benchmarkSymbol: 'QQQ',
      notes: 'base',
      tags: ['imported'],
    })
  })

  it('keeps existing sector/currency details when imported rows omit them', () => {
    const imported = createImportedOverlaySnapshot()
    imported.positions = [
      { symbol: 'AAPL', marketValue: 13000, quantity: 13 },
    ]
    imported.cashBalances = [{ currency: 'USD', amount: 300 }]

    const merged = overlayImportedSnapshot(createBaseSnapshot(), imported)

    expect(merged.positions).toEqual([
      { symbol: 'AAPL', marketValue: 13000, quantity: 13, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'MSFT', marketValue: 8000, quantity: 8, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ])
    expect(merged.cashBalances).toEqual([
      { currency: 'EUR', amount: 50 },
      { currency: 'USD', amount: 300 },
    ])
  })

  it('keeps zero-quantity imported rows as explicit overlays', () => {
    const imported = createImportedOverlaySnapshot()
    imported.positions = [
      { symbol: 'AAPL', marketValue: 0, quantity: 0, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ]

    const merged = overlayImportedSnapshot(createBaseSnapshot(), imported)

    expect(merged.positions).toEqual([
      { symbol: 'AAPL', marketValue: 0, quantity: 0, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'MSFT', marketValue: 8000, quantity: 8, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
    ])
  })

  it('adds new mixed-currency positions and cash balances without disturbing unrelated currencies', () => {
    const imported = createImportedOverlaySnapshot()
    imported.baseCurrency = 'EUR'
    imported.positions = [
      { symbol: 'SAP', marketValue: 7000, quantity: 20, currency: 'EUR', sector: 'Technology', sourceType: 'equity' },
    ]
    imported.cashBalances = [
      { currency: 'CHF', amount: 125 },
    ]

    const merged = overlayImportedSnapshot(createBaseSnapshot(), imported)

    expect(merged.baseCurrency).toBe('EUR')
    expect(merged.positions).toEqual([
      { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'MSFT', marketValue: 8000, quantity: 8, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
      { symbol: 'SAP', marketValue: 7000, quantity: 20, currency: 'EUR', sector: 'Technology', sourceType: 'equity' },
    ])
    expect(merged.cashBalances).toEqual([
      { currency: 'CHF', amount: 125 },
      { currency: 'EUR', amount: 50 },
      { currency: 'USD', amount: 1000 },
    ])
  })

  it('does not duplicate source file names when the same file is overlaid twice', () => {
    const imported = createImportedOverlaySnapshot()
    imported.importedMeta.sourceFileNames = ['IB2025.pdf', 'IB2026.pdf']

    const merged = overlayImportedSnapshot(createBaseSnapshot(), imported)

    expect(merged.importedMeta.sourceFileNames).toEqual(['IB2025.pdf', 'IB2026.pdf'])
  })
})
