import { describe, expect, it } from 'vitest'

import {
  missingPersistedStartupNodeRestoreMessage,
  resolveImportedWorkspaceStartupTruth,
  assertValidStartupSelection,
  isValidStartupDraftActiveNodeFallback,
  missingPersistedStartupDraftRestoreMessage,
  missingPersistedStartupSelectedSnapshotRestoreMessage,
} from './startupSelectionValidation'

describe('isValidStartupDraftActiveNodeFallback', () => {
  it('returns true for a persisted draft selection when the restored draft matches the active draft and its base node matches the restored imported snapshot node', () => {
    expect(isValidStartupDraftActiveNodeFallback({
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toBe(true)
  })

  it('returns false when the restored active node kind is not an imported workspace base or snapshot node', () => {
    expect(isValidStartupDraftActiveNodeFallback({
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'variant' },
    })).toBe(false)
  })

  it('returns true for a persisted draft selection when the restored draft matches an imported base active node', () => {
    expect(isValidStartupDraftActiveNodeFallback({
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_base' },
    })).toBe(true)
  })

  it('returns false when the restored draft base node does not match the restored active node', () => {
    expect(isValidStartupDraftActiveNodeFallback({
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-2', kind: 'imported_snapshot' },
    })).toBe(false)
  })

  it('returns false when the restored draft does not match the active draft id even if its base node matches the restored active node', () => {
    expect(isValidStartupDraftActiveNodeFallback({
      restoredWorkspaceState: {
        activeDraftId: 'draft-2',
        selectedExposureSnapshotId: 'draft',
      },
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toBe(false)
  })
})

describe('assertValidStartupSelection', () => {
  it('accepts a valid authoritative node id selection', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: null,
        selectedExposureSnapshotId: 'node-1',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: null,
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).not.toThrow()
  })

  it('rejects a restored active node missing from authoritative imported nodes', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: null,
        selectedExposureSnapshotId: 'node-1',
      },
      authoritativeNodes: [{ id: 'node-2' }],
      restoredDraft: null,
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toThrow(missingPersistedStartupNodeRestoreMessage)
  })

  it('accepts a valid draft selection', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).not.toThrow()
  })

  it('accepts a valid draft selection rooted to an imported base active node', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_base' },
    })).not.toThrow()
  })

  it('rejects a missing authoritative node id selection', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: null,
        selectedExposureSnapshotId: 'missing-node',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: null,
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toThrow(missingPersistedStartupSelectedSnapshotRestoreMessage)
  })

  it('rejects a missing restored draft for a persisted draft selection', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: null,
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toThrow(missingPersistedStartupDraftRestoreMessage)
  })

  it('rejects a restored draft when the active draft id does not match', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-2',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toThrow(missingPersistedStartupDraftRestoreMessage)
  })

  it('rejects a restored draft when its base node does not match the restored active node', () => {
    expect(() => assertValidStartupSelection({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-2' }],
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-2', kind: 'imported_snapshot' },
    })).toThrow(missingPersistedStartupDraftRestoreMessage)
  })
})

describe('resolveImportedWorkspaceStartupTruth', () => {
  it('keeps a matching imported draft while forcing dashboard startup selection to the restored active node', () => {
    expect(resolveImportedWorkspaceStartupTruth({
      sessionRestored: true,
      isImportedWorkspace: true,
      restoredWorkspaceState: {
        activeDraftId: 'draft-1',
        selectedExposureSnapshotId: 'draft',
      },
      authoritativeNodes: [{ id: 'node-1' }],
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      restoredActiveNode: { id: 'node-1', kind: 'imported_snapshot' },
    })).toEqual({
      restoredDraft: { id: 'draft-1', baseNodeId: 'node-1' },
      dashboardSelectedSnapshotId: 'node-1',
    })
  })
})
