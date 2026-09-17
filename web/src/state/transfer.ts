/**
 * Export and import of saved playthroughs.
 *
 * Import reports every problem with a field path rather than failing at the first one, and never
 * partially applies a file. Slugs are resolved against the live snapshot separately, by the UI, so
 * a file written against a different snapshot degrades visibly instead of disappearing.
 */

import { z } from 'zod'
import { SAVE_SCHEMA, SAVE_VERSION, migrate, saveFileSchema, type Playthrough, type SaveFile } from './schema'

export interface ImportProblem {
  path: string
  message: string
}

export type ImportResult =
  | { ok: true; playthroughs: Playthrough[]; activeId: string | null; warnings: string[]; snapshotId: string | null }
  | { ok: false; problems: ImportProblem[] }

export function buildExport(playthroughs: Playthrough[], activeId: string | null, snapshotId: string | null): SaveFile {
  return {
    schema: SAVE_SCHEMA,
    version: SAVE_VERSION,
    exportedAt: new Date().toISOString(),
    snapshotId,
    playthroughs,
    activeId,
  }
}

export function exportToText(playthroughs: Playthrough[], activeId: string | null, snapshotId: string | null): string {
  return `${JSON.stringify(buildExport(playthroughs, activeId, snapshotId), null, 2)}\n`
}

function problems(error: z.ZodError): ImportProblem[] {
  return error.issues.map((issue) => ({
    path: issue.path.length ? issue.path.join('.') : '(document)',
    message: issue.message,
  }))
}

export function parseImport(text: string, currentSnapshotId: string | null): ImportResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    return { ok: false, problems: [{ path: '(document)', message: `This is not valid JSON: ${(error as Error).message}` }] }
  }

  const shape = parsed as { schema?: unknown; version?: unknown }
  if (shape?.schema !== SAVE_SCHEMA) {
    return {
      ok: false,
      problems: [{ path: 'schema', message: `Expected a Rotom Dex export ("${SAVE_SCHEMA}"), found ${JSON.stringify(shape?.schema ?? null)}.` }],
    }
  }
  const version = typeof shape.version === 'number' ? shape.version : NaN
  if (!Number.isInteger(version) || version < 1) {
    return { ok: false, problems: [{ path: 'version', message: 'The file does not say which version it was written with.' }] }
  }
  if (version > SAVE_VERSION) {
    return {
      ok: false,
      problems: [
        {
          path: 'version',
          message: `This file was written by a newer version of Rotom Dex (save version ${version}; this build understands ${SAVE_VERSION}). Nothing was changed.`,
        },
      ],
    }
  }

  const { value, applied } = migrate(parsed, version)
  const result = saveFileSchema.safeParse(value)
  if (!result.success) return { ok: false, problems: problems(result.error) }

  const warnings: string[] = []
  if (applied.length) warnings.push(`Upgraded the file from save version ${version} to ${SAVE_VERSION}.`)
  if (result.data.snapshotId && currentSnapshotId && result.data.snapshotId !== currentSnapshotId) {
    warnings.push(
      'This file was exported against a different data snapshot. Names that no longer exist are kept and flagged rather than removed.',
    )
  }
  const seen = new Set<string>()
  for (const playthrough of result.data.playthroughs) {
    if (seen.has(playthrough.id)) {
      return { ok: false, problems: [{ path: 'playthroughs', message: `Two playthroughs share the id "${playthrough.id}".` }] }
    }
    seen.add(playthrough.id)
  }
  const activeId = result.data.activeId && seen.has(result.data.activeId) ? result.data.activeId : null

  return { ok: true, playthroughs: result.data.playthroughs, activeId, warnings, snapshotId: result.data.snapshotId }
}
