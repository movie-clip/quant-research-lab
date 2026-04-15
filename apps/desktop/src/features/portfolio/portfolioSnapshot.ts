import type { BenchmarkSummary, ImportedPortfolioSnapshotSource, PortfolioRiskSummary } from './types'
import type { PortfolioPositionSnapshot, PortfolioSnapshot } from './workspaceTypes'

function inferSourceType(symbol: string) {
  if (symbol === 'BIL' || symbol === 'SGOV' || symbol === 'SHV') return 'cash_equivalent' as const
  if (symbol.length <= 5 && symbol === symbol.toUpperCase()) return 'equity' as const
  return 'other' as const
}

export function normalizePortfolioSnapshot(snapshot: PortfolioSnapshot): PortfolioSnapshot {
  const positions = [...snapshot.positions]
    .map((position) => ({
      ...position,
      symbol: position.symbol.trim().toUpperCase(),
      marketValue: Number.isFinite(position.marketValue) ? Number(position.marketValue) : 0,
      quantity: position.quantity == null ? null : Number(position.quantity),
    }))
    .filter((position) => position.symbol)
    .sort((left, right) => left.symbol.localeCompare(right.symbol))

  const deduped = positions.reduce<PortfolioPositionSnapshot[]>((accumulator, position) => {
    const existing = accumulator.find((item) => item.symbol === position.symbol)
    if (!existing) {
      accumulator.push(position)
      return accumulator
    }
    existing.marketValue += position.marketValue
    existing.quantity = (existing.quantity ?? 0) + (position.quantity ?? 0)
    return accumulator
  }, [])

  return {
    ...snapshot,
    positions: deduped,
    cashBalances: [...snapshot.cashBalances]
      .map((balance) => ({ currency: balance.currency.trim().toUpperCase(), amount: Number.isFinite(balance.amount) ? Number(balance.amount) : 0 }))
      .filter((balance) => balance.currency)
      .sort((left, right) => left.currency.localeCompare(right.currency)),
  }
}

export function buildPortfolioSnapshotFromAnalysis(
  analysis: Pick<ImportedPortfolioSnapshotSource, 'snapshot' | 'overview'> & {
    benchmark?: BenchmarkSummary | null
    risk_summary?: PortfolioRiskSummary
  },
  importedFileNames: string[],
): PortfolioSnapshot {
  const sectorBySymbol = new Map(
    Object.entries(analysis.overview.sector_position_breakdown).flatMap(([sector, positions]) =>
      positions.map((position) => [String(position.symbol).toUpperCase(), sector] as const),
    ),
  )

  return normalizePortfolioSnapshot({
    snapshotVersion: 1,
    baseCurrency: analysis.snapshot.statement.base_currency,
    importedMeta: {
      importer: analysis.snapshot.statement.importer,
      statementPeriod: analysis.snapshot.statement.statement_period,
      importedAt: analysis.snapshot.statements[0]?.imported_at ?? new Date().toISOString(),
      sourceFileNames: importedFileNames,
    },
    positions: analysis.snapshot.positions.map((position) => ({
      symbol: position.symbol,
      marketValue: position.market_value,
      quantity: position.quantity,
      currency: position.currency,
      sector: sectorBySymbol.get(position.symbol.toUpperCase()) ?? null,
      sourceType: inferSourceType(position.symbol),
    })),
    cashBalances: analysis.snapshot.cash_balances.map((balance) => ({
      currency: balance.currency,
      amount: balance.ending_cash ?? 0,
    })),
    metadata: {
      benchmarkSymbol: analysis.benchmark?.symbol ?? analysis.risk_summary?.benchmark_symbol ?? 'SPY',
      notes: null,
      tags: [],
    },
  })
}

export function clonePortfolioSnapshot(snapshot: PortfolioSnapshot): PortfolioSnapshot {
  return normalizePortfolioSnapshot(JSON.parse(JSON.stringify(snapshot)) as PortfolioSnapshot)
}

export function overlayImportedSnapshot(baseSnapshot: PortfolioSnapshot, importedSnapshot: PortfolioSnapshot): PortfolioSnapshot {
  const next = clonePortfolioSnapshot(baseSnapshot)

  const positionBySymbol = new Map(next.positions.map((position) => [position.symbol, position]))
  for (const importedPosition of importedSnapshot.positions) {
    const existing = positionBySymbol.get(importedPosition.symbol)
    positionBySymbol.set(importedPosition.symbol, {
      ...existing,
      ...importedPosition,
      sector: importedPosition.sector ?? existing?.sector ?? null,
      currency: importedPosition.currency ?? existing?.currency ?? next.baseCurrency,
      sourceType: importedPosition.sourceType ?? existing?.sourceType,
      name: importedPosition.name ?? existing?.name,
    })
  }

  const cashByCurrency = new Map(next.cashBalances.map((balance) => [balance.currency, balance]))
  for (const importedCashBalance of importedSnapshot.cashBalances) {
    cashByCurrency.set(importedCashBalance.currency, importedCashBalance)
  }

  next.baseCurrency = importedSnapshot.baseCurrency ?? next.baseCurrency
  next.importedMeta = {
    importer: importedSnapshot.importedMeta.importer ?? next.importedMeta.importer,
    statementPeriod: importedSnapshot.importedMeta.statementPeriod ?? next.importedMeta.statementPeriod,
    importedAt: importedSnapshot.importedMeta.importedAt,
    sourceFileNames: Array.from(new Set([...next.importedMeta.sourceFileNames, ...importedSnapshot.importedMeta.sourceFileNames])),
  }
  next.positions = Array.from(positionBySymbol.values())
  next.cashBalances = Array.from(cashByCurrency.values())
  next.metadata = {
    ...next.metadata,
    benchmarkSymbol: importedSnapshot.metadata.benchmarkSymbol ?? next.metadata.benchmarkSymbol,
  }

  return normalizePortfolioSnapshot(next)
}

export function getPortfolioSnapshotGrossExposure(snapshot: PortfolioSnapshot) {
  return snapshot.positions.reduce((total, position) => total + Math.abs(position.marketValue), 0)
}

export function getPortfolioSnapshotNetCapital(snapshot: PortfolioSnapshot) {
  return snapshot.positions.reduce((total, position) => total + position.marketValue, 0)
}

export function getPortfolioSnapshotSectorCount(snapshot: PortfolioSnapshot) {
  return new Set(snapshot.positions.map((position) => position.sector ?? 'Unknown')).size
}

export function hashPortfolioSnapshot(snapshot: PortfolioSnapshot) {
  return JSON.stringify(normalizePortfolioSnapshot(snapshot))
}
