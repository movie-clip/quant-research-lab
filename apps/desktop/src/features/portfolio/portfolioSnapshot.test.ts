import { describe, expect, it } from 'vitest'
import { overlayImportedSnapshot } from './portfolioSnapshot'
import type { PortfolioSnapshot } from './workspaceTypes'

function makeSnapshot(
  symbols: Record<string, number>,
  cashUsd: number,
  fileName: string,
): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: '2025-01-01 - 2026-05-25',
      importedAt: '2026-05-27T00:00:00.000Z',
      sourceFileNames: [fileName],
    },
    positions: Object.entries(symbols).map(([symbol, marketValue]) => ({
      symbol,
      marketValue,
      quantity: 1,
      currency: 'USD',
      sector: null,
      sourceType: 'equity' as const,
    })),
    cashBalances: [{ currency: 'USD', amount: cashUsd }],
    metadata: { benchmarkSymbol: 'SPY' },
  }
}

function makeSnapshotWithPositions(
  positions: Array<{ symbol: string; marketValue: number; quantity?: number | null; sector?: string | null }>,
  cashBalances: Array<{ currency: string; amount: number }> = [],
  fileName = 'TEST.pdf',
): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: '2025-01-01 - 2026-05-25',
      importedAt: '2026-05-27T00:00:00.000Z',
      sourceFileNames: [fileName],
    },
    positions: positions.map((p) => ({
      symbol: p.symbol,
      marketValue: p.marketValue,
      quantity: p.quantity === undefined ? 1 : p.quantity,
      currency: 'USD',
      sector: p.sector ?? null,
      sourceType: 'equity' as const,
    })),
    cashBalances,
    metadata: { benchmarkSymbol: 'SPY' },
  }
}

describe('overlayImportedSnapshot', () => {
  it('applies three sequential overlays correctly (IB -> +FF -> +ESPP)', () => {
    const ibSnapshot = makeSnapshot({ VUAA: 50_000, XLK: 10_000 }, 1200, 'IB2026.pdf')
    const ffSnapshot = makeSnapshot({ VTI: 3018.96 }, 52.04, 'FF2026.pdf')
    const esppSnapshot = makeSnapshot({ MSFT: 3391.24 }, 10.44, 'ESPP2026.pdf')

    const afterFf = overlayImportedSnapshot(ibSnapshot, ffSnapshot)
    const afterEspp = overlayImportedSnapshot(afterFf, esppSnapshot)

    const symbols = afterEspp.positions.map((p) => p.symbol).sort()
    expect(symbols).toContain('VUAA')
    expect(symbols).toContain('XLK')
    expect(symbols).toContain('VTI')
    expect(symbols).toContain('MSFT')
    expect(afterEspp.positions).toHaveLength(4)

    // US-14.1: USD cash balances must SUM across statements (was REPLACE).
    // IB 1200 + FF 52.04 + ESPP 10.44 = 1262.48.
    const usdBalance = afterEspp.cashBalances.find((b) => b.currency === 'USD')
    expect(usdBalance).toBeDefined()
    expect(usdBalance!.amount).toBeCloseTo(1262.48)

    const fileNames = afterEspp.importedMeta.sourceFileNames
    expect(fileNames).toContain('IB2026.pdf')
    expect(fileNames).toContain('FF2026.pdf')
    expect(fileNames).toContain('ESPP2026.pdf')
    expect(new Set(fileNames).size).toBe(fileNames.length)
  })

  it('does not duplicate symbols when the same symbol appears in two overlays', () => {
    const ibSnapshot = makeSnapshot({ VUAA: 50_000, VWCE: 5_000 }, 1000, 'IB2026.pdf')
    const secondSnapshot = makeSnapshot({ VUAA: 99_999 }, 200, 'OTHER.pdf')

    const result = overlayImportedSnapshot(ibSnapshot, secondSnapshot)

    const vuaaRows = result.positions.filter((p) => p.symbol === 'VUAA')
    expect(vuaaRows).toHaveLength(1)
    // US-14.1: duplicate-symbol positions now SUM marketValue across statements
    // (was REPLACE). IB 50_000 + second 99_999 = 149_999.
    expect(vuaaRows[0].marketValue).toBeCloseTo(149_999)
    expect(result.positions.find((p) => p.symbol === 'VWCE')).toBeDefined()
  })

  it('accumulates sourceFileNames without duplicating the same file', () => {
    const snap = makeSnapshot({ VUAA: 1000 }, 100, 'IB2026.pdf')
    const result = overlayImportedSnapshot(snap, snap)

    expect(result.importedMeta.sourceFileNames).toEqual(['IB2026.pdf'])
  })

  // ── US-14.1: symbol-collision sum behaviour ────────────────────────────────

  it('sums_marketValue_when_symbol_in_both', () => {
    const base = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 50_000, quantity: 250 }])
    const imported = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 5_000, quantity: 25 }])

    const result = overlayImportedSnapshot(base, imported)

    const msft = result.positions.find((p) => p.symbol === 'MSFT')
    expect(msft).toBeDefined()
    expect(msft!.marketValue).toBeCloseTo(55_000)
  })

  it('sums_quantity_when_both_have_non_null_quantity', () => {
    const base = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 50_000, quantity: 100 }])
    const imported = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 5_000, quantity: 10 }])

    const result = overlayImportedSnapshot(base, imported)

    const msft = result.positions.find((p) => p.symbol === 'MSFT')
    expect(msft!.quantity).toBe(110)
  })

  it('treats_null_quantity_as_zero_when_only_one_side_is_null', () => {
    const base = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 50_000, quantity: null }])
    const imported = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 5_000, quantity: 10 }])

    const result = overlayImportedSnapshot(base, imported)

    const msft = result.positions.find((p) => p.symbol === 'MSFT')
    expect(msft!.quantity).toBe(10) // null treated as 0; sum = 0 + 10
  })

  it('keeps_quantity_null_when_both_sides_null', () => {
    const base = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 50_000, quantity: null }])
    const imported = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 5_000, quantity: null }])

    const result = overlayImportedSnapshot(base, imported)

    const msft = result.positions.find((p) => p.symbol === 'MSFT')
    // Fail-closed: both unknown → merged unknown. Don't fabricate a 0.
    expect(msft!.quantity).toBeNull()
  })

  it('preserves_existing_sector_when_imported_sector_is_null', () => {
    const base = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 50_000, sector: 'Technology' }])
    const imported = makeSnapshotWithPositions([{ symbol: 'MSFT', marketValue: 5_000, sector: null }])

    const result = overlayImportedSnapshot(base, imported)

    const msft = result.positions.find((p) => p.symbol === 'MSFT')
    expect(msft!.sector).toBe('Technology')
  })

  it('sums_cash_balance_when_currency_in_both', () => {
    const base = makeSnapshotWithPositions([], [{ currency: 'USD', amount: 1000 }])
    const imported = makeSnapshotWithPositions([], [{ currency: 'USD', amount: 500 }])

    const result = overlayImportedSnapshot(base, imported)

    const usd = result.cashBalances.find((b) => b.currency === 'USD')
    expect(usd).toBeDefined()
    expect(usd!.amount).toBeCloseTo(1500)
  })
})
