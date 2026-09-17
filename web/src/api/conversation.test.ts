import { afterEach, expect, it, vi } from 'vitest'
import { askRotom, connectKey } from './conversation'

afterEach(() => vi.unstubAllGlobals())

it('distinguishes a stopped backend from an invalid Gemini key', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  await expect(connectKey('test-only-key')).rejects.toThrow('Cannot reach the Rotom server')
})

it('keeps provider errors and handles non-JSON proxy failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Gemini quota reached'}),{status:503})))
  await expect(connectKey('test-only-key')).rejects.toThrow('Gemini quota reached')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Bad Gateway',{status:502})))
  await expect(connectKey('test-only-key')).rejects.toThrow('HTTP 502')
})

it('delivers a streamed prompt answer and sends the key only in its header', async () => {
  const result={data:{prose:'In Emerald, Ralts has 25 base Attack.'}}
  const fetch=vi.fn().mockResolvedValue(new Response(`event: progress\ndata: {"message":"Checking Emerald"}\n\nevent: answer\ndata: ${JSON.stringify(result)}\n\nevent: done\ndata: {}\n\n`))
  vi.stubGlobal('fetch',fetch)
  const progress=vi.fn()
  await expect(askRotom({message:'Ralts stats in Emerald'},'test-only-key',new AbortController().signal,progress)).resolves.toEqual(result)
  expect(progress).toHaveBeenCalledWith('Checking Emerald')
  const options=fetch.mock.calls[0]![1]
  expect(options.headers['X-Rotom-Gemini-Key']).toBe('test-only-key')
  expect(options.body).not.toContain('test-only-key')
})

it('shows a completed answer without waiting for the connection to close',async()=>{
  const result={data:{prose:'Ralts can be found on Route 102 in Emerald.'}}
  const cancel=vi.fn()
  const stream=new ReadableStream({
    start(controller){controller.enqueue(new TextEncoder().encode(`event: answer\ndata: ${JSON.stringify(result)}\n\n`))},
    cancel,
  })
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(stream)))
  await expect(askRotom({message:'Where is Ralts in Emerald?'},'test-only-key',new AbortController().signal,vi.fn())).resolves.toEqual(result)
  expect(cancel).toHaveBeenCalled()
})
