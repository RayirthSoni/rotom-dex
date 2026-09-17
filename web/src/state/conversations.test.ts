import { beforeEach, expect, it } from 'vitest'
import { useConversations, useCredential } from './conversations'
import { usePlaythroughs } from './playthroughs'
import { conversationSchema } from './conversationSchema'

beforeEach(()=>{localStorage.clear();useConversations.setState({activeId:null,conversations:[]});useCredential.getState().set('');usePlaythroughs.getState().reset()})
it('rejects malformed nested saved answers before rendering them',()=>{
 const conversation={id:'a',title:'Saved',game:'red',mode:'story',format:'',updatedAt:'2026-09-17',exchanges:[{id:'b',question:'Stats?',game:'red',answer:{prose:'answer',abstained:false,cards:[{kind:'note',title:'Stats',tool:'dex_lookup',rows:[null]}],actions:[],recommendations:[],assumptions:[],references:[]}}]}
 expect(conversationSchema.safeParse(conversation).success).toBe(false)
})
it('persists conversation context separately from credentials',async()=>{
 const id=useConversations.getState().create('emerald')
 useConversations.getState().update(id,{profileId:'test-profile',research:false,spoiler:'none',format:'gen3ou'})
 useCredential.getState().set('secret-visitor-key',true)
 expect(localStorage.getItem('rotom-dex.conversations')).toContain('test-profile')
 expect(JSON.stringify({...localStorage})).not.toContain('secret-visitor-key')
 useConversations.setState({activeId:null,conversations:[]},false)
 // Restore the saved document, as a fresh page would.
 localStorage.setItem('rotom-dex.conversations',JSON.stringify({version:1,state:{version:1,activeId:id,conversations:[{id,title:'Saved',game:'emerald',mode:'story',format:'',profileId:'test-profile',research:false,exchanges:[],updatedAt:'2026-09-17'}]}}))
 await useConversations.persist.rehydrate()
 expect(useConversations.getState().conversations[0]?.research).toBe(false)
})
it('migrates version-one playthroughs without losing milestones or plans',async()=>{
 const id=usePlaythroughs.getState().create('emerald','Old save')
 usePlaythroughs.getState().addMember(id,'ralts')
 usePlaythroughs.getState().toggleMilestone(id,'stone-badge')
 usePlaythroughs.getState().pinPlan(id,{kind:'boss',battle:'roxanne',label:'Roxanne',note:'Remember this'})
 const state=usePlaythroughs.getState()
 localStorage.setItem('rotom-dex.playthroughs',JSON.stringify({version:1,state:{version:1,activeId:id,playthroughs:state.playthroughs}}))
 await usePlaythroughs.persist.rehydrate()
 const restored=usePlaythroughs.getState()
 expect(restored.version).toBe(2)
 expect(restored.playthroughs[id]?.team[0]?.pokemon).toBe('ralts')
 expect(restored.playthroughs[id]?.completedMilestones).toEqual(['stone-badge'])
 expect(restored.playthroughs[id]?.pinnedPlans[0]?.note).toBe('Remember this')
})
