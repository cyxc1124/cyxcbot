import { describe, expect, it } from 'vitest'
import type { RuntimeLogEntry } from '../api/types'
import { DISPLAY_MAX, LOG_FLUSH_MS, mergeLogs, trimLogs } from './logsDisplay'

function entry(n: number): RuntimeLogEntry {
  return {
    ts: `2026-01-01T00:00:0${n % 10}.000Z`,
    level: 'INFO',
    logger: 'test',
    message: `message-${n}`,
  }
}

describe('logsDisplay', () => {
  it('keeps flush interval within suggested batching window', () => {
    expect(LOG_FLUSH_MS).toBeGreaterThanOrEqual(100)
    expect(LOG_FLUSH_MS).toBeLessThanOrEqual(250)
  })

  it('mergeLogs returns previous list when incoming is empty', () => {
    const prev = [entry(1)]
    expect(mergeLogs(prev, [])).toBe(prev)
  })

  it('mergeLogs appends incoming entries', () => {
    const prev = [entry(1)]
    const merged = mergeLogs(prev, [entry(2), entry(3)])
    expect(merged).toHaveLength(3)
    expect(merged[2]?.message).toBe('message-3')
  })

  it('mergeLogs trims to DISPLAY_MAX', () => {
    const prev = Array.from({ length: DISPLAY_MAX }, (_, i) => entry(i))
    const merged = mergeLogs(prev, [entry(9999)])
    expect(merged).toHaveLength(DISPLAY_MAX)
    expect(merged.at(-1)?.message).toBe('message-9999')
    expect(merged[0]?.message).toBe('message-1')
  })

  it('trimLogs keeps arrays at or below DISPLAY_MAX', () => {
    const items = Array.from({ length: DISPLAY_MAX - 1 }, (_, i) => entry(i))
    expect(trimLogs(items)).toBe(items)
    expect(trimLogs(items).length).toBe(DISPLAY_MAX - 1)
  })
})
