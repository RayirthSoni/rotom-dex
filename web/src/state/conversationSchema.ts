import { z } from 'zod'

// Browser saves are untrusted and may outlive the version that wrote them.
// Preserve server metadata while validating every field traversed by the renderer.
const text = z.string().max(20000)
const action = z.discriminatedUnion('kind', [
  z.object({kind:z.literal('add_team_member'),payload:z.object({pokemon:text})}),
  z.object({kind:z.literal('mark_milestone'),payload:z.object({milestone:text})}),
  z.object({kind:z.literal('set_current_location'),payload:z.object({location:text})}),
  z.object({kind:z.literal('pin_plan'),payload:z.object({battle:text})}),
  z.object({kind:z.literal('set_member_level'),payload:z.object({member:z.number().int().min(0).max(5),level:z.number().int().min(1).max(100)})}),
  z.object({kind:z.literal('set_member_moves'),payload:z.object({member:z.number().int().min(0).max(5),moves:z.array(text).max(4)})}),
]).and(z.object({label:text,applied:z.literal(false).default(false)}))
const answer = z.object({
  prose:text,abstained:z.boolean(),
  cards:z.array(z.object({
    kind:text,title:text,tool:text,sprite_url:text.nullable().optional(),
    rows:z.array(z.object({label:text,value:text,evidence_id:text.optional()})).max(40),
  }).passthrough()).max(24),
  actions:z.array(action).max(15),
  recommendations:z.array(z.object({text,rationale:text,status:z.enum(['reachable','locked','unknown'])}).passthrough()).max(24),
  assumptions:z.array(z.object({text,because:text})).max(40),
  references:z.array(z.object({kind:z.enum(['web','evidence']),id:text,url:text.optional(),title:text.optional(),review_status:text.optional()})).max(100),
  games:z.array(text).max(3).optional(),
  follow_ups:z.array(text).max(20).optional(),
}).passthrough()
const evidence = z.object({id:text,sources:z.array(z.object({
  source_id:text,kind:text,url:text,retrieved_at:text,sha256:text.nullable(),license:text,review_status:text,selector:text,
}).passthrough())}).passthrough()

export const conversationSchema = z.object({
  id:text,title:text,game:text.nullable(),mode:z.enum(['story','competitive']),format:text,
  profileId:text.optional(),research:z.boolean().optional(),spoiler:z.enum(['none','hint','full']).optional(),updatedAt:text,
  exchanges:z.array(z.object({
    id:text,question:text,game:text.nullable(),answer:answer.optional(),error:text.optional(),
    envelope:z.object({evidence:z.array(evidence)}).passthrough().optional(),
  })).max(100),
})
