import { appStateStoreName, deletePortfolioDatabase, portfolioNodeStoreName, withStore, withStores, workingDraftStoreName, workspaceStateStoreName, workspaceStoreName } from './portfolioDb'
import { buildImportedHistorySource } from '../features/portfolio/historySource'
import { buildPortfolioSnapshotFromAnalysis, clonePortfolioSnapshot, getPortfolioSnapshotGrossExposure, getPortfolioSnapshotNetCapital, getPortfolioSnapshotSectorCount } from '../features/portfolio/portfolioSnapshot'
import type { ImportAdmissionReviewDispositionV1, ImportAdmissionSummaryV1, ImportedPortfolioSnapshotSource, ImportedSnapshot } from '../features/portfolio/types'
import type { ImportedHistoryContext, ImportedNodeSource, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

const activeWorkspacePointerKey = 'active-workspace-pointer'
type ImportAdmissionCheckV1 = ImportAdmissionSummaryV1['checks'][number]
type NonPassImportAdmissionCheckV1 = ImportAdmissionCheckV1 & { status: Exclude<ImportAdmissionCheckV1['status'], 'pass'> }
type CanonicalImportAdmissionEvidenceSummary = {
  status: ImportAdmissionReviewDispositionV1['evidence_summary']['status']
  trust_impact: ImportAdmissionReviewDispositionV1['evidence_summary']['trust_impact']
  message: string
  affected_fields: string[]
  observed: { label: string; value: number | string | null } | null
  comparison: { label: string; value: number | string | null } | null
  delta: number | null
  currency: string | null
}

export function buildPersistedImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  admissionSummary?: ImportAdmissionSummaryV1 | null
  admissionReviewDispositions?: Record<string, ImportAdmissionReviewDispositionV1>
}): ImportedNodeSource {
  const source: ImportedNodeSource = {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildImportedHistorySource({
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
  if (input.admissionSummary !== undefined) {
    source.admissionSummary = input.admissionSummary
  }
  if (input.admissionReviewDispositions !== undefined) {
    const sanitizedDispositions = sanitizeImportAdmissionReviewDispositions(input.admissionReviewDispositions)
    if (sanitizedDispositions) {
      source.admissionReviewDispositions = sanitizedDispositions
    }
  }
  return source
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function sanitizeAdmissionEvidenceValue(value: unknown): { label: string; value: number | string | null } | null | undefined {
  if (value === undefined) return undefined
  if (value === null) return null
  if (!isPlainRecord(value) || typeof value.label !== 'string') return undefined
  if (value.value !== null && typeof value.value !== 'string' && (typeof value.value !== 'number' || !Number.isFinite(value.value))) return undefined
  return { label: value.label, value: value.value }
}

function canonicalizeAdmissionEvidenceValue(value: ImportAdmissionReviewDispositionV1['evidence_summary']['observed']): CanonicalImportAdmissionEvidenceSummary['observed'] {
  return value ? { label: value.label, value: value.value } : null
}

function canonicalizeImportAdmissionEvidenceSummary(value: ImportAdmissionReviewDispositionV1['evidence_summary']): CanonicalImportAdmissionEvidenceSummary {
  return {
    status: value.status,
    trust_impact: value.trust_impact,
    message: value.message,
    affected_fields: [...(value.affected_fields ?? [])],
    observed: canonicalizeAdmissionEvidenceValue(value.observed),
    comparison: canonicalizeAdmissionEvidenceValue(value.comparison),
    delta: value.delta ?? null,
    currency: value.currency ?? null,
  }
}

function buildCurrentImportAdmissionCheckEvidence(check: NonPassImportAdmissionCheckV1): CanonicalImportAdmissionEvidenceSummary {
  return canonicalizeImportAdmissionEvidenceSummary({
    status: check.status,
    trust_impact: check.trust_impact,
    message: check.message,
    affected_fields: check.affected_fields ?? [],
    observed: check.observed ?? null,
    comparison: check.comparison ?? null,
    delta: check.delta ?? null,
    currency: check.currency ?? null,
  })
}

function importAdmissionEvidenceSummariesMatch(savedEvidence: ImportAdmissionReviewDispositionV1['evidence_summary'], currentCheck: NonPassImportAdmissionCheckV1) {
  return JSON.stringify(canonicalizeForFingerprint(canonicalizeImportAdmissionEvidenceSummary(savedEvidence)))
    === JSON.stringify(canonicalizeForFingerprint(buildCurrentImportAdmissionCheckEvidence(currentCheck)))
}

function sanitizeImportAdmissionEvidenceSummary(value: unknown): ImportAdmissionReviewDispositionV1['evidence_summary'] | null {
  if (!isPlainRecord(value)) return null
  if (value.status !== 'warn' && value.status !== 'fail' && value.status !== 'unavailable') return null
  if (value.trust_impact !== 'none' && value.trust_impact !== 'degraded' && value.trust_impact !== 'withheld' && value.trust_impact !== 'unavailable') return null
  if (typeof value.message !== 'string') return null
  if (!Array.isArray(value.affected_fields) || !value.affected_fields.every((field) => typeof field === 'string')) return null

  const observed = sanitizeAdmissionEvidenceValue(value.observed)
  const comparison = sanitizeAdmissionEvidenceValue(value.comparison)
  if (observed === undefined && 'observed' in value) return null
  if (comparison === undefined && 'comparison' in value) return null
  if (value.delta !== undefined && value.delta !== null && (typeof value.delta !== 'number' || !Number.isFinite(value.delta))) return null
  if (value.currency !== undefined && value.currency !== null && typeof value.currency !== 'string') return null

  return {
    status: value.status,
    trust_impact: value.trust_impact,
    message: value.message,
    affected_fields: [...value.affected_fields],
    ...(observed !== undefined ? { observed } : {}),
    ...(comparison !== undefined ? { comparison } : {}),
    ...(value.delta !== undefined ? { delta: value.delta } : {}),
    ...(value.currency !== undefined ? { currency: value.currency } : {}),
  }
}

function sanitizeImportAdmissionReviewDisposition(value: unknown): ImportAdmissionReviewDispositionV1 | null {
  if (!isPlainRecord(value)) return null
  if (value.schema_version !== 'import_admission_review_disposition_v1') return null
  if (!isNonEmptyString(value.check_id)) return null
  if (value.disposition !== 'accepted_known_exception' && value.disposition !== 'needs_source_correction' && value.disposition !== 'deferred') return null
  if (!isNonEmptyString(value.rationale)) return null
  if (!isNonEmptyString(value.reviewed_at)) return null
  if (!isNonEmptyString(value.reviewer_label)) return null
  if (!isNonEmptyString(value.snapshot_fingerprint)) return null
  if (!isNonEmptyString(value.admission_summary_fingerprint)) return null
  const evidenceSummary = sanitizeImportAdmissionEvidenceSummary(value.evidence_summary)
  if (!evidenceSummary) return null

  return {
    schema_version: 'import_admission_review_disposition_v1',
    check_id: value.check_id,
    disposition: value.disposition,
    rationale: value.rationale,
    reviewed_at: value.reviewed_at,
    reviewer_label: value.reviewer_label,
    snapshot_fingerprint: value.snapshot_fingerprint,
    admission_summary_fingerprint: value.admission_summary_fingerprint,
    evidence_summary: evidenceSummary,
  }
}

function sanitizeImportAdmissionReviewDispositions(value: unknown): Record<string, ImportAdmissionReviewDispositionV1> | undefined {
  if (!isPlainRecord(value)) return undefined
  const sanitizedEntries = Object.entries(value).flatMap(([checkId, disposition]) => {
    const sanitizedDisposition = sanitizeImportAdmissionReviewDisposition(disposition)
    if (!sanitizedDisposition || sanitizedDisposition.check_id !== checkId) return []
    return [[checkId, sanitizedDisposition] as const]
  })
  return sanitizedEntries.length > 0 ? Object.fromEntries(sanitizedEntries) : undefined
}

function sanitizeImportedNodeSource(value: ImportedNodeSource): ImportedNodeSource {
  const source: ImportedNodeSource = {
    importedFileNames: Array.isArray(value.importedFileNames) ? value.importedFileNames.filter((fileName) => typeof fileName === 'string') : [],
    importedAt: typeof value.importedAt === 'string' ? value.importedAt : '',
    importer: value.importer ?? null,
    baseCurrency: value.baseCurrency ?? null,
    historySource: structuredClone(value.historySource),
  }
  if (value.admissionSummary !== undefined) {
    source.admissionSummary = structuredClone(value.admissionSummary)
  }
  const sanitizedDispositions = sanitizeImportAdmissionReviewDispositions(value.admissionReviewDispositions)
  if (sanitizedDispositions) {
    source.admissionReviewDispositions = sanitizedDispositions
  }
  return source
}

function sanitizePortfolioWorkspaceForRead(workspace: PortfolioWorkspace): PortfolioWorkspace {
  if ('kind' in workspace.source) {
    return structuredClone(workspace)
  }
  return {
    ...structuredClone(workspace),
    source: sanitizeImportedNodeSource(workspace.source),
  }
}

function sanitizePortfolioNodeForRead(node: PortfolioNode): PortfolioNode {
  const clonedNode = structuredClone(node)
  if (!clonedNode.source) {
    return clonedNode
  }
  return {
    ...clonedNode,
    source: sanitizeImportedNodeSource(clonedNode.source),
  }
}

function assertValidImportAdmissionReviewDispositionForSave(input: {
  disposition: ImportAdmissionReviewDispositionV1
  admissionSummary: ImportAdmissionSummaryV1 | null | undefined
}) {
  const sanitizedDisposition = sanitizeImportAdmissionReviewDisposition(input.disposition)
  if (!sanitizedDisposition) {
    throw new Error('Import admission review metadata is malformed')
  }
  const matchingCheck = input.admissionSummary?.checks.find((check) => check.check_id === sanitizedDisposition.check_id) ?? null
  if (!matchingCheck) {
    throw new Error('Import admission review metadata must reference an admission check')
  }
  if (matchingCheck.status === 'pass') {
    throw new Error('Import admission review metadata can only be saved for non-pass checks')
  }
  const nonPassCheck = matchingCheck as NonPassImportAdmissionCheckV1
  if (!importAdmissionEvidenceSummariesMatch(sanitizedDisposition.evidence_summary, nonPassCheck)) {
    throw new Error('Import admission review metadata evidence must match current admission check evidence')
  }
  return sanitizedDisposition
}

export function canonicalizeForFingerprint(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalizeForFingerprint)
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, nestedValue]) => [key, canonicalizeForFingerprint(nestedValue)]))
  }
  return value
}

export function buildDeterministicImportAdmissionFingerprint(value: unknown, prefix: string) {
  return `${prefix}:${JSON.stringify(canonicalizeForFingerprint(value))}`
}

export function buildImportSnapshotFingerprint(input: {
  portfolioSnapshot?: PortfolioSnapshot | null
  importedSource?: ImportedNodeSource | null
}) {
  const source = input.importedSource
  return buildDeterministicImportAdmissionFingerprint({
    importedMeta: input.portfolioSnapshot?.importedMeta ?? null,
    importedFileNames: source?.importedFileNames ?? [],
    importedAt: source?.importedAt ?? null,
    importer: source?.importer ?? null,
    baseCurrency: source?.baseCurrency ?? input.portfolioSnapshot?.baseCurrency ?? null,
    historySourceKind: source?.historySource.kind ?? null,
  }, 'import_snapshot')
}

export function buildImportAdmissionSummaryFingerprint(summary: ImportAdmissionSummaryV1 | null | undefined) {
  return buildDeterministicImportAdmissionFingerprint(summary ?? null, 'import_admission_summary')
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
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
      admissionSummary: input.analysis.admission_summary ?? null,
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
    selectedExposureSnapshotId: rootNodeId,
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
    request.onsuccess = () => resolve(request.result ? sanitizePortfolioWorkspaceForRead(request.result as PortfolioWorkspace) : null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace'))
  })
}

export async function getNode(nodeId: string) {
  return withStore<PortfolioNode | null>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(nodeId)
    request.onsuccess = () => resolve(request.result ? sanitizePortfolioNodeForRead(request.result as PortfolioNode) : null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load node'))
  })
}

export async function saveImportAdmissionReviewDisposition(input: {
  workspaceId: string
  nodeId?: string | null
  disposition: ImportAdmissionReviewDispositionV1
}) {
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found')
  const targetNode = input.nodeId ? await getNode(input.nodeId) : null
  if (input.nodeId && !targetNode) throw new Error('Import admission review metadata target node not found')
  if (targetNode && targetNode.workspaceId !== input.workspaceId) {
    throw new Error('Import admission review metadata target node does not belong to supplied workspace')
  }
  if (targetNode && targetNode.kind !== 'imported_base' && targetNode.kind !== 'imported_snapshot') {
    throw new Error('Import admission review metadata can only be saved on imported source nodes')
  }
  const admissionSummary = targetNode?.kind === 'imported_snapshot'
    ? targetNode.source?.admissionSummary
    : !('kind' in workspace.source)
      ? workspace.source.admissionSummary
      : null
  const disposition = assertValidImportAdmissionReviewDispositionForSave({
    disposition: input.disposition,
    admissionSummary,
  })
  const now = new Date().toISOString()

  if (targetNode?.kind === 'imported_snapshot' && targetNode.source) {
    const nextSource: ImportedNodeSource = {
      ...targetNode.source,
      admissionReviewDispositions: {
        ...(targetNode.source.admissionReviewDispositions ?? {}),
        [disposition.check_id]: disposition,
      },
    }
    const nextNode: PortfolioNode = {
      ...targetNode,
      source: nextSource,
    }
    await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
      const request = store.put(nextNode)
      request.onsuccess = () => resolve(undefined)
      request.onerror = () => reject(request.error ?? new Error('Failed to save import admission review metadata'))
    })
    return { workspace, node: nextNode }
  }

  if ('kind' in workspace.source) {
    throw new Error('Import admission review metadata requires an imported workspace source')
  }

  const nextWorkspace: PortfolioWorkspace = {
    ...workspace,
    updatedAt: now,
    source: {
      ...workspace.source,
      admissionReviewDispositions: {
        ...(workspace.source.admissionReviewDispositions ?? {}),
        [disposition.check_id]: disposition,
      },
    },
  }

  await withStore<void>(workspaceStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(nextWorkspace)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save import admission review metadata'))
  })

  return { workspace: nextWorkspace, node: targetNode }
}

export async function getWorkspaceNodes(workspaceId: string) {
  return withStore<PortfolioNode[]>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve(((request.result as PortfolioNode[]) ?? []).map(sanitizePortfolioNodeForRead))
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

export async function createDraftFromNode(input: { workspaceId: string; baseNodeId: string; name?: string }) {
  const node = await getNode(input.baseNodeId)
  if (!node) throw new Error('Base node not found')
  if (!node.portfolioSnapshot) throw new Error('Base node does not contain a portfolio snapshot')
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
  return draft
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

export async function saveImportedSnapshotNode(input: {
  workspaceId: string
  parentNodeId: string
  portfolioSnapshot: PortfolioSnapshot
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  admissionSummary?: ImportAdmissionSummaryV1 | null
  name: string
}) {
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found')

  const parentNode = await getNode(input.parentNodeId)
  if (!parentNode) throw new Error('Parent node not found')
  if (!parentNode.portfolioSnapshot) throw new Error('Parent node snapshot not found')

  const source: ImportedNodeSource = buildPersistedImportedSource({
    importedFileNames: input.importedFileNames,
    importedAt: input.portfolioSnapshot.importedMeta.importedAt,
    importer: input.portfolioSnapshot.importedMeta.importer,
    baseCurrency: input.portfolioSnapshot.baseCurrency,
    historyContext: input.historyContext ?? null,
    importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    admissionSummary: input.admissionSummary ?? workspace.source.admissionSummary ?? null,
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
  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).clear()
    transaction.objectStore(portfolioNodeStoreName).clear()
    transaction.objectStore(workingDraftStoreName).clear()
    transaction.objectStore(workspaceStateStoreName).clear()
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
