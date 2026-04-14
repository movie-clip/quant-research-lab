import type { PortfolioNode } from './workspaceTypes'
import { formatVariantNodeLabel } from './variantLabels'

type VariantListProps = {
  nodes: PortfolioNode[]
  activeNodeId: string | null
  onOpenNode?: (nodeId: string) => void
}

export function VariantList({ nodes, activeNodeId, onOpenNode }: VariantListProps) {
  if (!nodes.length) return null

  const orderedNodes = [...nodes].sort((left, right) => left.createdAt.localeCompare(right.createdAt))

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Variants</p></div>
        <p className="helper">Base import plus immutable child variants saved from the working draft.</p>
      </div>
      <div className="list-table">
        {orderedNodes.map((node) => (
          <div className="list-row" key={node.id}>
            <span>{formatVariantNodeLabel(node, nodes)}{node.id === activeNodeId ? ' · active' : ''}</span>
            <button className="secondary-button" type="button" onClick={() => onOpenNode?.(node.id)} disabled={node.id === activeNodeId}>Open</button>
          </div>
        ))}
      </div>
    </section>
  )
}
