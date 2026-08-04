import type { RuntimeLogEntry } from '../api/types'

export const DISPLAY_MAX = 2000
export const LOG_FLUSH_MS = 150
/** Distance from bottom (px) still treated as "at bottom" for follow-latest. */
export const NEAR_BOTTOM_PX = 48

export function isNearBottom(
  el: Pick<HTMLElement, 'scrollHeight' | 'scrollTop' | 'clientHeight'>,
  thresholdPx = NEAR_BOTTOM_PX,
): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= thresholdPx
}

export function logDedupeKey(entry: RuntimeLogEntry): string {
  return `${entry.session_id}:${entry.entry_id}`
}

export function trimLogs(items: RuntimeLogEntry[]): RuntimeLogEntry[] {
  if (items.length <= DISPLAY_MAX) return items
  return items.slice(items.length - DISPLAY_MAX)
}

export function mergeLogs(
  prev: RuntimeLogEntry[],
  incoming: RuntimeLogEntry[],
): RuntimeLogEntry[] {
  if (!incoming.length) return prev

  const incomingSession = incoming[0]?.session_id
  const prevSession = prev[0]?.session_id
  if (
    incomingSession &&
    prevSession &&
    incomingSession !== prevSession
  ) {
    return trimLogs(incoming)
  }

  const seen = new Set(prev.map(logDedupeKey))
  const novel = incoming.filter((item) => !seen.has(logDedupeKey(item)))
  if (!novel.length) return prev
  return trimLogs([...prev, ...novel])
}
