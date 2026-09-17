/**
 * The saved document, and the only place untrusted input is validated.
 *
 * A save file crosses a version boundary and may have been hand-edited, exported from an older
 * build, or written by something else entirely, so it is parsed strictly with field-level errors.
 * API responses are *not* validated this way: they come from the same snapshot the UI is reading,
 * and running a schema over a half-megabyte learnset on a phone would cost more than it proves.
 */

import { z } from 'zod'

export const SAVE_VERSION = 1
export const SAVE_SCHEMA = 'rotom-dex/playthroughs'

const slug = z.string().min(1).max(64).regex(/^[a-z0-9][a-z0-9.-]*$/, 'must be a lowercase slug')

export const teamMemberSchema = z.object({
  id: z.string().min(1).max(64),
  pokemon: slug,
  nickname: z.string().max(24).nullable().default(null),
  level: z.number().int().min(1).max(100).nullable().default(null),
  moves: z.array(slug).max(4).default([]),
  nature: slug.nullable().default(null),
  ability: slug.nullable().default(null),
  heldItem: slug.nullable().default(null),
})

export const closedWorldSchema = z.object({
  milestones: z.boolean().default(false),
  locations: z.boolean().default(false),
  bag: z.boolean().default(false),
  party: z.boolean().default(false),
  trade: z.boolean().default(false),
})

export const pinnedPlanSchema = z.object({
  id: z.string().min(1).max(64),
  kind: z.enum(['boss']),
  battle: z.string().min(1).max(96),
  label: z.string().max(120),
  pinnedAt: z.string(),
  note: z.string().max(500).default(''),
})

export const playthroughSchema = z.object({
  id: z.string().min(1).max(64),
  name: z.string().min(1).max(60),
  game: slug,
  createdAt: z.string(),
  updatedAt: z.string(),
  currentLocation: slug.nullable().default(null),
  visitedLocations: z.array(slug).max(1000).default([]),
  completedMilestones: z.array(slug).max(500).default([]),
  bag: z.array(slug).max(500).default([]),
  tradeAccess: z.enum(['none', 'local', 'any']).default('none'),
  spoilerLevel: z.enum(['none', 'hint', 'full']).default('hint'),
  closedWorld: closedWorldSchema.default({ milestones: false, locations: false, bag: false, party: false, trade: false }),
  team: z.array(teamMemberSchema).max(6).default([]),
  pinnedPlans: z.array(pinnedPlanSchema).max(50).default([]),
})

export const saveFileSchema = z.object({
  schema: z.literal(SAVE_SCHEMA),
  version: z.number().int().min(1),
  exportedAt: z.string(),
  snapshotId: z.string().nullable().default(null),
  playthroughs: z.array(playthroughSchema).max(50),
  activeId: z.string().nullable().default(null),
})

export const storedStateSchema = z.object({
  version: z.number().int().min(1),
  activeId: z.string().nullable(),
  playthroughs: z.record(z.string(), playthroughSchema),
})

export type TeamMember = z.infer<typeof teamMemberSchema>
export type ClosedWorld = z.infer<typeof closedWorldSchema>
export type PinnedPlan = z.infer<typeof pinnedPlanSchema>
export type Playthrough = z.infer<typeof playthroughSchema>
export type SaveFile = z.infer<typeof saveFileSchema>
export type StoredState = z.infer<typeof storedStateSchema>

/**
 * Forward migrations, applied in order. A file from a *newer* version is refused rather than
 * coerced: silently dropping fields we do not understand would lose a player's work.
 */
export const migrations: Record<number, (input: unknown) => unknown> = {
  // 1 is the first published shape; entries are added as `2: (old) => ...` when it changes.
}

export function migrate(input: unknown, from: number): { value: unknown; applied: number[] } {
  const applied: number[] = []
  let value = input
  for (let version = from + 1; version <= SAVE_VERSION; version += 1) {
    const step = migrations[version]
    if (step) {
      value = step(value)
      applied.push(version)
    }
  }
  return { value, applied }
}

export function emptyClosedWorld(): ClosedWorld {
  return { milestones: false, locations: false, bag: false, party: false, trade: false }
}
