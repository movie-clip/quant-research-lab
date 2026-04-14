import type { ExposureFactorModelResponse, ImportedExposureFactorModelSource, ImportedPortfolioSnapshotSource } from '../features/portfolio/types'

export type PersistedImportSession = {
  files: File[]
  analysis: ImportedPortfolioSnapshotSource & ImportedExposureFactorModelSource
  factorModel: ExposureFactorModelResponse | null
  lastImportedFileNames: string[]
}

const databaseName = 'portfolio-workstation'
const storeName = 'app-state'
const sessionKey = 'portfolio-import-session'
const sessionSchemaVersion = 3

type StoredSessionRecord = PersistedImportSession & { id: string; schemaVersion?: number }

let databasePromise: Promise<IDBDatabase> | null = null

function getIndexedDb() {
  return globalThis.indexedDB
}

function openDatabase() {
  if (!getIndexedDb()) {
    return Promise.reject(new Error('IndexedDB unavailable'))
  }

  if (!databasePromise) {
    databasePromise = new Promise((resolve, reject) => {
      const request = getIndexedDb().open(databaseName, 1)

      request.onupgradeneeded = () => {
        const database = request.result
        if (!database.objectStoreNames.contains(storeName)) {
          database.createObjectStore(storeName, { keyPath: 'id' })
        }
      }

      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error ?? new Error('Failed to open IndexedDB'))
    })
  }

  return databasePromise
}

function withStore<T>(mode: IDBTransactionMode, handler: (store: IDBObjectStore, resolve: (value: T) => void, reject: (reason?: unknown) => void) => void) {
  return openDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(storeName, mode)
    const store = transaction.objectStore(storeName)

    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    handler(store, resolve, reject)
  }))
}

export async function loadImportSession(): Promise<PersistedImportSession | null> {
  if (!getIndexedDb()) {
    return null
  }

  return withStore<PersistedImportSession | null>('readonly', (store, resolve, reject) => {
    const request = store.get(sessionKey)
    request.onsuccess = () => {
      const record = request.result as StoredSessionRecord | undefined
      if (!record) {
        resolve(null)
        return
      }

      if ((record.schemaVersion ?? 1) !== sessionSchemaVersion) {
        resolve(null)
        return
      }

      resolve({
        files: record.files,
        analysis: record.analysis,
        factorModel: record.factorModel,
        lastImportedFileNames: record.lastImportedFileNames,
      })
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load import session'))
  })
}

export async function saveImportSession(session: PersistedImportSession): Promise<void> {
  if (!getIndexedDb()) {
    return
  }

  await withStore<void>('readwrite', (store, resolve, reject) => {
    const request = store.put({ id: sessionKey, schemaVersion: sessionSchemaVersion, ...session })
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error ?? new Error('Failed to save import session'))
  })
}

export async function clearImportSession(): Promise<void> {
  if (!getIndexedDb()) {
    return
  }

  await withStore<void>('readwrite', (store, resolve, reject) => {
    const request = store.delete(sessionKey)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error ?? new Error('Failed to clear import session'))
  })
}
