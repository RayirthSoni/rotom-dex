import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { SnapshotProvider } from './api/SnapshotProvider'
import { router } from './routes'
import './styles/index.css'

const client = new QueryClient({
  defaultOptions: {
    queries: { staleTime: Infinity, gcTime: 1000 * 60 * 60, refetchOnWindowFocus: false, retry: false },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <SnapshotProvider>
        <RouterProvider router={router} />
      </SnapshotProvider>
    </QueryClientProvider>
  </StrictMode>,
)
