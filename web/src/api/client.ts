/**
 * The API client, and the one place every failure mode is given a name.
 *
 * Two error bodies exist: the handlers return `{detail: string}` for 400/404/503, while FastAPI's
 * own validation returns `{detail: [{loc, msg, type}]}` for 422. Both are normalised into `ApiError`
 * so no screen has to know the difference.
 */

import type { Envelope } from './types'

export type ApiErrorKind =
  | 'offline' // the request never reached a server
  | 'database_missing' // 503: the snapshot is not built, or is out of date
  | 'not_found' // 404
  | 'semantic' // 400: meaningless inside the requested game
  | 'validation' // 422
  | 'server' // 5xx other than 503

export interface FieldError {
  path: string
  message: string
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number
  readonly fields: FieldError[]

  constructor(kind: ApiErrorKind, status: number, message: string, fields: FieldError[] = []) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
    this.fields = fields
  }

  /** True when retrying could plausibly succeed without the caller changing anything. */
  get retryable(): boolean {
    return this.kind === 'offline' || this.kind === 'server' || this.kind === 'database_missing'
  }
}

const KIND_BY_STATUS: Record<number, ApiErrorKind> = {
  400: 'semantic',
  404: 'not_found',
  422: 'validation',
  503: 'database_missing',
}

function parseDetail(body: unknown): { message: string; fields: FieldError[] } {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return { message: detail, fields: [] }
    if (Array.isArray(detail)) {
      const fields = detail.map((entry) => {
        const e = entry as { loc?: unknown[]; msg?: string }
        const loc = Array.isArray(e.loc) ? e.loc.filter((p) => p !== 'body').join('.') : ''
        return { path: loc, message: e.msg ?? 'is invalid' }
      })
      const summary = fields.map((f) => (f.path ? `${f.path}: ${f.message}` : f.message)).join('; ')
      return { message: summary || 'The request was rejected.', fields }
    }
  }
  return { message: 'The request failed.', fields: [] }
}

export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError('offline', 0, 'Could not reach the Rotom Dex server.')
  }
  const text = await response.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  if (!response.ok) {
    const { message, fields } = parseDetail(body)
    const kind = KIND_BY_STATUS[response.status] ?? 'server'
    throw new ApiError(kind, response.status, message, fields)
  }
  return body as T
}

export function get<T>(path: string, signal?: AbortSignal): Promise<Envelope<T>> {
  return request<Envelope<T>>(path, { signal })
}

export function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<Envelope<T>> {
  return request<Envelope<T>>(path, { method: 'POST', body: JSON.stringify(body), signal })
}

export function plain<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal })
}

/** SQLite booleans reach us as 0/1 on most rows and as real booleans on a few. */
export function asBool(value: number | boolean | null | undefined): boolean {
  return value === true || value === 1
}

/** Build a query string, dropping anything unset so URLs stay stable as cache keys. */
export function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const rendered = search.toString()
  return rendered ? `?${rendered}` : ''
}
