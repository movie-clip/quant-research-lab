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

export function formatVariantNodeLabel(node: PortfolioNode, nodes: PortfolioNode[]): string {
  const nodeById = new Map(nodes.map((item) => [item.id, item]))
  return buildNodePath(node, nodeById).join(' -> ')
}

export function formatWorkingDraftLabel(activeNode: PortfolioNode | null, nodes: PortfolioNode[]): string {
  if (!activeNode) return 'Working Draft · base'
  return `Working Draft · ${formatVariantNodeLabel(activeNode, nodes)}`
}
