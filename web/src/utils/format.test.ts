import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatDateTime } from './format'

afterEach(() => vi.unstubAllEnvs())

describe('formatDateTime', () => {
  it.each([
    '2026-10-31T07:42:15+00:00',
    '2026-10-31T07:42:15Z',
    '2026-10-31T15:42:15+08:00',
    '2026-10-31T07:42:15',
  ])('displays %s in the browser time zone', (iso) => {
    vi.stubEnv('TZ', 'Asia/Shanghai')
    expect(formatDateTime(iso)).toBe('2026/10/31 15:42:15')
  })

  it('displays the offset when the browser uses another time zone', () => {
    vi.stubEnv('TZ', 'America/New_York')
    const formatted = formatDateTime('2026-10-31T07:42:15+00:00')
    expect(formatted).toContain('2026/10/31')
    expect(formatted).toContain('03:42:15')
    expect(formatted).toContain('GMT-4')
  })
})
