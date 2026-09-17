import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { askRotom, connectKey } from '../../api/conversation'
import { useConversations, useCredential, type Exchange } from '../../state/conversations'
import { toContext, usePlaythroughs } from '../../state/playthroughs'
import type { ChatAction, GameListRow } from '../../api/types'
import { EvidenceList } from '../../components/Provenance'
import { RotomMark } from '../../components/RotomMark'
import { ItemSprite, PokemonSprite } from '../../components/Sprite'
import { isAllowedSpriteUrl } from '../../domain/sprites'

const EXAMPLES: Array<[label: string, text: string, art: React.ReactNode]> = [
  ['Find a Pokémon', 'Where can I catch Ralts in Emerald?', <PokemonSprite formId={280} type="psychic" size={48} />],
  ['Find an item', 'Where can I get an Exp. Share in Diamond?', <ItemSprite slug="exp-share" size={48} />],
  ['Understand a mechanic', 'What is STAB?', <span className="sprite-backdrop" style={{ width: 48, height: 48 }}><span className="example-mark" aria-hidden="true">?</span></span>],
  ['Build a team', 'Help me build a story team around Charmander in Red.', <PokemonSprite formId={4} type="fire" size={48} />],
]
const title = (s: string) => s.replaceAll('-', ' ').replace(/\b\w/g, c => c.toUpperCase())

function Answer({exchange, apply}: {exchange: Exchange; apply: (action: ChatAction) => string}) {
  const [copied, setCopied] = useState(false)
  const [applied, setApplied] = useState<Record<number,string>>({})
  const a = exchange.answer
  if (!a) return null
  return <div className="rotom-response" data-testid="chat-answer" data-abstained={a.abstained}>
    <div className="answer-byline"><RotomMark size={26} /><strong>Rotom</strong><span>{a.games?.map(title).join(' · ') || (exchange.game ? title(exchange.game) : 'Pokémon explained')}</span></div>
    <p className="answer-prose">{a.prose}</p>
    {a.cards?.length > 0 && <div className="answer-cards">{a.cards.map((card,i) => <section className="answer-card" key={i}>
      {isAllowedSpriteUrl(card.sprite_url) && <span className="sprite-backdrop answer-sprite" style={{ width: 64, height: 64 }}><img className="sprite sprite-pixel" src={card.sprite_url} alt="" loading="lazy" decoding="async"/></span>}<h3>{title(card.title)}</h3><dl>{card.rows.map((row,j) => <div key={j}><dt>{title(row.label)}</dt><dd>{row.value}</dd></div>)}</dl>
    </section>)}</div>}
    {a.recommendations?.length > 0 && <section className="advice"><h3>Suggestions for you</h3>{a.recommendations.map((r,i) => <p key={i}><strong>{r.text}</strong><br/>{r.rationale} <small>{r.status === 'unknown' ? 'Availability needs checking' : title(r.status)}</small></p>)}</section>}
    {a.actions?.map((action,i) => <button className="btn btn-sm" key={i} disabled={Boolean(applied[i])} onClick={() => setApplied(s => ({...s,[i]:apply(action)}))}>{applied[i] || action.label}</button>)}
    <div className="answer-footer"><button type="button" onClick={async () => {try {await navigator.clipboard.writeText([a.prose,...a.cards.map(c => `${c.title}\n${c.rows.map(r => `${r.label}: ${r.value}`).join('\n')}`),...a.recommendations.map(r => `${r.text}\n${r.rationale}`),...a.references.filter(r => r.url?.startsWith('https://')).map(r => `${r.title || 'Source'}: ${r.url}`)].join('\n\n')); setCopied(true)} catch {setCopied(false)}}}>{copied ? 'Copied' : 'Copy answer'}</button>
      <details><summary>Sources & details</summary>
        {a.references?.filter(r => r.url?.startsWith('https://')).map(r => <p key={r.id}><a href={r.url} target="_blank" rel="noreferrer">{r.title || 'Source'}</a> <small>{['reference-reviewed','source-reviewed','gameplay-verified'].includes(r.review_status || '') ? 'Reviewed reference' : r.review_status === 'calculated' ? 'Calculated result' : 'Web research'}</small></p>)}
        {a.cards?.some(c => c.sprite_url) && <p><a href="https://github.com/PokeAPI/sprites">Pokémon sprites: PokéAPI</a></p>}
        {exchange.envelope && <EvidenceList evidence={exchange.envelope.evidence}/>}
        {a.assumptions?.map((x,i) => <p key={i} className="text-sm text-muted">{x.text}</p>)}
      </details></div>
  </div>
}

export function AskRotomScreen() {
  const route = useParams()
  const store = useConversations()
  const credential = useCredential()
  const profiles = usePlaythroughs()
  const [games, setGames] = useState<GameListRow[]>([])
  const [question, setQuestion] = useState('')
  const [keyDraft, setKeyDraft] = useState('')
  const [keyOpen, setKeyOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [contextOpen, setContextOpen] = useState(false)
  const [keyStatus, setKeyStatus] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [pending, setPending] = useState(false)
  const [progress, setProgress] = useState('')
  const abort = useRef<AbortController | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const active = store.conversations.find(c => c.id === store.activeId)
  const selectedGame = active ? active.game : route.game ?? null
  const profileId = active?.profileId || ''
  const research = active?.research ?? true
  const spoiler = active?.spoiler || 'full'
  const profile = profiles.playthroughs[profileId]
  function setProfileId(profileId: string) {store.update(ensureConversation(),{profileId})}
  function setResearch(research: boolean) {store.update(ensureConversation(),{research})}
  useEffect(() => {api.games().then(r => setGames(r.data ?? [])).catch(() => setKeyStatus('Game data could not be loaded. Please refresh.'))}, [])
  useEffect(() => {if (active?.exchanges.length || pending) end.current?.scrollIntoView({block:'end', behavior:'smooth'})}, [active?.exchanges.length, pending])
  useEffect(() => () => abort.current?.abort(), [])
  useEffect(() => {if (route.game) {const s=useConversations.getState(); const c=s.conversations.find(x=>x.id===s.activeId); if(c?.game !== route.game) s.create(route.game)}}, [route.game])
  function ensureConversation() {return active?.id || store.create(route.game || null)}
  function changeGame(game: string) {store.update(ensureConversation(), {game:game || null, profileId:''})}
  function apply(action: ChatAction, exchange: Exchange) {
    const actionGame = exchange.answer?.games?.[0] || exchange.game
    if (!actionGame) return 'Choose a game first'
    let p = usePlaythroughs.getState().playthroughs[profileId]
    if (!p || p.game !== actionGame) {
      const existing = Object.values(usePlaythroughs.getState().playthroughs).find(x => x.game === actionGame)
      const id = existing?.id || profiles.create(actionGame, `${title(actionGame)} team`)
      setProfileId(id); p = usePlaythroughs.getState().playthroughs[id]
    }
    if (!p) return 'Could not create a playthrough'
    const payload=action.payload as Record<string, unknown>
    switch(action.kind) {
      case 'add_team_member':
        if (p.team.some(m => m.pokemon === payload.pokemon)) return 'Already on your team'
        if (p.team.length >= 6) return 'Team is full'
        profiles.addMember(p.id,String(payload.pokemon)); return 'Added to team'
      case 'mark_milestone': profiles.update(p.id,{completedMilestones:[...new Set([...p.completedMilestones,String(payload.milestone)])]}); return 'Progress saved'
      case 'set_current_location': profiles.update(p.id,{currentLocation:String(payload.location)}); return 'Location saved'
      case 'pin_plan': profiles.pinPlan(p.id,{kind:'boss',battle:String(payload.battle),label:action.label,note:''}); return 'Plan saved'
      case 'set_member_level':
      case 'set_member_moves': {
        const member = p.team[Number(payload.member)]
        if (!member) return 'Choose a team member first'
        profiles.updateMember(p.id,member.id,action.kind === 'set_member_level' ? {level:Number(payload.level)} : {moves:payload.moves as string[]}); return 'Team updated'
      }
      default: return 'Action could not be applied'
    }
  }
  async function send(text = question) {
    if (!text.trim() || pending) return
    if (!credential.key) {setKeyOpen(true); setKeyStatus('Connect your Gemini key, then send your question.'); return}
    const id=ensureConversation()
    const c=useConversations.getState().conversations.find(x => x.id === id)!
    const exchange: Exchange = {id:crypto.randomUUID(),question:text.trim(),game:selectedGame}
    const exchanges=[...c.exchanges,exchange]
    store.update(id,{title:c.exchanges.length ? c.title : text.slice(0,48),exchanges})
    setQuestion(''); setPending(true); setProgress('Connecting to Rotom…')
    const controller=new AbortController(); abort.current=controller
    try {
      const response=await askRotom({version:2,game:selectedGame,context:profile?.game === selectedGame ? toContext(profile) : null,spoiler_level:spoiler,
        message:text,mode:c.mode,format:c.format || null,research,
        history:c.exchanges.filter(e => e.answer).flatMap(e => [{role:'user',text:e.question},{role:'assistant',text:e.answer!.prose.slice(0,2000)}]).slice(-12)},credential.key,controller.signal,setProgress)
      const answer=response.data as Exchange['answer']
      const current=useConversations.getState().conversations.find(x => x.id === id)!
      store.update(id,{game:answer?.games?.length === 1 ? answer.games[0] : current.game,exchanges:current.exchanges.map(e => e.id === exchange.id ? {...e,answer,envelope:response} : e)})
    } catch(error) {
      const message=controller.signal.aborted ? 'Stopped. You can retry this question.' : error instanceof Error ? error.message : 'Could not connect. Please retry.'
      const current=useConversations.getState().conversations.find(x => x.id === id)
      if (current) store.update(id,{exchanges:current.exchanges.map(e => e.id === exchange.id ? {...e,error:message} : e)})
    } finally {setPending(false); setProgress(''); abort.current=null; input.current?.focus()}
  }
  return <div className="chat-app">
    <div className="chat-toolbar"><button className="quiet-button" onClick={() => setHistoryOpen(!historyOpen)} aria-expanded={historyOpen}>Conversations</button>
      <button className="quiet-button" disabled={pending} onClick={() => {store.create(selectedGame); setQuestion(''); input.current?.focus()}}>+ New chat</button>
      <div className="toolbar-spacer"/>
      <button className="connection-button" onClick={() => setKeyOpen(!keyOpen)} aria-expanded={keyOpen}><span className={credential.key ? 'connection-dot connected' : 'connection-dot'}/>{credential.key ? 'Gemini connected' : 'Connect Gemini'}</button>
    </div>
    {keyOpen && <section className="setup-panel" aria-label="Gemini connection"><h2>Your key. Your conversations.</h2><p>Connect your own Gemini API key. Chat and web research use your quota. The key passes through this server to Google and stays in memory only until you reload or disconnect.</p>
      {!credential.key ? <form onSubmit={async e => {e.preventDefault(); setConnecting(true); setKeyStatus('Testing connection…'); try {await connectKey(keyDraft.trim()); credential.set(keyDraft.trim(),true); setKeyDraft(''); setKeyStatus('Connected. You can ask your question now.'); setKeyOpen(false)} catch(error) {setKeyStatus(error instanceof Error ? error.message : 'Connection failed')} finally {setConnecting(false)}}}>
        <label htmlFor="gemini-key">Gemini API key</label><div className="key-input-row"><input id="gemini-key" type="password" autoComplete="off" value={keyDraft} onChange={e => setKeyDraft(e.target.value)} placeholder="Paste your Gemini key"/><button className="btn btn-primary" disabled={connecting || !keyDraft.trim()}>{connecting ? 'Connecting…' : 'Connect'}</button></div>
        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">Get a key in Google AI Studio</a>
      </form> : <button className="btn" onClick={() => {abort.current?.abort(); credential.set(''); setKeyStatus('Disconnected. Your key has been cleared.')}}>Disconnect & clear key</button>}
      <p role="status">{keyStatus}</p></section>}
    <div className="chat-layout">
      {historyOpen && <aside className="conversation-list" aria-label="Saved conversations"><h2>Your conversations</h2>{store.conversations.length === 0 && <p>Your chats will appear here.</p>}{store.conversations.map(c => <div key={c.id} className={c.id === active?.id ? 'selected' : ''}><button disabled={pending} onClick={() => store.select(c.id)}>{c.title}<small>{c.game ? title(c.game) : 'No game selected'}</small></button><button disabled={pending} aria-label={`Delete ${c.title}`} onClick={() => {if (window.confirm('Delete this conversation from this browser?')) store.remove(c.id)}}>×</button></div>)}</aside>}
      <div className="chat-column">
        <div className="context-bar"><label><span>Game</span><select aria-label="Game for this conversation" value={selectedGame || ''} disabled={pending} onChange={e => changeGame(e.target.value)}><option value="">Choose when needed</option>{games.filter(g => g.support_tier !== 'excluded').map(g => <option key={g.slug} value={g.slug}>{g.name}{g.slug.endsWith('-japan') ? ' (Japan)' : ''}</option>)}</select></label>
          <label><span>Advice</span><select aria-label="Advice mode" value={active?.mode || 'story'} disabled={pending} onChange={e => store.update(ensureConversation(),{mode:e.target.value as 'story' | 'competitive'})}><option value="story">Story & exploration</option><option value="competitive">Competitive</option></select></label>
          <button className="quiet-button" onClick={() => setContextOpen(!contextOpen)} aria-expanded={contextOpen}>My context {profile ? '•' : '+'}</button>
        </div>
        {active?.mode === 'competitive' && <label className="format-input">Competitive format<input value={active.format} onChange={e => store.update(active.id,{format:e.target.value})} placeholder="Exact format, e.g. gen3ou"/><Link to="/competitive">Browse formats & team tools</Link></label>}
        {contextOpen && <section className="setup-panel"><h2>Make it personal</h2><p>Optional. Add a team and progress when you want advice for your own playthrough.</p><label>Saved playthrough<select value={profileId} onChange={e => setProfileId(e.target.value)}><option value="">No saved context</option>{Object.values(profiles.playthroughs).filter(p => p.game === selectedGame).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><Link to="/playthroughs">Manage saved teams & progress</Link><label>Spoiler preference<select value={spoiler} onChange={e => store.update(ensureConversation(),{spoiler:e.target.value as 'none' | 'hint' | 'full'})}><option value="full">Show requested game details</option><option value="hint">Hints near my progress</option><option value="none">Avoid later story details</option></select></label><label className="research-switch"><input type="checkbox" checked={research} onChange={e => setResearch(e.target.checked)}/> Research missing information with my Gemini key</label></section>}
        {!active?.exchanges.length && <section className="chat-welcome"><div className="welcome-face"><RotomMark size={88} blink /></div><div className="welcome-dialog"><h1>A little guidance.<br/><span>A better adventure.</span></h1><p>Find your next teammate, track down an item, or make sense of a tricky mechanic. Just ask Rotom.</p></div><div className="example-grid">{EXAMPLES.map(([label,text,art]) => <button key={label} type="button" onClick={() => {setQuestion(text); input.current?.focus()}}>{art}<strong>{label}</strong><span className="example-text">{text}</span></button>)}</div></section>}
        <ol className="transcript" aria-label="Conversation">{active?.exchanges.map(e => <li key={e.id}><div className="user-message">{e.question}</div>{e.error ? <div className="chat-error" role="alert"><p>{e.error}</p><button className="quiet-button" disabled={pending} onClick={() => send(e.question)}>Retry question</button></div> : <Answer exchange={e} apply={action => apply(action,e)}/>}</li>)}</ol>
        {pending && <div className="thinking" role="status"><span className="connection-dot connected"/>{progress}</div>}<div ref={end}/>
        <div className="composer-wrap">{!pending && active?.exchanges.at(-1)?.answer?.follow_ups && <div className="follow-ups">{active.exchanges.at(-1)!.answer!.follow_ups!.map(q => <button key={q} onClick={() => {setQuestion(q); input.current?.focus()}}>{q}</button>)}</div>}
          <form className="composer" onSubmit={e => {e.preventDefault(); void send()}}><textarea ref={input} aria-label="Ask Rotom a question" placeholder="Ask anything about Pokémon…" value={question} onChange={e => setQuestion(e.target.value)} maxLength={2000} rows={2} onKeyDown={e => {if(e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault(); void send()}}}/><div className="composer-bottom"><span>{selectedGame ? `Playing ${title(selectedGame)}` : 'Your adventure, your game'} · Enter to send</span>{pending ? <button type="button" className="send-button" onClick={() => abort.current?.abort()}>Stop</button> : <button type="submit" className="send-button" disabled={!question.trim()}>Ask Rotom</button>}</div></form>
          <p className="composer-note">{credential.key ? 'Chats saved on this browser · Key in tab memory only' : 'Bring your own Gemini key to chat. Reference tools are free to browse.'}</p>
        </div>
      </div>
    </div>
  </div>
}
