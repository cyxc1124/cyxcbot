import { describe, expect, it } from 'vitest'
import { computePolicyAfterToggle } from './restrictPolicy'

describe('message policy with an incomplete roster', () => {
  it('keeps the allowlist when enabling the last observed official session', () => {
    expect(computePolicyAfterToggle('official', true, ['official'], true, [], false))
      .toEqual({ restrict: true, enabled_ids: ['official'] })
  })

  it('preserves IDs outside the observed list', () => {
    expect(computePolicyAfterToggle('official', true, ['official'], true, ['1001', 'unseen'], false))
      .toEqual({ restrict: true, enabled_ids: ['1001', 'unseen', 'official'] })
    expect(computePolicyAfterToggle('official', false, ['official'], true, ['1001', 'official'], false))
      .toEqual({ restrict: true, enabled_ids: ['1001'] })
  })

  it('retains complete-roster behavior for existing callers', () => {
    expect(computePolicyAfterToggle('1001', true, ['1001'], true, []))
      .toEqual({ restrict: false, enabled_ids: [] })
  })
})
