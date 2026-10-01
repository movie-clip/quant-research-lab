import { vi } from 'vitest'

/** Fetch/Response helpers shared by the App-level specs (extracted from App.test.tsx, unchanged). */
export function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Selecting an Exposure snapshot fires runDriftEngine; most App tests don't
// register that route, so it previously fell through and logged a noisy
// "[drift] FAILED: Unhandled fetch" (the app swallows the error, tests still
// pass). Serve a harmless unavailable DriftResult here so the stub honestly
// models what the app calls. Genuinely-unknown routes still throw (safety net).
const _driftFallbackPayload = {
  windows: [],
  benchmark_symbol: 'SPY',
  daily_series: [],
  availability: 'unavailable' as const,
}

export function unhandledOrDrift(pathname: string, method: string): Response {
  if (pathname === '/api/engines/drift/run' && method === 'POST') {
    return jsonResponse(_driftFallbackPayload)
  }
  throw new Error(`Unhandled fetch: ${method} ${pathname}`)
}

function requestUrl(input: RequestInfo | URL) {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  return new URL(rawUrl, 'http://localhost')
}

export function requestPathname(input: RequestInfo | URL) {
  return requestUrl(input).pathname
}

export function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  if (init?.method) return init.method.toUpperCase()
  if (typeof input !== 'string' && !(input instanceof URL) && input.method) return input.method.toUpperCase()
  return 'GET'
}

export function requestJsonBody(init?: RequestInit) {
  return JSON.parse(typeof init?.body === 'string' ? init.body : String(init?.body ?? '{}'))
}

export function matchingFetchCalls(fetchMock: { mock: { calls: ReadonlyArray<ReadonlyArray<unknown>> } }, pathname: string, method?: string) {
  return fetchMock.mock.calls.filter((call) => {
    const input = call[0] as RequestInfo | URL
    const init = call[1] as RequestInit | undefined
    return requestPathname(input) === pathname
      && (method == null || requestMethod(input, init) === method.toUpperCase())
  }) as Array<[RequestInfo | URL, RequestInit | undefined]>
}

export function installFetchMock(handler: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    return await handler(input, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
