import type { PortfolioSnapshot } from '../portfolio/workspaceTypes'

export type AuthoritativeCurrentPortfolio = {
  artifact_id: string
  as_of_timestamp: string
  weights: Array<{ symbol: string; weight: number }>
}

export function buildAuthoritativeCurrentPortfolio(
  draftSnapshot: PortfolioSnapshot | null,
): AuthoritativeCurrentPortfolio | null {
  if (!draftSnapshot?.importedMeta.importedAt) return null

  const positions = draftSnapshot.positions
    .filter((position) => typeof position.marketValue === 'number' && position.marketValue > 0)
    .map((position) => ({ symbol: position.symbol, marketValue: position.marketValue }))

  const totalMarketValue = positions.reduce((sum, position) => sum + position.marketValue, 0)
  if (totalMarketValue <= 0) return null

  return {
    artifact_id: `workspace_current_portfolio_${draftSnapshot.snapshotVersion}`,
    as_of_timestamp: draftSnapshot.importedMeta.importedAt,
    weights: positions.map((position) => ({
      symbol: position.symbol,
      weight: position.marketValue / totalMarketValue,
    })),
  }
}
