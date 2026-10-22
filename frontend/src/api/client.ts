const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // not JSON: fall through
  }
  return `שגיאה ${res.status}`
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** A list answer plus the total number of matches, which the server sends in X-Total-Count. */
export async function apiWithTotal<T extends unknown[]>(path: string): Promise<{ items: T; total: number }> {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  const items = (await res.json()) as T
  const total = Number(res.headers.get('X-Total-Count'))
  return { items, total: Number.isFinite(total) && res.headers.has('X-Total-Count') ? total : items.length }
}

export function jsonBody(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export const pageImageUrl = (pageId: string, original = false) =>
  `${BASE}/pages/${pageId}/image${original ? '?original=true' : ''}`
