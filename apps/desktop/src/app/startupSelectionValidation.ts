import type { PortfolioNode, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

export const missingPersistedStartupDraftRestoreMessage = 'Unable to restore previous portfolio workspace: persisted draft selected on startup is missing'
export const missingPersistedStartupNodeRestoreMessage = 'Unable to restore previous portfolio workspace: persisted startup node is missing from authoritative workspace state'
export const missingPersistedStartupSelectedSnapshotRestoreMessage = 'Unable to restore previous portfolio workspace: persisted startup selected snapshot is missing from authoritative workspace state'

type StartupSelectionValidationInput<TRestoredDraft extends Pick<WorkingDraft, 'id' | 'baseNodeId'> | null = Pick<WorkingDraft, 'id' | 'baseNodeId'> | null> = {
  sessionRestored: boolean
  isImportedWorkspace: boolean
  restoredWorkspaceState: Pick<WorkspaceState, 'activeDraftId' | 'selectedExposureSnapshotId'>
  authoritativeNodes: Array<Pick<PortfolioNode, 'id'>>
  restoredDraft: TRestoredDraft
  restoredActiveNode: Pick<PortfolioNode, 'id' | 'kind'>
}

function isImportedWorkspaceDraftBaseNodeKind(kind: PortfolioNode['kind']) {
  return kind === 'imported_base' || kind === 'imported_snapshot'
}

function resolveRestorableImportedWorkspaceDraft<TRestoredDraft extends Pick<WorkingDraft, 'id' | 'baseNodeId'> | null>(
  input: Pick<StartupSelectionValidationInput<TRestoredDraft>, 'restoredWorkspaceState' | 'restoredDraft' | 'restoredActiveNode'>,
) {
  return isImportedWorkspaceDraftBaseNodeKind(input.restoredActiveNode.kind)
    && input.restoredDraft != null
    && input.restoredWorkspaceState.activeDraftId === input.restoredDraft.id
    && input.restoredDraft.baseNodeId === input.restoredActiveNode.id
    ? input.restoredDraft
    : null
}

export function isValidStartupDraftActiveNodeFallback(input: Pick<StartupSelectionValidationInput, 'restoredWorkspaceState' | 'restoredDraft' | 'restoredActiveNode'>) {
  return input.restoredWorkspaceState.selectedExposureSnapshotId === 'draft'
    && resolveRestorableImportedWorkspaceDraft(input) != null
}

export function resolveImportedWorkspaceStartupTruth<TRestoredDraft extends Pick<WorkingDraft, 'id' | 'baseNodeId'> | null>(
  input: StartupSelectionValidationInput<TRestoredDraft>,
) {
  assertValidStartupSelection(input)

  return {
    restoredDraft: input.sessionRestored && input.isImportedWorkspace
      ? resolveRestorableImportedWorkspaceDraft(input)
      : input.restoredDraft,
    dashboardSelectedSnapshotId: input.restoredActiveNode.id,
  }
}

export function assertValidStartupSelection(input: StartupSelectionValidationInput) {
  if (!input.sessionRestored) {
    return
  }

  const { selectedExposureSnapshotId, activeDraftId } = input.restoredWorkspaceState

  if (
    input.isImportedWorkspace
    && !input.authoritativeNodes.some((node) => node.id === input.restoredActiveNode.id)
  ) {
    throw new Error(missingPersistedStartupNodeRestoreMessage)
  }

  if (
    input.isImportedWorkspace
    && selectedExposureSnapshotId
    && selectedExposureSnapshotId !== 'draft'
    && !input.authoritativeNodes.some((node) => node.id === selectedExposureSnapshotId)
  ) {
    throw new Error(missingPersistedStartupSelectedSnapshotRestoreMessage)
  }

  if (selectedExposureSnapshotId !== 'draft') {
    return
  }

  const restoredDraft = resolveRestorableImportedWorkspaceDraft(input)

  if (!restoredDraft || activeDraftId !== restoredDraft.id) {
    throw new Error(missingPersistedStartupDraftRestoreMessage)
  }
}
