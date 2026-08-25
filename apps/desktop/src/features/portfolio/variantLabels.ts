import type { PortfolioNode } from './workspaceTypes'

function buildNodePath(node: PortfolioNode, nodeById: Map<string, PortfolioNode>): string[] {
  const path: string[] = [node.kind === 'imported_base' ? 'base' : node.name]
  let current = node

  while (current.parentId) {
    const parent = nodeById.get(current.parentId)
    if (!parent) break
    path.unshift(parent.kind === 'imported_base' ? 'base' : parent.name)
    current = parent
  }

  return path
}

export function resolveNodeImportDate(node: PortfolioNode, nodes: PortfolioNode[]): string | null {
  const nodeById = new Map(nodes.map((item) => [item.id, item]))
  const importedAt = node.portfolioSnapshot?.importedMeta?.importedAt
  if (importedAt) return importedAt.slice(0, 10)

  let current = node
  while (current.parentId) {
    const parent = nodeById.get(current.parentId)
    if (!parent) break
    const parentImportedAt = parent.portfolioSnapshot?.importedMeta?.importedAt
    if (parentImportedAt) return parentImportedAt.slice(0, 10)
    current = parent
  }

  return null
}

export function formatVariantNodeLabel(node: PortfolioNode, nodes: PortfolioNode[]): string {
  const nodeById = new Map(nodes.map((item) => [item.id, item]))
  const path = buildNodePath(node, nodeById).join(' -> ')
  const importDate = resolveNodeImportDate(node, nodes)
  return importDate ? `${path} (${importDate})` : path
}

export function formatWorkingDraftLabel(activeNode: PortfolioNode | null, nodes: PortfolioNode[]): string {
  if (!activeNode) return 'Working Draft · base'
  return `Working Draft · ${formatVariantNodeLabel(activeNode, nodes)}`
}
