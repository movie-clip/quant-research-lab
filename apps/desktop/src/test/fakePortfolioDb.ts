import { vi } from 'vitest'

import * as portfolioDb from '../app/portfolioDb'

/**
 * Minimal in-memory stand-in for IndexedDB, backing both `withStore` and `withStores` from a single
 * shared map so a value written through one entry point (e.g. createWorkspaceFromImport's `withStores`
 * transaction) is readable through the other (e.g. saveImportedSnapshotNode's `withStore` reads).
 * Real cross-function flows in portfolioWorkspaceStorage mix both.
 *
 * Reuse this instead of an ad hoc store stub when a test needs more than one storage function to see
 * the same data, or when it needs to prove that a code path did NOT write (`writes` records every put,
 * delete and clear; `seed` places saved data without recording a write).
 */
export type FakeDbWrite = { store: string; op: 'put' | 'delete' | 'clear'; key: string | null }

export function createFakePortfolioDb() {
  const stores = new Map<string, Map<string, unknown>>()
  const writes: FakeDbWrite[] = []

  function storeFor(name: string) {
    if (!stores.has(name)) stores.set(name, new Map())
    return stores.get(name)!
  }

  function keyFor(value: unknown): string {
    const v = value as { id?: string; workspaceId?: string }
    return v.id ?? v.workspaceId ?? ''
  }

  function settled<T>(result?: T) {
    const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result }
    queueMicrotask(() => request.onsuccess?.())
    return request as unknown as IDBRequest
  }

  function makeStoreApi(name: string) {
    const map = storeFor(name)
    return {
      get(key: string) {
        return settled(map.get(key))
      },
      put(value: unknown) {
        const key = keyFor(value)
        writes.push({ store: name, op: 'put', key })
        map.set(key, structuredClone(value))
        return settled()
      },
      delete(key: string) {
        writes.push({ store: name, op: 'delete', key })
        map.delete(key)
        return settled()
      },
      clear() {
        writes.push({ store: name, op: 'clear', key: null })
        map.clear()
        return settled()
      },
      index(_indexName: string) {
        return {
          getAll(key: string) {
            return settled(Array.from(map.values()).filter((v) => (v as { workspaceId?: string }).workspaceId === key))
          },
        }
      },
    } as unknown as IDBObjectStore
  }

  return {
    stores,
    writes,
    /** Place already-saved data in a store without recording a write. */
    seed(storeName: string, value: unknown) {
      storeFor(storeName).set(keyFor(value), structuredClone(value))
    },
    /** Read back a stored value as saved (no sanitising). */
    read<T>(storeName: string, key: string): T | undefined {
      return storeFor(storeName).get(key) as T | undefined
    },
    install() {
      vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
        return new Promise((resolve, reject) => handler(makeStoreApi(storeName), resolve, reject))
      })
      vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
        const transaction = { objectStore: (name: string) => makeStoreApi(name) } as unknown as IDBTransaction
        return new Promise((resolve, reject) => handler(transaction, resolve, reject))
      })
    },
  }
}
