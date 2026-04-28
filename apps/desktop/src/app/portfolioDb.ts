const databaseName = 'portfolio-workstation'
const databaseVersion = 17

export const appStateStoreName = 'app-state'
export const workspaceStoreName = 'workspaces'
export const portfolioNodeStoreName = 'portfolio_nodes'
export const workingDraftStoreName = 'working_drafts'
export const workspaceStateStoreName = 'workspace_state'
export const candidateImprovementDraftStoreName = 'candidate_improvement_drafts'
export const intentBoundSeededEtfReplacementRankingDraftStoreName = 'intent_bound_seeded_etf_replacement_ranking_drafts'
export const replacementIntentDraftStoreName = 'replacement_intent_drafts'
export const formedCandidateStoreName = 'formed_candidate_drafts'
export const constructedCandidateStoreName = 'constructed_candidate_drafts'
export const constructionConstraintValidationStoreName = 'construction_constraint_validation_drafts'
export const selectedConstructionRuleStoreName = 'selected_construction_rule_drafts'
export const hypotheticalReplacementReplayDraftStoreName = 'hypothetical_replacement_replay_drafts'
export const versionedProposalStoreName = 'versioned_proposals'
export const activeThesisStoreName = 'active_thesis'
export const persistedConstructionArtifactReviewStoreName = 'persisted_construction_artifact_reviews'
export const persistedOptimizerHandoffReviewStoreName = 'persisted_optimizer_handoff_reviews'
export const reviewSnapshotArtifactStoreName = 'review_snapshot_artifacts'

let databasePromise: Promise<IDBDatabase> | null = null
let openDatabaseHandle: IDBDatabase | null = null

export function getPortfolioDatabaseName() {
  return databaseName
}

export function getIndexedDb() {
  return globalThis.indexedDB
}

export function openPortfolioDatabase() {
  if (!getIndexedDb()) {
    return Promise.reject(new Error('IndexedDB unavailable'))
  }

  if (!databasePromise) {
    databasePromise = new Promise((resolve, reject) => {
      const request = getIndexedDb().open(databaseName, databaseVersion)

      request.onupgradeneeded = (event) => {
        const database = request.result
        const oldVersion = event.oldVersion

        if (request.transaction && oldVersion < 3) {
          const storeNames = [
            appStateStoreName,
            workspaceStoreName,
            portfolioNodeStoreName,
            workingDraftStoreName,
            workspaceStateStoreName,
            candidateImprovementDraftStoreName,
            intentBoundSeededEtfReplacementRankingDraftStoreName,
            replacementIntentDraftStoreName,
            formedCandidateStoreName,
            constructedCandidateStoreName,
            constructionConstraintValidationStoreName,
            selectedConstructionRuleStoreName,
            hypotheticalReplacementReplayDraftStoreName,
            versionedProposalStoreName,
            activeThesisStoreName,
            persistedConstructionArtifactReviewStoreName,
            persistedOptimizerHandoffReviewStoreName,
            reviewSnapshotArtifactStoreName,
          ]

          for (const storeName of storeNames) {
            if (database.objectStoreNames.contains(storeName)) {
              database.deleteObjectStore(storeName)
            }
          }
        }

        if (!database.objectStoreNames.contains(appStateStoreName)) {
          database.createObjectStore(appStateStoreName, { keyPath: 'id' })
        }
        if (!database.objectStoreNames.contains(workspaceStoreName)) {
          database.createObjectStore(workspaceStoreName, { keyPath: 'id' })
        }
        if (!database.objectStoreNames.contains(portfolioNodeStoreName)) {
          const store = database.createObjectStore(portfolioNodeStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
          store.createIndex('parentId', 'parentId', { unique: false })
        }
        if (!database.objectStoreNames.contains(workingDraftStoreName)) {
          const store = database.createObjectStore(workingDraftStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(workspaceStateStoreName)) {
          database.createObjectStore(workspaceStateStoreName, { keyPath: 'workspaceId' })
        }
        if (!database.objectStoreNames.contains(candidateImprovementDraftStoreName)) {
          const store = database.createObjectStore(candidateImprovementDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(intentBoundSeededEtfReplacementRankingDraftStoreName)) {
          const store = database.createObjectStore(intentBoundSeededEtfReplacementRankingDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(replacementIntentDraftStoreName)) {
          const store = database.createObjectStore(replacementIntentDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(formedCandidateStoreName)) {
          const store = database.createObjectStore(formedCandidateStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(constructedCandidateStoreName)) {
          const store = database.createObjectStore(constructedCandidateStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(constructionConstraintValidationStoreName)) {
          const store = database.createObjectStore(constructionConstraintValidationStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(selectedConstructionRuleStoreName)) {
          const store = database.createObjectStore(selectedConstructionRuleStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(hypotheticalReplacementReplayDraftStoreName)) {
          const store = database.createObjectStore(hypotheticalReplacementReplayDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(versionedProposalStoreName)) {
          const store = database.createObjectStore(versionedProposalStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(activeThesisStoreName)) {
          database.createObjectStore(activeThesisStoreName, { keyPath: 'workspaceId' })
        }
        if (!database.objectStoreNames.contains(persistedConstructionArtifactReviewStoreName)) {
          const store = database.createObjectStore(persistedConstructionArtifactReviewStoreName, { keyPath: 'workspaceId' })
          store.createIndex('constructionArtifactId', 'constructionArtifactId', { unique: false })
        }
        if (!database.objectStoreNames.contains(persistedOptimizerHandoffReviewStoreName)) {
          const store = database.createObjectStore(persistedOptimizerHandoffReviewStoreName, { keyPath: 'workspaceId' })
          store.createIndex('handoffId', 'handoffReference.handoff_id', { unique: false })
          store.createIndex('artifactId', 'handoffReference.artifact_id', { unique: false })
        }
        if (!database.objectStoreNames.contains(reviewSnapshotArtifactStoreName)) {
          const store = database.createObjectStore(reviewSnapshotArtifactStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
          store.createIndex('reviewSnapshotArtifactId', 'reviewSnapshotArtifactId', { unique: false })
        }
      }

      request.onsuccess = () => {
        openDatabaseHandle = request.result
        openDatabaseHandle.onclose = () => {
          if (openDatabaseHandle === request.result) {
            openDatabaseHandle = null
          }
        }
        resolve(request.result)
      }
      request.onerror = () => reject(request.error ?? new Error('Failed to open IndexedDB'))
    })
  }

  return databasePromise
}

export function deletePortfolioDatabase() {
  if (!getIndexedDb()) {
    return Promise.reject(new Error('IndexedDB unavailable'))
  }

  if (openDatabaseHandle) {
    openDatabaseHandle.close()
    openDatabaseHandle = null
  }

  databasePromise = null

  return new Promise<void>((resolve, reject) => {
    const request = getIndexedDb().deleteDatabase(databaseName)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error ?? new Error('Failed to delete IndexedDB database'))
    request.onblocked = () => reject(new Error('IndexedDB deletion blocked by an open connection'))
  })
}

export function withStore<T>(storeName: string, mode: IDBTransactionMode, handler: (store: IDBObjectStore, resolve: (value: T) => void, reject: (reason?: unknown) => void) => void) {
  return openPortfolioDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(storeName, mode)
    const store = transaction.objectStore(storeName)

    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    handler(store, resolve, reject)
  }))
}

export function withStores<T>(storeNames: string[], mode: IDBTransactionMode, handler: (transaction: IDBTransaction, resolve: (value: T) => void, reject: (reason?: unknown) => void) => void) {
  return openPortfolioDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(storeNames, mode)
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    handler(transaction, resolve, reject)
  }))
}
