import { appStateStoreName, candidateImprovementDraftStoreName, deletePortfolioDatabase, hypotheticalReplacementReplayDraftStoreName, portfolioNodeStoreName, replacementIntentDraftStoreName, versionedProposalStoreName, withStore, withStores, workingDraftStoreName, workspaceStateStoreName, workspaceStoreName } from './portfolioDb'
import { buildImportedHistorySource } from '../features/portfolio/historySource'
import { buildPortfolioSnapshotFromAnalysis, clonePortfolioSnapshot, getPortfolioSnapshotGrossExposure, getPortfolioSnapshotNetCapital, getPortfolioSnapshotSectorCount, hashPortfolioSnapshot } from '../features/portfolio/portfolioSnapshot'
import type { ImportedPortfolioSnapshotSource, ImportedSnapshot } from '../features/portfolio/types'
import type { CandidateImprovementDraftArtifact, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedNodeSource, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, ReplacementIntentDraftArtifact, VersionedProposalArtifact, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

const activeWorkspacePointerKey = 'active-workspace-pointer'

export function buildPersistedImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedNodeSource {
  return {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildImportedHistorySource({
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
}

function createId(prefix: string) {
  return `${prefix}_${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`
}

function createChangeSummary(baseSnapshot: PortfolioSnapshot, nextSnapshot: PortfolioSnapshot, label: string) {
  const baseMap = new Map(baseSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const nextMap = new Map(nextSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const symbols = new Set([...baseMap.keys(), ...nextMap.keys()])
  const changedPositionsCount = Array.from(symbols).filter((symbol) => (baseMap.get(symbol) ?? 0) !== (nextMap.get(symbol) ?? 0)).length

  return {
    label,
    changedPositionsCount,
    changedSectorsCount: Math.abs(getPortfolioSnapshotSectorCount(nextSnapshot) - getPortfolioSnapshotSectorCount(baseSnapshot)),
    grossExposureDelta: getPortfolioSnapshotGrossExposure(nextSnapshot) - getPortfolioSnapshotGrossExposure(baseSnapshot),
    netCapitalDelta: getPortfolioSnapshotNetCapital(nextSnapshot) - getPortfolioSnapshotNetCapital(baseSnapshot),
  }
}

export function isDraftDirty(baseSnapshot: PortfolioSnapshot, draftSnapshot: PortfolioSnapshot) {
  return hashPortfolioSnapshot(baseSnapshot) !== hashPortfolioSnapshot(draftSnapshot)
}

export async function createWorkspaceFromImport(input: {
  name?: string
  analysis: ImportedPortfolioSnapshotSource
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState }> {
  const portfolioSnapshot = buildPortfolioSnapshotFromAnalysis(input.analysis, input.importedFileNames)
  const importedAt = portfolioSnapshot.importedMeta.importedAt
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const draftId = createId('draft')
  const workspace: PortfolioWorkspace = {
    id: workspaceId,
    name: input.name ?? portfolioSnapshot.importedMeta.statementPeriod ?? 'Portfolio Workspace',
    createdAt: importedAt,
    updatedAt: importedAt,
    rootNodeId,
    activeNodeId: rootNodeId,
    source: buildPersistedImportedSource({
      importedFileNames: input.importedFileNames,
      importedAt,
      importer: portfolioSnapshot.importedMeta.importer,
      baseCurrency: portfolioSnapshot.baseCurrency,
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
  const rootNode: PortfolioNode = {
    id: rootNodeId,
    workspaceId,
    parentId: null,
    kind: 'imported_base',
    name: 'Base Import',
    createdAt: importedAt,
    changeSummary: {
      label: 'Base Import',
      changedPositionsCount: portfolioSnapshot.positions.length,
      changedSectorsCount: getPortfolioSnapshotSectorCount(portfolioSnapshot),
      grossExposureDelta: getPortfolioSnapshotGrossExposure(portfolioSnapshot),
      netCapitalDelta: getPortfolioSnapshotNetCapital(portfolioSnapshot),
    },
    portfolioSnapshot,
  }
  const draft: WorkingDraft = {
    id: draftId,
    workspaceId,
    baseNodeId: rootNodeId,
    updatedAt: importedAt,
    name: 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(portfolioSnapshot),
  }
  const workspaceState: WorkspaceState = {
    workspaceId,
    activeNodeId: rootNodeId,
    activeDraftId: draftId,
    selectedExposureSnapshotId: 'draft',
    lastOpenedAt: importedAt,
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workingDraftStoreName).put(draft)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft, workspaceState })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft, workspaceState }
}

export async function getWorkspace(workspaceId: string) {
  return withStore<PortfolioWorkspace | null>(workspaceStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioWorkspace | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace'))
  })
}

export async function getNode(nodeId: string) {
  return withStore<PortfolioNode | null>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(nodeId)
    request.onsuccess = () => resolve((request.result as PortfolioNode | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load node'))
  })
}

export async function getWorkspaceNodes(workspaceId: string) {
  return withStore<PortfolioNode[]>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioNode[]) ?? [])
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace nodes'))
  })
}

export async function getDraft(workspaceId: string) {
  return withStore<WorkingDraft | null>(workingDraftStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve(((request.result as WorkingDraft[] | undefined) ?? [])[0] ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load draft'))
  })
}

export async function saveDraft(draft: WorkingDraft) {
  await withStore<void>(workingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(draft)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save draft'))
  })
}

export async function getCandidateImprovementDraft(draftId: string) {
  return withStore<CandidateImprovementDraftArtifact | null>(candidateImprovementDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as CandidateImprovementDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load candidate improvement draft'))
  })
}

export async function saveCandidateImprovementDraft(annotation: CandidateImprovementDraftArtifact) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save candidate improvement draft'))
  })
}

export async function deleteCandidateImprovementDraft(draftId: string) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete candidate improvement draft'))
  })
}

export async function getReplacementIntentDraft(draftId: string) {
  return withStore<ReplacementIntentDraftArtifact | null>(replacementIntentDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ReplacementIntentDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load replacement intent draft'))
  })
}

export async function saveReplacementIntentDraft(annotation: ReplacementIntentDraftArtifact) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save replacement intent draft'))
  })
}

export async function deleteReplacementIntentDraft(draftId: string) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete replacement intent draft'))
  })
}

export async function getHypotheticalReplacementReplayDraft(draftId: string) {
  return withStore<HypotheticalReplacementReplayDraftArtifact | null>(hypotheticalReplacementReplayDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as HypotheticalReplacementReplayDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load hypothetical replay draft'))
  })
}

export async function saveHypotheticalReplacementReplayDraft(annotation: HypotheticalReplacementReplayDraftArtifact) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save hypothetical replay draft'))
  })
}

export async function deleteHypotheticalReplacementReplayDraft(draftId: string) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete hypothetical replay draft'))
  })
}

export async function getWorkspaceProposalArtifacts(workspaceId: string) {
  return withStore<VersionedProposalArtifact[]>(versionedProposalStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve(((request.result as VersionedProposalArtifact[] | undefined) ?? []).sort((left, right) => right.versionNumber - left.versionNumber || right.createdAt.localeCompare(left.createdAt)))
    request.onerror = () => reject(request.error ?? new Error('Failed to load proposal artifacts'))
  })
}

export async function saveProposalArtifact(proposal: VersionedProposalArtifact) {
  await withStore<void>(versionedProposalStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(proposal)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save proposal artifact'))
  })
}

export async function createDraftFromNode(input: { workspaceId: string; baseNodeId: string; name?: string }) {
  const node = await getNode(input.baseNodeId)
  if (!node) throw new Error('Base node not found')
  const existingDraft = await getDraft(input.workspaceId)
  const draft: WorkingDraft = {
    id: existingDraft?.id ?? createId('draft'),
    workspaceId: input.workspaceId,
    baseNodeId: input.baseNodeId,
    updatedAt: new Date().toISOString(),
    name: input.name ?? 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(node.portfolioSnapshot),
  }
  await saveDraft(draft)
  await deleteCandidateImprovementDraft(draft.id)
  await deleteReplacementIntentDraft(draft.id)
  await deleteHypotheticalReplacementReplayDraft(draft.id)
  return draft
}

export async function discardDraft(workspaceId: string) {
  const state = await getWorkspaceState(workspaceId)
  if (!state) return null
  return createDraftFromNode({ workspaceId, baseNodeId: state.activeNodeId })
}

export async function getWorkspaceState(workspaceId: string) {
  return withStore<WorkspaceState | null>(workspaceStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => resolve((request.result as WorkspaceState | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace state'))
  })
}

export async function setActiveNode(input: { workspaceId: string; nodeId: string; createDraftFromNode?: boolean }) {
  const state = (await getWorkspaceState(input.workspaceId)) ?? {
    workspaceId: input.workspaceId,
    activeNodeId: input.nodeId,
    activeDraftId: null,
    lastOpenedAt: new Date().toISOString(),
  }
  const draft = input.createDraftFromNode === false ? null : await createDraftFromNode({ workspaceId: input.workspaceId, baseNodeId: input.nodeId })
  const nextState: WorkspaceState = {
    ...state,
    activeNodeId: input.nodeId,
    activeDraftId: draft?.id ?? null,
    selectedExposureSnapshotId: draft ? 'draft' : input.nodeId,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStores([workspaceStateStoreName, workspaceStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStateStoreName).put(nextState)

    const workspaceStore = transaction.objectStore(workspaceStoreName)
    const workspaceRequest = workspaceStore.get(input.workspaceId)
    workspaceRequest.onsuccess = () => {
      const workspace = workspaceRequest.result as PortfolioWorkspace | undefined
      if (workspace) {
        workspaceStore.put({ ...workspace, activeNodeId: input.nodeId, updatedAt: nextState.lastOpenedAt })
      }
      const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId: input.workspaceId })
      pointerRequest.onsuccess = () => resolve(nextState)
      pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to update active workspace pointer'))
    }
    workspaceRequest.onerror = () => reject(workspaceRequest.error ?? new Error('Failed to load workspace for active node update'))
  })

  return nextState
}

export async function setSelectedExposureSnapshot(input: { workspaceId: string; snapshotId: string }) {
  const state = await getWorkspaceState(input.workspaceId)
  if (!state) return null

  const nextState: WorkspaceState = {
    ...state,
    selectedExposureSnapshotId: input.snapshotId,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStore<void>(workspaceStateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(nextState)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to persist selected exposure snapshot'))
  })

  return nextState
}

export async function saveVariantFromDraft(input: { workspaceId: string; draftId: string; variantName: string }) {
  const draft = await getDraft(input.workspaceId)
  if (!draft || draft.id !== input.draftId) throw new Error('Draft not found')
  const baseNode = await getNode(draft.baseNodeId)
  if (!baseNode) throw new Error('Base node not found')

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: draft.baseNodeId,
    kind: 'variant',
    name: input.variantName,
    createdAt: new Date().toISOString(),
    changeSummary: createChangeSummary(baseNode.portfolioSnapshot, draft.portfolioSnapshot, input.variantName),
    portfolioSnapshot: clonePortfolioSnapshot(draft.portfolioSnapshot),
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save portfolio node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found after saving variant')
  return { node, workspace, workspaceState }
}

export async function saveImportedSnapshotNode(input: {
  workspaceId: string
  parentNodeId: string
  portfolioSnapshot: PortfolioSnapshot
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  name: string
}) {
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found')

  const parentNode = await getNode(input.parentNodeId)
  if (!parentNode) throw new Error('Parent node not found')

  const source: ImportedNodeSource = buildPersistedImportedSource({
    importedFileNames: input.importedFileNames,
    importedAt: input.portfolioSnapshot.importedMeta.importedAt,
    importer: input.portfolioSnapshot.importedMeta.importer,
    baseCurrency: input.portfolioSnapshot.baseCurrency,
    historyContext: input.historyContext ?? null,
    importedHistorySnapshot: input.importedHistorySnapshot ?? null,
  })

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: input.parentNodeId,
    kind: 'imported_snapshot',
    name: input.name,
    createdAt: input.portfolioSnapshot.importedMeta.importedAt,
    changeSummary: createChangeSummary(parentNode.portfolioSnapshot, input.portfolioSnapshot, input.name),
    portfolioSnapshot: input.portfolioSnapshot,
    source,
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save imported snapshot node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const nextWorkspace = await getWorkspace(input.workspaceId)
  if (!nextWorkspace) throw new Error('Workspace not found after saving imported snapshot node')
  return { node, workspace: nextWorkspace, workspaceState }
}

export async function clearPortfolioWorkspaceState() {
  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName, candidateImprovementDraftStoreName, replacementIntentDraftStoreName, hypotheticalReplacementReplayDraftStoreName, versionedProposalStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).clear()
    transaction.objectStore(portfolioNodeStoreName).clear()
    transaction.objectStore(workingDraftStoreName).clear()
    transaction.objectStore(workspaceStateStoreName).clear()
    transaction.objectStore(candidateImprovementDraftStoreName).clear()
    transaction.objectStore(replacementIntentDraftStoreName).clear()
    transaction.objectStore(hypotheticalReplacementReplayDraftStoreName).clear()
    transaction.objectStore(versionedProposalStoreName).clear()
    const request = transaction.objectStore(appStateStoreName).delete(activeWorkspacePointerKey)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to clear workspace state'))
  })
}

export async function resetLocalPortfolioDatabase() {
  await deletePortfolioDatabase()
}

export async function getLastOpenedWorkspaceState() {
  const pointer = await withStore<{ id: string; workspaceId: string } | null>(appStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(activeWorkspacePointerKey)
    request.onsuccess = () => resolve((request.result as { id: string; workspaceId: string } | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load active workspace pointer'))
  })
  if (!pointer) return null
  return getWorkspaceState(pointer.workspaceId)
}
