import { buildImportedHistorySource } from '../features/portfolio/historySource'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import { analyzeCombinedImport } from '../features/portfolio/portfolioAnalysisAdapter'
import { buildPortfolioSnapshotFromAnalysis, clonePortfolioSnapshot } from '../features/portfolio/portfolioSnapshot'
import type { ImportAdmissionSummaryV1, ImportedBootstrapResponse } from '../features/portfolio/types'
import type { ImportedNodeSource, PortfolioNode, PortfolioWorkspace, WorkingDraft } from '../features/portfolio/workspaceTypes'

/**
 * Saved-node re-derive (US-46.1 AC 10-12, US-46.3 AC 13-15, US-46.4 AC 11; decisions D-5, D-7, D-11, D-12).
 *
 * A node saved before `derivationVersion` existed may hold doubled holdings, a last-file-only
 * admission label or a fabricated Freedom24 cost basis. On load, each such node's stored statement
 * is sent back through `analyze-combined`; the engine owns the merge guards, the admission roll-up
 * over `carried_admissions` and the legacy cost-basis scrub. This module only orchestrates and
 * computes no financial value or label.
 *
 * In memory only: nothing is written back to IndexedDB, so loading is deterministic from the
 * stored inputs and nothing stored is destroyed. A node that cannot be re-derived is returned with
 * no portfolio snapshot, admission summary or exposure override, so old figures are never shown as
 * current.
 */

const noStoredStatementMessage =
  'This saved portfolio has no stored statement to recompute from, so its saved figures are not shown. Re-import the original statements.'
const missingLineageAdmissionMessage =
  'A statement this saved portfolio was built from has no recorded admission review, so it cannot be recomputed and its saved figures are not shown. Re-import the original statements.'

function importSourceOf(node: PortfolioNode, workspace: PortfolioWorkspace): ImportedNodeSource | null {
  if (node.kind === 'imported_base') return workspace.source
  if (node.kind === 'imported_snapshot') return node.source ?? null
  return null
}

function nodeDepth(node: PortfolioNode, nodeById: Map<string, PortfolioNode>) {
  let depth = 0
  const seen = new Set<string>([node.id])
  let current = node
  while (current.parentId) {
    const parent = nodeById.get(current.parentId)
    if (!parent || seen.has(parent.id)) break
    seen.add(parent.id)
    depth += 1
    current = parent
  }
  return depth
}

/**
 * Persisted admission summaries on the lineage root..node, root first. Each is one statement's own
 * engine-computed admission. Null when the lineage is incomplete or any import node on it has no
 * recorded admission: the node is then not re-derivable.
 */
function collectLineageAdmissions(
  node: PortfolioNode,
  nodeById: Map<string, PortfolioNode>,
  workspace: PortfolioWorkspace,
): ImportAdmissionSummaryV1[] | null {
  const admissions: ImportAdmissionSummaryV1[] = []
  const seen = new Set<string>()
  let current: PortfolioNode | null = node
  let reachedRoot = false
  while (current && !seen.has(current.id)) {
    seen.add(current.id)
    const source = importSourceOf(current, workspace)
    if (source) {
      if (!source.admissionSummary) return null
      admissions.push(source.admissionSummary)
    }
    if (current.kind === 'imported_base') {
      reachedRoot = true
      break
    }
    current = current.parentId ? (nodeById.get(current.parentId) ?? null) : null
  }
  return reachedRoot ? admissions.reverse() : null
}

type NodeOutcome = { ok: true; node: PortfolioNode; source: ImportedNodeSource } | { ok: false; node: PortfolioNode; source: ImportedNodeSource; detail: string }

function failedOutcome(node: PortfolioNode, source: ImportedNodeSource, detail: string): NodeOutcome {
  return {
    ok: false,
    detail,
    node: { ...node, portfolioSnapshot: null },
    source: { ...source, admissionSummary: null, importedExposureOverride: null },
  }
}

async function rederiveNode(
  node: PortfolioNode,
  source: ImportedNodeSource,
  nodeById: Map<string, PortfolioNode>,
  workspace: PortfolioWorkspace,
): Promise<NodeOutcome> {
  const stored = source.historySource
  if (stored.kind !== 'imported_replay' || !stored.importedHistorySnapshot) {
    return failedOutcome(node, source, noStoredStatementMessage)
  }

  const isRoot = node.kind === 'imported_base'
  const carriedAdmissions = isRoot ? [] : collectLineageAdmissions(node, nodeById, workspace)
  if (!carriedAdmissions) {
    return failedOutcome(node, source, missingLineageAdmissionMessage)
  }

  let response: ImportedBootstrapResponse
  try {
    response = await analyzeCombinedImport({ snapshots: [stored.importedHistorySnapshot], carriedAdmissions })
  } catch (caughtError) {
    return failedOutcome(node, source, caughtError instanceof Error ? caughtError.message : 'Combined import analysis failed')
  }
  if (!response?.snapshot) {
    return failedOutcome(node, source, noStoredStatementMessage)
  }

  const projection = projectImportedBootstrap(response)
  const previousSnapshot = node.portfolioSnapshot
  const rebuilt = buildPortfolioSnapshotFromAnalysis(
    projection.workspace,
    previousSnapshot?.importedMeta.sourceFileNames ?? source.importedFileNames,
  )
  const portfolioSnapshot = {
    ...rebuilt,
    importedMeta: { ...rebuilt.importedMeta, importedAt: previousSnapshot?.importedMeta.importedAt ?? source.importedAt },
  }

  const nextSource: ImportedNodeSource = {
    ...source,
    historySource: buildImportedHistorySource({
      historyContext: stored.historyContext,
      importedHistorySnapshot: response.snapshot,
    }),
    admissionSummary: response.admission_summary,
  }
  if (isRoot) {
    nextSource.importedExposureOverride = {
      overview: projection.workspace.overview,
      lookthrough: projection.workspace.lookthrough,
      lookthrough_sector_exposure: projection.workspace.lookthrough_sector_exposure,
      market_overlap: projection.workspace.market_overlap,
      current_state_concentration: projection.workspace.current_state_concentration,
      availability: projection.workspace.availability,
    }
  } else if (source.importedExposureOverride !== undefined) {
    // Add nodes never stored an override; a stale one must not survive.
    nextSource.importedExposureOverride = null
  }

  return { ok: true, node: { ...node, portfolioSnapshot }, source: nextSource }
}

/**
 * Re-derive every legacy import node (root: `workspace.source`; add nodes: `node.source`), ancestor
 * first. Variant nodes are not touched. `importError` is the server detail of each failed node
 * (distinct messages joined), or null.
 */
export async function rederiveSavedNodes(input: {
  workspace: PortfolioWorkspace
  nodes: PortfolioNode[]
  activeNode: PortfolioNode
  draft: WorkingDraft | null
  isActive?: () => boolean
}): Promise<{
  workspace: PortfolioWorkspace
  nodes: PortfolioNode[]
  activeNode: PortfolioNode
  draft: WorkingDraft | null
  importError: string | null
}> {
  const isActive = input.isActive ?? (() => true)
  const { workspace } = input

  // The active node is read separately from the node list; derive over their union so both agree.
  const allNodes = input.nodes.some((item) => item.id === input.activeNode.id) ? input.nodes : [...input.nodes, input.activeNode]
  const nodeById = new Map(allNodes.map((item) => [item.id, item]))

  const legacyNodes = allNodes
    .filter((item) => {
      const source = importSourceOf(item, workspace)
      return source != null && source.derivationVersion === undefined
    })
    .map((item) => ({ item, depth: nodeDepth(item, nodeById) }))
    .sort((left, right) => left.depth - right.depth)
    .map(({ item }) => item)

  if (!legacyNodes.length) {
    return { workspace, nodes: input.nodes, activeNode: input.activeNode, draft: input.draft, importError: null }
  }

  const outcomes = new Map<string, NodeOutcome>()
  const failures: string[] = []
  for (const legacyNode of legacyNodes) {
    // Lineage reads use the stored nodes, never a sibling's re-derived output.
    const outcome = await rederiveNode(legacyNode, importSourceOf(legacyNode, workspace) as ImportedNodeSource, nodeById, workspace)
    if (!isActive()) {
      return { workspace, nodes: input.nodes, activeNode: input.activeNode, draft: input.draft, importError: null }
    }
    outcomes.set(legacyNode.id, outcome)
    if (!outcome.ok && !failures.includes(outcome.detail)) {
      failures.push(outcome.detail)
    }
  }

  const applyOutcome = (item: PortfolioNode): PortfolioNode => {
    const outcome = outcomes.get(item.id)
    if (!outcome) return item
    return item.kind === 'imported_snapshot' ? { ...outcome.node, source: outcome.source } : outcome.node
  }

  const rootOutcome = Array.from(outcomes.values()).find((outcome) => outcome.node.kind === 'imported_base')
  const nextWorkspace: PortfolioWorkspace = rootOutcome ? { ...workspace, source: rootOutcome.source } : workspace
  const nextNodes = input.nodes.map(applyOutcome)
  const nextActiveNode = applyOutcome(input.activeNode)

  // A clean draft mirrors its base node, so it is re-cloned from the re-derived node (or dropped when
  // that node has no snapshot). A dirty draft carries the user's edits and is left alone.
  let nextDraft = input.draft
  if (nextDraft && nextDraft.status === 'clean' && outcomes.has(nextDraft.baseNodeId)) {
    const baseNode = applyOutcome(nodeById.get(nextDraft.baseNodeId) as PortfolioNode)
    nextDraft = baseNode.portfolioSnapshot
      ? { ...nextDraft, portfolioSnapshot: clonePortfolioSnapshot(baseNode.portfolioSnapshot) }
      : null
  }

  return {
    workspace: nextWorkspace,
    nodes: nextNodes,
    activeNode: nextActiveNode,
    draft: nextDraft,
    importError: failures.length ? failures.join('; ') : null,
  }
}
