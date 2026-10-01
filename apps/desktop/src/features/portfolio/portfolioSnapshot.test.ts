import { describe, expect, it } from 'vitest'
import { IB_TRUTH, ibOverview, ibStatementSnapshot } from '../../test/combinedImportFixtures'
import * as portfolioAnalysisAdapterModule from './portfolioAnalysisAdapter'
import * as portfolioSnapshotModule from './portfolioSnapshot'
import { buildPortfolioSnapshotFromAnalysis, normalizePortfolioSnapshot } from './portfolioSnapshot'
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

describe('desktop no longer merges holdings (US-46.1: analyze-combined is the one merge source)', () => {
  it('has no client-side overlay export left to sum statements with', () => {
    // Regression guard: the client overlay summed same-symbol rows across statements and doubled a
    // statement added onto itself (VUAA 160). Merging belongs to the engine.
    expect('overlayImportedSnapshot' in portfolioSnapshotModule).toBe(false)
    expect('combineImportedSnapshots' in portfolioAnalysisAdapterModule).toBe(false)
  })
})

describe('normalizePortfolioSnapshot dedupe key (US-46.1 AC 8)', () => {
  function withPositions(
    positions: Array<{ symbol: string; marketValue: number; quantity: number | null; currency: string | null }>,
  ): PortfolioSnapshot {
    return {
      ...makeSnapshot({}, 0, 'TEST.pdf'),
      positions: positions.map((position) => ({ ...position, sector: null, sourceType: 'equity' as const })),
    }
  }

  it('never sums two currencies of one symbol', () => {
    const normalized = normalizePortfolioSnapshot(
      withPositions([
        { symbol: 'SXRV', marketValue: 8_823.6, quantity: 6, currency: 'EUR' },
        { symbol: 'SXRV', marketValue: 1_000, quantity: 1, currency: 'USD' },
      ]),
    )

    const rows = normalized.positions.filter((position) => position.symbol === 'SXRV')
    expect(rows).toHaveLength(2)
    expect(rows.find((row) => row.currency === 'EUR')).toMatchObject({ marketValue: 8_823.6, quantity: 6 })
    expect(rows.find((row) => row.currency === 'USD')).toMatchObject({ marketValue: 1_000, quantity: 1 })
  })

  it('still sums the same symbol in the same currency (US-14.1: distinct accounts holding one line)', () => {
    const normalized = normalizePortfolioSnapshot(
      withPositions([
        { symbol: 'MSFT', marketValue: 50_000, quantity: 100, currency: 'USD' },
        { symbol: 'MSFT', marketValue: 5_000, quantity: 10, currency: 'USD' },
      ]),
    )

    expect(normalized.positions).toHaveLength(1)
    expect(normalized.positions[0]).toMatchObject({ symbol: 'MSFT', marketValue: 55_000, quantity: 110 })
  })

  it('keeps a row with no currency apart from the same symbol with a currency', () => {
    const normalized = normalizePortfolioSnapshot(
      withPositions([
        { symbol: 'MSFT', marketValue: 100, quantity: 1, currency: null },
        { symbol: 'MSFT', marketValue: 200, quantity: 2, currency: 'USD' },
      ]),
    )

    expect(normalized.positions).toHaveLength(2)
  })

  it('leaves an engine-combined snapshot untouched: 18 distinct IB2026 lines stay 18 (US-46.1 AC 1)', () => {
    // The engine already returned one row per holding; normalising must not merge or drop any.
    const built = buildPortfolioSnapshotFromAnalysis(
      { snapshot: ibStatementSnapshot(), overview: ibOverview() },
      ['IB2026.csv'],
    )

    expect(built.positions).toHaveLength(IB_TRUTH.positionCount)
    const vuaa = built.positions.find((position) => position.symbol === 'VUAA')
    expect(vuaa).toMatchObject({ quantity: IB_TRUTH.vuaaQuantity, marketValue: IB_TRUTH.vuaaMarketValue })
  })
})

describe('buildPortfolioSnapshotFromAnalysis fxRates (US-30.2)', () => {
  function makeAnalysis(statementTotals: { fx_rates: Record<string, number> } | null) {
    return {
      snapshot: {
        statement: { importer: 'interactive_brokers', base_currency: 'USD', statement_period: '2026-01-01 - 2026-06-30' },
        statements: [{ imported_at: '2026-07-08T00:00:00Z' }],
        statement_totals: statementTotals,
        positions: [{ symbol: 'AAPL', market_value: 1000, quantity: 10, currency: 'USD' }],
        cash_balances: [{ currency: 'USD', ending_cash: 500 }],
      },
      overview: null,
    } as unknown as Parameters<typeof buildPortfolioSnapshotFromAnalysis>[0]
  }

  it('copies statement-implied fx_rates into the workspace snapshot', () => {
    const built = buildPortfolioSnapshotFromAnalysis(
      makeAnalysis({ fx_rates: { EURUSD: 1.1422, USDUSD: 1.0 } }),
      ['IB2026.csv'],
    )
    expect(built.fxRates).toEqual({ EURUSD: 1.1422, USDUSD: 1.0 })
  })

  it('leaves fxRates absent when the analysis carries no statement totals', () => {
    const built = buildPortfolioSnapshotFromAnalysis(makeAnalysis(null), ['IB2026.csv'])
    expect(built.fxRates).toBeUndefined()
  })
})
