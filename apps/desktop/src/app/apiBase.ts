const desktopApiOriginFallback = 'http://127.0.0.1:8000'

export type ResolveDesktopApiUrlOptions = {
  isDev?: boolean
  desktopApiOrigin?: string | null
}

function normalizeDesktopApiOrigin(origin: string | null | undefined) {
  const candidate = origin?.trim()
  if (!candidate) return null

  try {
    const parsed = new URL(candidate)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null
    }
    return parsed.origin
  } catch {
    return null
  }
}

export function resolveDesktopApiUrl(path: string, options: ResolveDesktopApiUrlOptions = {}) {
  const isDev = options.isDev ?? import.meta.env.DEV
  if (isDev) {
    return path
  }

  const backendOrigin = normalizeDesktopApiOrigin(options.desktopApiOrigin ?? import.meta.env.VITE_DESKTOP_API_ORIGIN)
    ?? desktopApiOriginFallback

  return new URL(path, `${backendOrigin}/`).toString()
}
