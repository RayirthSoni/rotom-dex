import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { useEnvelope } from '../../api/queries'
import { useKey } from '../../api/SnapshotProvider'
import { QueryBoundary } from '../../components/QueryBoundary'
import type { GameListRow } from '../../api/types'
import { useConversations } from '../../state/conversations'

export function GameSelector() {
  const [filter,setFilter] = useState('')
  const navigate=useNavigate()
  const {state,refetch}=useEnvelope<GameListRow[]>(useKey('games'),api.games)
  return <div className="mx-auto max-w-5xl"><h1 className="text-2xl font-bold">Choose a game</h1><p className="mt-2 text-sm" style={{color:'var(--ink-muted)'}}>Your answer changes with your game. Choose the exact version, including its expansion when relevant.</p>
    <label className="block my-5">Find your game<input type="search" className="block rounded border p-3 mt-2 w-full max-w-md" aria-label="Filter games" placeholder="Emerald, Diamond, Scarlet…" value={filter} onChange={e=>setFilter(e.target.value)}/></label>
    <QueryBoundary state={state} onRetry={()=>refetch()}>{games=><ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{games.filter(g=>g.support_tier!=='excluded' && `${g.name} ${g.slug}`.toLowerCase().includes(filter.toLowerCase())).map(g=><li key={g.slug}><button className="w-full border rounded-xl p-4 text-left hover:border-[var(--accent)]" style={{background:'var(--surface-raised)'}} onClick={()=>{useConversations.getState().create(g.slug);navigate(`/g/${g.slug}/ask`)}}><strong>{g.name}{g.slug.endsWith('-japan')?' (Japan)':''}</strong><span className="block text-sm mt-2" style={{color:'var(--ink-muted)'}}>Generation {g.generation}{g.support_tier==='catalog'?' · Local reference data not yet imported':''}</span></button></li>)}</ul>}</QueryBoundary>
    <p className="text-sm mt-6" style={{color:'var(--ink-muted)'}}>Some questions still need research. <Link className="underline" to="/coverage">View detailed data coverage</Link></p>
  </div>
}
