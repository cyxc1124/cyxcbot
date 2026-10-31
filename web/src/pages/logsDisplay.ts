import type { LogLevel, RuntimeLogEntry } from '../api/types'

export const DISPLAY_MAX = 2000
export const LOG_FLUSH_MS = 150

export const OUTPUT_LOG_LEVELS: LogLevel[] = ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
export const WEB_LOG_LEVELS = OUTPUT_LOG_LEVELS.filter((level) => level !== 'TRACE')
export const LOG_LEVEL_CLASS: Record<string, string> = {
  TRACE: 'text-muted-foreground',
  DEBUG: 'text-muted-foreground',
  INFO: 'text-primary',
  SUCCESS: 'text-emerald-600 dark:text-emerald-400',
  WARNING: 'text-amber-600 dark:text-amber-400',
  ERROR: 'text-red-600 dark:text-red-400',
  CRITICAL: 'text-red-700 dark:text-red-300',
}

export interface LogViewOptions {
  levels: readonly LogLevel[]
  limit: number
  wrap: boolean
}

export const LOG_VIEW_PRESETS: Record<'开发' | '运维' | '精简', LogViewOptions> = {
  开发: { levels: WEB_LOG_LEVELS, limit: 2000, wrap: true },
  运维: { levels: WEB_LOG_LEVELS.filter((level) => level !== 'DEBUG'), limit: 2000, wrap: true },
  精简: { levels: ['WARNING', 'ERROR', 'CRITICAL'], limit: 500, wrap: false },
}

export function logViewPreset(view: LogViewOptions): string {
  return Object.entries(LOG_VIEW_PRESETS).find(([, preset]) => (
    preset.limit === view.limit && preset.wrap === view.wrap
    && preset.levels.length === view.levels.length
    && preset.levels.every((level) => view.levels.includes(level))
  ))?.[0] ?? '自定义'
}

export function minLogLevel(levels: readonly LogLevel[]): LogLevel {
  return WEB_LOG_LEVELS.find((level) => levels.includes(level)) ?? 'INFO'
}

export function filterLogs(items: RuntimeLogEntry[], view: LogViewOptions, query = ''): RuntimeLogEntry[] {
  const levels = new Set<string>(view.levels)
  const search = query.trim().toLowerCase()
  return items.filter((entry) => (
    levels.has(entry.level.toUpperCase())
    && (!search || `${entry.ts} ${entry.level} ${entry.logger} ${entry.message}`.toLowerCase().includes(search))
  )).slice(-view.limit)
}

export function serializeLogs(items: RuntimeLogEntry[]): string {
  return items.map((entry) => `${entry.ts} | ${entry.level.padEnd(8)} | ${entry.logger} | ${entry.message}`).join('\n')
}
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

export function appendToLogBuffer(
  buffer: RuntimeLogEntry[],
  incoming: RuntimeLogEntry[],
): RuntimeLogEntry[] {
  return trimLogs([...buffer, ...incoming])
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
