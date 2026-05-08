import { useEffect, useRef, useState } from 'react'
import type { GenericRankingArtifact, GenericRankingArtifactRecentRow, GenericRankingRequest } from './types'

const API_BASE = '/api'

async function readJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(
      typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string'
        ? payload.detail
        : fallbackMessage,
    )
  }
  return payload as T
}

export interface GenericRankingState {
  // Run state
  runLoading: boolean
  runError: string | null
  result: GenericRankingArtifact | null
  resultSource: 'fresh' | 'recent' | null

  // Recent runs state
  recentRunsLoading: boolean
  recentRunsError: string | null
  recentRuns: GenericRankingArtifactRecentRow[]

  // Artifact load state
  artifactLoadingId: string | null
  artifactLoadError: string | null

  // Actions
  runRanking: (request: GenericRankingRequest) => void
  loadRecentRuns: () => void
  loadRecentArtifact: (artifactId: string) => void
}

export function useGenericRanking(): GenericRankingState {
  const resultRequestOwnerRef = useRef(0)

  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [result, setResult] = useState<GenericRankingArtifact | null>(null)
  const [resultSource, setResultSource] = useState<'fresh' | 'recent' | null>(null)

  const [recentRunsLoading, setRecentRunsLoading] = useState(false)
  const [recentRunsError, setRecentRunsError] = useState<string | null>(null)
  const [recentRuns, setRecentRuns] = useState<GenericRankingArtifactRecentRow[]>([])

  const [artifactLoadingId, setArtifactLoadingId] = useState<string | null>(null)
  const [artifactLoadError, setArtifactLoadError] = useState<string | null>(null)

  function beginResultRequest(nextSource: 'fresh' | 'recent', artifactId?: string) {
    const owner = resultRequestOwnerRef.current + 1
    resultRequestOwnerRef.current = owner
    setRunLoading(nextSource === 'fresh')
    setArtifactLoadingId(nextSource === 'recent' ? (artifactId ?? null) : null)
    setRunError(null)
    setArtifactLoadError(null)
    return owner
  }

  function isActiveResultRequest(owner: number) {
    return resultRequestOwnerRef.current === owner
  }

  async function fetchRecentRuns() {
    setRecentRunsLoading(true)
    setRecentRunsError(null)
    try {
      const response = await fetch(`${API_BASE}/strategy-lab/ranking/artifacts/recent`)
      const payload = await readJsonResponse<GenericRankingArtifactRecentRow[]>(
        response,
        'Recent generic ranking runs are unavailable',
      )
      setRecentRuns(payload)
    } catch (caught) {
      setRecentRuns([])
      setRecentRunsError(caught instanceof Error ? caught.message : 'Recent generic ranking runs are unavailable')
    } finally {
      setRecentRunsLoading(false)
    }
  }

  async function runRanking(request: GenericRankingRequest) {
    const owner = beginResultRequest('fresh')
    try {
      const response = await fetch(`${API_BASE}/strategy-lab/ranking/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      const payload = await readJsonResponse<GenericRankingArtifact>(response, 'Generic ranking request failed')
      if (!isActiveResultRequest(owner)) return
      setResult(payload)
      setResultSource('fresh')
      setRunLoading(false)
      void fetchRecentRuns()
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setRunError(caught instanceof Error ? caught.message : 'Generic ranking request failed')
      setRunLoading(false)
    } finally {
      if (isActiveResultRequest(owner)) {
        setRunLoading(false)
      }
    }
  }

  async function loadRecentArtifact(artifactId: string) {
    const owner = beginResultRequest('recent', artifactId)
    try {
      const response = await fetch(
        `${API_BASE}/strategy-lab/ranking/artifacts/${encodeURIComponent(artifactId)}`,
      )
      const payload = await readJsonResponse<GenericRankingArtifact>(
        response,
        'Generic ranking artifact could not be loaded',
      )
      if (!isActiveResultRequest(owner)) return
      setResult(payload)
      setResultSource('recent')
      setArtifactLoadingId(null)
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setArtifactLoadError(
        caught instanceof Error ? caught.message : 'Generic ranking artifact could not be loaded',
      )
      setArtifactLoadingId(null)
    } finally {
      if (isActiveResultRequest(owner)) {
        setArtifactLoadingId(null)
      }
    }
  }

  useEffect(() => {
    void fetchRecentRuns()
  }, [])

  return {
    runLoading,
    runError,
    result,
    resultSource,
    recentRunsLoading,
    recentRunsError,
    recentRuns,
    artifactLoadingId,
    artifactLoadError,
    runRanking: (request) => { void runRanking(request) },
    loadRecentRuns: () => { void fetchRecentRuns() },
    loadRecentArtifact: (artifactId) => { void loadRecentArtifact(artifactId) },
  }
}
