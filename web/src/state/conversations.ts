import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { ChatAnswer, Envelope } from '../api/types'
import { conversationSchema } from './conversationSchema'

export interface Exchange {
  id: string
  question: string
  game: string | null
  answer?: ChatAnswer & { games?: string[]; follow_ups?: string[]; format?: string | null }
  envelope?: Envelope<ChatAnswer | null>
  error?: string
}
export interface Conversation {
  id: string
  title: string
  game: string | null
  mode: 'story' | 'competitive'
  format: string
  profileId?: string
  research?: boolean
  spoiler?: 'none' | 'hint' | 'full'
  exchanges: Exchange[]
  updatedAt: string
}
interface Conversations {
  version: number
  activeId: string | null
  conversations: Conversation[]
  create: (game?: string | null) => string
  select: (id: string) => void
  update: (id: string, patch: Partial<Conversation>) => void
  remove: (id: string) => void
}
const uid = () => crypto.randomUUID()
export const useConversations = create<Conversations>()(persist((set) => ({
  version: 1, activeId: null, conversations: [],
  create: (game = null) => {
    const id = uid()
    set(s => ({activeId: id, conversations: [{id, title: 'New conversation', game, mode: 'story' as const, format: '', exchanges: [], updatedAt: new Date().toISOString()}, ...s.conversations].slice(0, 50)}))
    return id
  },
  select: activeId => set({activeId}),
  update: (id, patch) => set(s => ({conversations: s.conversations.map(c => c.id === id ? {...c, ...patch, exchanges:(patch.exchanges || c.exchanges).slice(-100), id, updatedAt: new Date().toISOString()} : c)})),
  remove: id => set(s => ({conversations: s.conversations.filter(c => c.id !== id), activeId: s.activeId === id ? null : s.activeId})),
}), {
  name: 'rotom-dex.conversations', version: 1, storage: createJSONStorage(() => localStorage),
  partialize: s => ({version: s.version, activeId: s.activeId, conversations: s.conversations}),
  merge: (saved, current) => {
    const s = saved as Partial<Conversations> | undefined
    if (s?.version !== 1 || !Array.isArray(s.conversations)) return current
    const conversations = s.conversations.slice(0,50).flatMap(c => {
      const parsed = conversationSchema.safeParse(c)
      return parsed.success ? [parsed.data as Conversation] : []
    })
    return {...current, conversations, activeId: conversations.some(c => c.id === s.activeId) ? s.activeId! : null}
  },
}))

// Deliberately separate from persisted stores, URLs, exports, and request bodies.
export const useCredential = create<{key: string; connected: boolean; set: (key: string, connected?: boolean) => void}>(set => ({
  key: '', connected: false, set: (key, connected = false) => set({key, connected}),
}))
