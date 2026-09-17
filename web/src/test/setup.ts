import '@testing-library/jest-dom/vitest'
import { beforeEach } from 'vitest'

/**
 * A working `localStorage`.
 *
 * The jsdom build vitest resolves here does not provide Web Storage, and persistence is one of the
 * behaviours worth testing, so the suite supplies a minimal in-memory implementation with the same
 * semantics (values stringified, missing keys null).
 */
class MemoryStorage implements Storage {
  #entries = new Map<string, string>()

  get length(): number {
    return this.#entries.size
  }

  clear(): void {
    this.#entries.clear()
  }

  getItem(key: string): string | null {
    return this.#entries.get(key) ?? null
  }

  key(index: number): string | null {
    return [...this.#entries.keys()][index] ?? null
  }

  removeItem(key: string): void {
    this.#entries.delete(key)
  }

  setItem(key: string, value: string): void {
    this.#entries.set(key, String(value))
  }
}

if (typeof globalThis.localStorage === 'undefined') {
  const storage = new MemoryStorage()
  Object.defineProperty(globalThis, 'localStorage', { value: storage, writable: true, configurable: true })
  Object.defineProperty(globalThis, 'sessionStorage', { value: new MemoryStorage(), writable: true, configurable: true })
  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', { value: storage, writable: true, configurable: true })
  }
}

beforeEach(() => {
  localStorage.clear()
})
