import { describe, expect, it, vi, afterEach } from 'vitest'
import { ApiError, asBool, get, post, query } from './client'

function respond(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }))
}

afterEach(() => vi.unstubAllGlobals())

describe('the API client', () => {
  it('normalises the two different error bodies the API can return', async () => {
    // 400/404/503 use {detail: string}; FastAPI's own validation uses {detail: [...]}.
    vi.stubGlobal('fetch', () => respond(404, { detail: "Unknown game 'nope'" }))
    await expect(get('/api/pokemon?game=nope')).rejects.toMatchObject({
      kind: 'not_found',
      status: 404,
      message: "Unknown game 'nope'",
      fields: [],
    })

    vi.stubGlobal('fetch', () =>
      respond(422, { detail: [{ loc: ['body', 'context', 'team'], msg: 'List should have at most 6 items', type: 'too_long' }] }),
    )
    const error = await post('/api/team/analyze', {}).catch((e: ApiError) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).kind).toBe('validation')
    expect((error as ApiError).fields).toEqual([{ path: 'context.team', message: 'List should have at most 6 items' }])
  })

  it('distinguishes an unreachable server from a missing database', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')))
    const offline = await get('/api/games').catch((e: ApiError) => e)
    expect((offline as ApiError).kind).toBe('offline')
    expect((offline as ApiError).retryable).toBe(true)

    vi.stubGlobal('fetch', () => respond(503, { detail: 'Database not found' }))
    const missing = await get('/api/games').catch((e: ApiError) => e)
    expect((missing as ApiError).kind).toBe('database_missing')
    expect((missing as ApiError).retryable).toBe(true)
  })

  it('does not retry what the caller must change', async () => {
    vi.stubGlobal('fetch', () => respond(400, { detail: 'Type does not exist in generation 1' }))
    const semantic = await get('/api/type-effectiveness').catch((e: ApiError) => e)
    expect((semantic as ApiError).retryable).toBe(false)
  })

  it('drops unset query parameters so cache keys stay stable', () => {
    expect(query({ game: 'emerald', q: undefined, type: '', limit: 50, offset: 0 })).toBe('?game=emerald&limit=50&offset=0')
    expect(query({})).toBe('')
  })

  it('absorbs the API’s mixed 0/1 and boolean columns', () => {
    expect([asBool(1), asBool(true)]).toEqual([true, true])
    expect([asBool(0), asBool(false), asBool(null), asBool(undefined)]).toEqual([false, false, false, false])
  })
})
