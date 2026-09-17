/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Empty in development (Vite proxies /api) and in production (FastAPI serves the bundle). */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
