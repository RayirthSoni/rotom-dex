import { useEffect, useState } from 'react'
import { API_BASE } from '../../api/client'
import { useConversations } from '../../state/conversations'
import { Link } from 'react-router-dom'

type Format = { id: string; name: string; generation: number; rules: string[]; snapshot: string }
type Validation = { valid: boolean; issues: string[]; format: string; rules: string[]; snapshot: string }
type Damage = { range: number[]; description: string; assumptions: string }
async function request<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}/api/competitive/${path}`, body ? {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)} : {})
  const payload = await r.json()
  if (!r.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Check the format and Pokémon details.')
  return payload.data
}
export function CompetitiveScreen() {
  const [formats,setFormats] = useState<Format[]>([])
  const [filter,setFilter] = useState('')
  const [format,setFormat] = useState('')
  const [team,setTeam] = useState(() => localStorage.getItem('rotom-dex.competitive-team.v1') || '')
  const [validation,setValidation] = useState<Validation | null>(null)
  const [damage,setDamage] = useState<Damage | null>(null)
  const [error,setError] = useState('')
  const [busy,setBusy] = useState(false)
  const [generation,setGeneration] = useState(3)
  const [attacker,setAttacker] = useState('')
  const [defender,setDefender] = useState('')
  const [move,setMove] = useState('')
  const [level,setLevel] = useState(50)
  const [attackerTera,setAttackerTera] = useState(false)
  const [defenderTera,setDefenderTera] = useState(false)
  const [weather,setWeather] = useState('')
  useEffect(() => {request<Format[]>('formats').then(setFormats).catch(e => setError(e.message))},[])
  useEffect(() => {localStorage.setItem('rotom-dex.competitive-team.v1',team)},[team])
  async function run(task: () => Promise<void>) {setBusy(true); setError(''); try {await task()} catch(e) {setError(e instanceof Error ? e.message : 'Please try again')} finally {setBusy(false)}}
  const selected=formats.find(f => f.id === format)
  return <div className="competitive-page"><p className="eyebrow">TEAM WORKSHOP</p><h1>A team with a plan.</h1><p>Check a team against an exact format, then explore damage ranges. These tools work without a Gemini key.</p>
    {error && <p role="alert" className="chat-error">{error}</p>}
    <section className="setup-panel"><h2>1. Choose the rules</h2><label>Find a format<input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Generation, OU, VGC, regulation…"/></label><label>Format<select value={format} onChange={e => {setFormat(e.target.value);setValidation(null)}}><option value="">Choose an exact format</option>{formats.filter(f => `${f.id} ${f.name}`.toLowerCase().includes(filter.toLowerCase())).map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
      {selected && <p>Generation {selected.generation} · Rules: {selected.rules.join(', ')}. Showdown snapshot {selected.snapshot}. This is a pinned ruleset; check the dated official regulation before tournament entry.</p>}
    </section>
    <section className="setup-panel"><h2>2. Bring your team</h2><p>Paste a Pokémon Showdown team. Include abilities, moves, items, natures, EVs, IVs and battle modifiers when relevant. Saved in this browser.</p>
      <label>Showdown team<textarea rows={13} value={team} maxLength={20000} onChange={e => {setTeam(e.target.value); setValidation(null)}} placeholder={'Swampert @ Leftovers\nAbility: Torrent\nEVs: 252 HP / 252 Def / 4 SpD\nRelaxed Nature\n- Earthquake\n- Surf\n- Ice Beam\n- Protect'}/></label>
      <div className="flex gap-2 flex-wrap"><button className="btn" disabled={busy || !format || !team.trim()} onClick={() => run(async () => setValidation(await request<Validation>('validate',{format,team})))}>Check legality</button>
      <button className="btn" disabled={busy || !team.trim()} onClick={() => run(async () => {const imported=await request<{team:unknown[]}>('team',{operation:'import',text:team}); const exported=await request<{text:string}>('team',{operation:'export',team:imported.team}); setTeam(exported.text); await navigator.clipboard.writeText(exported.text)})}>Copy Showdown export</button>
      <Link to="/" onClick={() => {const store=useConversations.getState(); const id=store.create();store.update(id,{mode:'competitive',format})}}>Discuss this format with Rotom ↗</Link></div>
      {validation && <div role="status"><h3>{validation.valid ? 'Legal in this format' : 'This team needs changes'}</h3><ul>{validation.issues.map((issue,i) => <li key={i}>{issue}</li>)}</ul><p>Competitive legality is separate from obtaining these Pokémon in your game and from how well the team performs.</p></div>}
    </section>
    <section className="setup-panel"><h2>3. Explore one attack</h2><p>A basic neutral-stat calculation. For exact EVs, IVs, abilities and held items, paste one Showdown set in each box. The chosen generation controls mechanics.</p><form onSubmit={e => {e.preventDefault(); void run(async () => {
      async function pokemon(text: string, terastallized: boolean) {if (!text.includes('\n') && !text.includes('@')) return {species:text,level}; const r=await request<{team:Record<string,unknown>[]}>('team',{operation:'import',text}); const set={...r.team[0],level:r.team[0]?.level || level}; if(!terastallized) delete (set as Record<string,unknown>).teraType; return set}
      setDamage(await request<Damage>('damage',{generation,attacker:await pokemon(attacker,attackerTera),defender:await pokemon(defender,defenderTera),move,field:weather ? {weather} : {}}))
    })}}><div className="battle-input-grid"><label>Generation<select value={generation} onChange={e => setGeneration(Number(e.target.value))}>{Array.from({length:9},(_,i) => <option key={i} value={i+1}>{i+1}</option>)}</select></label><label>Default level<input type="number" min={1} max={100} value={level} onChange={e => setLevel(Number(e.target.value))}/></label><label>Attacker name or Showdown set<textarea required value={attacker} onChange={e => setAttacker(e.target.value)} placeholder="Swampert"/></label><label>Defender name or Showdown set<textarea required value={defender} onChange={e => setDefender(e.target.value)} placeholder="Tyranitar"/></label>{generation===9 && <><label><input type="checkbox" checked={attackerTera} onChange={e=>setAttackerTera(e.target.checked)}/> Attacker is Terastallized (use the set's Tera Type)</label><label><input type="checkbox" checked={defenderTera} onChange={e=>setDefenderTera(e.target.checked)}/> Defender is Terastallized (use the set's Tera Type)</label></>}<label>Move<input required value={move} onChange={e => setMove(e.target.value)} placeholder="Earthquake"/></label><label>Weather<select value={weather} onChange={e => setWeather(e.target.value)}><option value="">None</option>{['Sun','Rain','Sand','Hail','Snow'].map(w => <option key={w}>{w}</option>)}</select></label></div><button className="btn" disabled={busy}>Calculate range</button></form>
      {damage && <div role="status"><h3>{damage.range.join('–')} damage</h3><p>{damage.description}</p><p className="text-muted">{damage.assumptions}</p></div>}
    </section>
    <p className="text-sm text-muted">Calculations: <a href="https://github.com/smogon/damage-calc">@smogon/calc</a>. Rules: <a href="https://github.com/smogon/pokemon-showdown">Pokémon Showdown</a>. No battle outcome is guaranteed.</p>
  </div>
}
