import { describe, expect, it } from 'vitest'
import { resolveOneBotListStatus } from './rosterStatus'

describe('OneBot roster status', () => {
  it('distinguishes an unused OneBot from an incomplete connected roster', () => {
    expect(resolveOneBotListStatus('offline', false)).toBe('offline')
    expect(resolveOneBotListStatus('incomplete', false)).toBe('incomplete')
    expect(resolveOneBotListStatus('ok', true)).toBe('ok')
  })

  it('keeps unavailable rosters protected with older API responses', () => {
    expect(resolveOneBotListStatus(undefined, false)).toBe('incomplete')
    expect(resolveOneBotListStatus(null, false)).toBe('incomplete')
    expect(resolveOneBotListStatus(undefined, true)).toBe('ok')
  })
})
