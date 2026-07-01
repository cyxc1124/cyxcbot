import type { RuntimeLogEntry } from '../api/types'

export const DISPLAY_MAX = 2000
export const LOG_FLUSH_MS = 150

export function trimLogs(items: RuntimeLogEntry[]): RuntimeLogEntry[] {
  if (items.length <= DISPLAY_MAX) return items
  return items.slice(items.length - DISPLAY_MAX)
}

export function mergeLogs(
  prev: RuntimeLogEntry[],
  incoming: RuntimeLogEntry[],
): RuntimeLogEntry[] {
  if (!incoming.length) return prev
  return trimLogs([...prev, ...incoming])
}
