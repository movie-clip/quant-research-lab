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

    const usdBalance = afterEspp.cashBalances.find((b) => b.currency === 'USD')
    expect(usdBalance).toBeDefined()
    expect(usdBalance!.amount).toBeCloseTo(10.44)

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
    expect(vuaaRows[0].marketValue).toBeCloseTo(99_999)
    expect(result.positions.find((p) => p.symbol === 'VWCE')).toBeDefined()
  })

  it('accumulates sourceFileNames without duplicating the same file', () => {
    const snap = makeSnapshot({ VUAA: 1000 }, 100, 'IB2026.pdf')
    const result = overlayImportedSnapshot(snap, snap)

    expect(result.importedMeta.sourceFileNames).toEqual(['IB2026.pdf'])
  })
})
