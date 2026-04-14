import { clonePortfolioSnapshot, normalizePortfolioSnapshot } from './portfolioSnapshot'
import type { PortfolioPositionSnapshot, PortfolioSnapshot } from './workspaceTypes'

export function setPositionMarketValue(snapshot: PortfolioSnapshot, symbol: string, marketValue: number) {
  const next = clonePortfolioSnapshot(snapshot)
  next.positions = next.positions.map((position) => position.symbol === symbol.toUpperCase()
    ? { ...position, marketValue: Number.isFinite(marketValue) ? marketValue : 0 }
    : position)
  return normalizePortfolioSnapshot(next)
}

export function addPosition(snapshot: PortfolioSnapshot, position: PortfolioPositionSnapshot) {
  const next = clonePortfolioSnapshot(snapshot)
  next.positions = [...next.positions, { ...position, symbol: position.symbol.toUpperCase() }]
  return normalizePortfolioSnapshot(next)
}

export function removePosition(snapshot: PortfolioSnapshot, symbol: string) {
  const next = clonePortfolioSnapshot(snapshot)
  next.positions = next.positions.filter((position) => position.symbol !== symbol.toUpperCase())
  return normalizePortfolioSnapshot(next)
}
