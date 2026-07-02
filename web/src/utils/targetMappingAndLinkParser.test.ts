import { describe, expect, it } from 'vitest'
import {
  buildPolicyPayload,
  buildToggleAllPayload,
  isAllPoliciesEnabled,
  isNoPoliciesEnabled,
} from './linkParserPolicy'
import {
  emptyForm,
  formFromTarget,
  getTargetDisplayName,
  getTargetId,
} from '../components/targetMapping/types'

describe('targetMapping types', () => {
  it('emptyForm defaults at_all based on target type', () => {
    expect(emptyForm(true).at_all).toBe(false)
    expect(emptyForm(false).at_all).toBe(true)
  })

  it('getTargetId reads uid or room_id', () => {
    expect(
      getTargetId(
        {
          id: 1,
          uid: '123',
          name: null,
          enabled: true,
          at_all: false,
          group_ids: [],
          user_ids: [],
          created_at: '',
        },
        true,
      ),
    ).toBe('123')
    expect(
      getTargetId(
        {
          id: 2,
          room_id: '456',
          name: null,
          enabled: true,
          at_all: true,
          group_ids: [],
          user_ids: [],
          created_at: '',
        },
        false,
      ),
    ).toBe('456')
  })

  it('getTargetDisplayName falls back to label plus id', () => {
    const target = {
      id: 1,
      uid: '99',
      name: null,
      enabled: true,
      at_all: false,
      group_ids: [],
      user_ids: [],
      created_at: '',
    }
    expect(getTargetDisplayName(target, true, 'UP 主')).toBe('UP 主 99')
    expect(getTargetDisplayName({ ...target, name: 'Alice' }, true, 'UP 主')).toBe('Alice')
  })

  it('formFromTarget copies subscription fields', () => {
    const target = {
      id: 3,
      room_id: '100',
      name: 'Room',
      enabled: false,
      at_all: true,
      group_ids: ['1'],
      user_ids: ['2'],
      created_at: '',
    }
    expect(formFromTarget(target, false)).toEqual({
      id: '100',
      name: 'Room',
      enabled: false,
      at_all: true,
      group_ids: ['1'],
      user_ids: ['2'],
    })
  })
})

describe('linkParserPolicy utils', () => {
  it('buildPolicyPayload normalizes booleans and customized flag', () => {
    expect(buildPolicyPayload({ video_enabled: false, live_enabled: false }, { video_enabled: true })).toEqual({
      video_enabled: true,
      live_enabled: false,
      customized: true,
    })
    expect(buildPolicyPayload({ video_enabled: true, live_enabled: true }, { live_enabled: false })).toEqual({
      video_enabled: true,
      live_enabled: false,
      customized: true,
    })
    expect(buildPolicyPayload({ video_enabled: true, live_enabled: false }, { live_enabled: false })).toEqual({
      video_enabled: true,
      live_enabled: false,
      customized: true,
    })
    expect(buildPolicyPayload({ video_enabled: false, live_enabled: false }, {})).toEqual({
      video_enabled: false,
      live_enabled: false,
      customized: false,
    })
  })

  it('detects all enabled or all disabled policies', () => {
    const items = [
      { video_enabled: true, live_enabled: true },
      { video_enabled: true, live_enabled: true },
    ]
    expect(isAllPoliciesEnabled(items)).toBe(true)
    expect(isNoPoliciesEnabled(items)).toBe(false)

    const off = [
      { video_enabled: false, live_enabled: false },
      { video_enabled: false, live_enabled: false },
    ]
    expect(isAllPoliciesEnabled(off)).toBe(false)
    expect(isNoPoliciesEnabled(off)).toBe(true)

    expect(isAllPoliciesEnabled([])).toBe(false)
    expect(isNoPoliciesEnabled([])).toBe(false)
  })

  it('buildToggleAllPayload mirrors bulk enable/disable', () => {
    expect(buildToggleAllPayload(true)).toEqual({ video_enabled: true, live_enabled: true })
    expect(buildToggleAllPayload(false)).toEqual({ video_enabled: false, live_enabled: false })
  })
})
