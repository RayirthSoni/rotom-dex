import { API_BASE } from './client'
import type { ChatAnswer, Envelope } from './types'

async function chatFetch(path: string, options: RequestInit): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, options)
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new Error('Cannot reach the Rotom server. Start or restart the local backend, then try again. This does not mean your Gemini key is invalid.', {cause:error})
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Rotom returned HTTP ${res.status}. Check that the backend is running and try again.`)
  }
  return res
}

export async function connectKey(key: string): Promise<void> {
  const signal = AbortSignal.timeout(35000)
  try {
    await chatFetch('/api/chat/connect', {method: 'POST', headers: {'X-Rotom-Gemini-Key': key}, signal})
  } catch (error) {
    if (signal.aborted) throw new Error('The Gemini connection test timed out. Please try again; your key has not been saved.', {cause:error})
    throw error
  }
}
export async function askRotom(body: unknown, key: string, signal: AbortSignal, onProgress: (message: string) => void): Promise<Envelope<ChatAnswer | null>> {
  const bounded = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {timedOut = true; bounded.abort()},65000)
  const cancel = () => bounded.abort()
  if (signal.aborted) cancel()
  else signal.addEventListener('abort',cancel,{once:true})
  try {
    return await receiveAnswer(body,key,bounded.signal,onProgress)
  } catch (error) {
    if (timedOut && !signal.aborted) throw new Error('Rotom did not finish within the response time limit. Please retry your question.', {cause:error})
    throw error
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort',cancel)
  }
}

async function receiveAnswer(body: unknown, key: string, signal: AbortSignal, onProgress: (message: string) => void): Promise<Envelope<ChatAnswer | null>> {
  const res = await chatFetch('/api/v2/chat/stream', {method: 'POST', headers: {'content-type':'application/json', 'X-Rotom-Gemini-Key':key}, body:JSON.stringify(body), signal})
  if (!res.body) throw new Error('Rotom returned an empty response. Please retry your question.')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try { while (true) {
    const {value, done} = await reader.read()
    buffer += decoder.decode(value, {stream: !done})
    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0,boundary); buffer = buffer.slice(boundary+2)
      const type = frame.split('\n').find(l => l.startsWith('event: '))?.slice(7)
      const line = frame.split('\n').find(l => l.startsWith('data: '))
      if (!line) continue
      const data = JSON.parse(line.slice(6))
      if (type === 'progress') onProgress(data.message)
      if (type === 'answer') return data
      if (type === 'error') throw new Error(data.detail)
    }
    if (done) break
  } } finally { void reader.cancel().catch(() => {}); reader.releaseLock() }
  throw new Error('The connection ended before Rotom finished. Please retry.')
}
