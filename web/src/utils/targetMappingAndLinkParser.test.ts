import { describe, expect, it } from 'vitest'
import {
  buildPolicyPayload,
  buildToggleAllPayload,
  buildToggleAllSendVideoPayload,
  isAllPoliciesEnabled,
  isAllSendVideoEnabled,
  isNoPoliciesEnabled,
  isNoSendVideoEnabled,
} from './linkParserPolicy'
import {
  emptyForm,
  formFromTarget,
  getTargetDisplayName,
  getTargetId,
} from '../components/targetMapping/types'

describe('targetMapping types', () => {
  it('emptyForm defaults at_all based on target type', () => {
    expect(emptyForm('dynamic').at_all).toBe(false)
    expect(emptyForm('live').at_all).toBe(true)
    expect(emptyForm('x').at_all).toBe(false)
  })

  it('getTargetId reads uid, room_id or username', () => {
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
        'dynamic',
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
        'live',
      ),
    ).toBe('456')
    expect(
      getTargetId(
        {
          id: 3,
          username: 'elonmusk',
          name: null,
          enabled: true,
          at_all: false,
          group_ids: [],
          user_ids: [],
          created_at: '',
        },
        'x',
      ),
    ).toBe('elonmusk')
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
    expect(getTargetDisplayName(target, 'dynamic', 'UP 主')).toBe('UP 主 99')
    expect(getTargetDisplayName({ ...target, name: 'Alice' }, 'dynamic', 'UP 主')).toBe(
      'Alice',
    )
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
    expect(formFromTarget(target, 'live')).toEqual({
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
    expect(
      buildPolicyPayload(
        {
          video_enabled: false,
          live_enabled: false,
          dynamic_enabled: false,
          send_video_enabled: false,
        },
        { video_enabled: true },
      ),
    ).toEqual({
      video_enabled: true,
      live_enabled: false,
      dynamic_enabled: false,
      send_video_enabled: false,
      customized: true,
    })
    expect(
      buildPolicyPayload(
        {
          video_enabled: true,
          live_enabled: true,
          dynamic_enabled: false,
          send_video_enabled: false,
        },
        { dynamic_enabled: true },
      ),
    ).toEqual({
      video_enabled: true,
      live_enabled: true,
      dynamic_enabled: true,
      send_video_enabled: false,
      customized: true,
    })
    expect(
      buildPolicyPayload(
        {
          video_enabled: false,
          live_enabled: false,
          dynamic_enabled: false,
          send_video_enabled: false,
        },
        {},
      ),
    ).toEqual({
      video_enabled: false,
      live_enabled: false,
      dynamic_enabled: false,
      send_video_enabled: false,
      customized: false,
    })
  })

  it('clears send_video when video_enabled is off', () => {
    expect(
      buildPolicyPayload(
        {
          video_enabled: true,
          live_enabled: false,
          dynamic_enabled: false,
          send_video_enabled: true,
        },
        { video_enabled: false },
      ),
    ).toEqual({
      video_enabled: false,
      live_enabled: false,
      dynamic_enabled: false,
      send_video_enabled: false,
      customized: false,
    })
  })

  it('detects all enabled or all disabled policies', () => {
    const items = [
      {
        video_enabled: true,
        live_enabled: true,
        dynamic_enabled: true,
        send_video_enabled: false,
      },
      {
        video_enabled: true,
        live_enabled: true,
        dynamic_enabled: true,
        send_video_enabled: true,
      },
    ]
    // 「全部启用」只看三项解析，不要求发送视频
    expect(isAllPoliciesEnabled(items)).toBe(true)
    expect(isNoPoliciesEnabled(items)).toBe(false)

    const off = [
      {
        video_enabled: false,
        live_enabled: false,
        dynamic_enabled: false,
        send_video_enabled: false,
      },
      {
        video_enabled: false,
        live_enabled: false,
        dynamic_enabled: false,
        send_video_enabled: false,
      },
    ]
    expect(isAllPoliciesEnabled(off)).toBe(false)
    expect(isNoPoliciesEnabled(off)).toBe(true)

    expect(isAllPoliciesEnabled([])).toBe(false)
    expect(isNoPoliciesEnabled([])).toBe(false)
  })

  it('buildToggleAllPayload never bulk-enables send_video', () => {
    expect(buildToggleAllPayload(true)).toEqual({
      video_enabled: true,
      live_enabled: true,
      dynamic_enabled: true,
      send_video_enabled: false,
    })
    expect(buildToggleAllPayload(false)).toEqual({
      video_enabled: false,
      live_enabled: false,
      dynamic_enabled: false,
      send_video_enabled: false,
    })
  })

  it('buildToggleAllSendVideoPayload enables video_enabled when turning on', () => {
    expect(
      buildToggleAllSendVideoPayload(
        {
          video_enabled: false,
          live_enabled: true,
          dynamic_enabled: false,
          send_video_enabled: false,
        },
        true,
      ),
    ).toEqual({
      video_enabled: true,
      live_enabled: true,
      dynamic_enabled: false,
      send_video_enabled: true,
    })
    expect(
      buildToggleAllSendVideoPayload(
        {
          video_enabled: true,
          live_enabled: true,
          dynamic_enabled: true,
          send_video_enabled: true,
        },
        false,
      ),
    ).toEqual({
      video_enabled: true,
      live_enabled: true,
      dynamic_enabled: true,
      send_video_enabled: false,
    })
  })

  it('detects all/none send_video flags', () => {
    expect(
      isAllSendVideoEnabled([
        {
          video_enabled: true,
          live_enabled: false,
          dynamic_enabled: false,
          send_video_enabled: true,
        },
      ]),
    ).toBe(true)
    expect(
      isNoSendVideoEnabled([
        {
          video_enabled: true,
          live_enabled: true,
          dynamic_enabled: true,
          send_video_enabled: false,
        },
      ]),
    ).toBe(true)
  })
})
