import { API_BASE } from './client'
import type { ChatAnswer, Envelope } from './types'

export async function connectKey(key: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/connect`, {method: 'POST', headers: {'X-Rotom-Gemini-Key': key}})
  if (!res.ok) { const body = await res.json(); throw new Error(typeof body.detail === 'string' ? body.detail : 'Could not connect. Check your key.') }
}
export async function askRotom(body: unknown, key: string, signal: AbortSignal, onProgress: (message: string) => void): Promise<Envelope<ChatAnswer | null>> {
  const res = await fetch(`${API_BASE}/api/v2/chat/stream`, {method: 'POST', headers: {'content-type':'application/json', 'X-Rotom-Gemini-Key':key}, body:JSON.stringify(body), signal})
  if (!res.ok) {
    const error = await res.json()
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Check your question and game context.')
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: Envelope<ChatAnswer | null> | undefined
  while (true) {
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
      if (type === 'answer') result = data
      if (type === 'error') throw new Error(data.detail)
    }
    if (done) break
  }
  if (!result) throw new Error('The connection ended before Rotom finished. Please retry.')
  return result
}
