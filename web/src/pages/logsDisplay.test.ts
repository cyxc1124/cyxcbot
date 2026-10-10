import { describe, expect, it } from 'vitest'
import type { RuntimeLogEntry } from '../api/types'
import {
  DISPLAY_MAX,
  LOG_FLUSH_MS,
  NEAR_BOTTOM_PX,
  appendToLogBuffer,
  isNearBottom,
  mergeLogs,
  trimLogs,
} from './logsDisplay'

function entry(n: number, sessionId = 'sess-a'): RuntimeLogEntry {
  return {
    session_id: sessionId,
    entry_id: n,
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

  it('isNearBottom treats edge and small slack as following', () => {
    expect(
      isNearBottom({ scrollHeight: 1000, scrollTop: 800, clientHeight: 200 }),
    ).toBe(true)
    expect(
      isNearBottom({
        scrollHeight: 1000,
        scrollTop: 800 - NEAR_BOTTOM_PX,
        clientHeight: 200,
      }),
    ).toBe(true)
    expect(
      isNearBottom({
        scrollHeight: 1000,
        scrollTop: 800 - NEAR_BOTTOM_PX - 1,
        clientHeight: 200,
      }),
    ).toBe(false)
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

  it('mergeLogs skips entries already present by session and entry_id', () => {
    const prev = [entry(1), entry(2)]
    const merged = mergeLogs(prev, [entry(1), entry(3)])
    expect(merged).toHaveLength(3)
    expect(merged.map((item) => item.entry_id)).toEqual([1, 2, 3])
  })

  it('mergeLogs keeps order when websocket replays REST history', () => {
    const prev = Array.from({ length: DISPLAY_MAX }, (_, i) => entry(i + 1))
    const replay = Array.from({ length: DISPLAY_MAX }, (_, i) => entry(i + 1))
    const merged = mergeLogs(prev, replay)
    expect(merged).toBe(prev)
    expect(merged[0]?.entry_id).toBe(1)
    expect(merged.at(-1)?.entry_id).toBe(DISPLAY_MAX)
  })

  it('mergeLogs replaces list when log session changes after restart', () => {
    const prev = [entry(1, 'old-session'), entry(2, 'old-session')]
    const merged = mergeLogs(prev, [entry(1, 'new-session'), entry(2, 'new-session')])
    expect(merged).toHaveLength(2)
    expect(merged.every((item) => item.session_id === 'new-session')).toBe(true)
  })

  it('mergeLogs appends entries with reused ids from a new session', () => {
    const prev = [entry(1, 'old-session'), entry(2, 'old-session')]
    const merged = mergeLogs(prev, [entry(1, 'new-session')])
    expect(merged).toHaveLength(1)
    expect(merged[0]?.session_id).toBe('new-session')
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

  it('bounds a long paused stream to the newest DISPLAY_MAX entries in arrival order', () => {
    let buffer: RuntimeLogEntry[] = []
    for (let i = 0; i < 12001; i++) {
      buffer = appendToLogBuffer(buffer, [entry(i)])
      expect(buffer.length).toBeLessThanOrEqual(DISPLAY_MAX)
    }
    expect(buffer.map((item) => item.entry_id)).toEqual(
      Array.from({ length: DISPLAY_MAX }, (_, i) => 10001 + i),
    )
    const resumed = mergeLogs([entry(0)], buffer)
    expect(resumed).toEqual(buffer)
  })

  it('bounds an oversized pending batch moved into the paused buffer', () => {
    const buffer = [entry(0)]
    const pending = Array.from({ length: 10001 }, (_, i) => entry(i + 1))
    const result = appendToLogBuffer(buffer, pending)
    expect(result).toEqual(pending.slice(-DISPLAY_MAX))
    expect(buffer).toEqual([entry(0)])
  })

  it('keeps buffered replays for the existing resume deduplication', () => {
    const displayed = [entry(1), entry(2)]
    const buffer = appendToLogBuffer([entry(2)], [entry(3)])
    expect(mergeLogs(displayed, buffer).map((item) => item.entry_id)).toEqual([1, 2, 3])
  })

  it('starts a fresh buffer after clearing paused logs', () => {
    let buffer = appendToLogBuffer([], [entry(1), entry(2)])
    expect(buffer).toHaveLength(2)
    buffer = []
    buffer = appendToLogBuffer(buffer, [entry(3)])
    expect(mergeLogs([], buffer)).toEqual([entry(3)])
  })
})
