import { useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { updateGroupStatusPolicy, updatePrivateStatusPolicy } from '../api/client'
import { StatusCheckPolicyTab } from './StatusCheckPolicyTab'

const { switches } = vi.hoisted(() => ({
  switches: [] as { disabled: boolean; onChange: (checked: boolean) => void }[],
}))

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
}))
vi.mock('../hooks/useLoadingOnKeyChange', () => ({
  useLoadingOnKeyChange: () => [false, vi.fn()],
}))
vi.mock('../contexts/ToastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock('../api/client', () => ({
  getGroupStatusPolicy: vi.fn(),
  getPrivateStatusPolicy: vi.fn(),
  updateGroupStatusPolicy: vi.fn(),
  updatePrivateStatusPolicy: vi.fn(),
}))
vi.mock('./ToggleSwitch', () => ({
  ToggleSwitch: (props: typeof switches[number]) => {
    switches.push(props)
    return <button role="switch" disabled={props.disabled} />
  },
}))

const display = { show_detailed: true, show_uptime: true, show_memory: true }

function renderPolicy(
  scope: 'group' | 'friend',
  { restrict = true, available = false, enabledIds = ['unseen'], numericRow = true } = {},
) {
  const rows = [
    { id: 'official', source: 'official' as const },
    ...(numericRow ? [{ id: '1001', source: 'onebot' as const }] : []),
  ]
  const groups = rows.map((row) => ({ group_id: row.id, group_name: row.id, source: row.source }))
  const users = rows.map((row) => ({ user_id: row.id, nickname: row.id, source: row.source }))
  const arrays = [groups, users, enabledIds]
  let trueStateCount = 0
  vi.mocked(useState).mockImplementation((initial?: unknown) => {
    const value = Array.isArray(initial)
      ? arrays.shift()
      : initial === true
        ? ++trueStateCount === 1 ? restrict : available
        : initial === 'ok' ? 'offline' : initial
    return [value, vi.fn()]
  })
  vi.mocked(updateGroupStatusPolicy).mockResolvedValue({
    restrict, enabled_group_ids: enabledIds, groups, display, group_list_available: available,
    onebot_list_status: available ? 'ok' : 'offline',
  })
  vi.mocked(updatePrivateStatusPolicy).mockResolvedValue({
    restrict, enabled_user_ids: enabledIds, users, display, friend_list_available: available,
    onebot_list_status: available ? 'ok' : 'offline',
  })
  return renderToStaticMarkup(<StatusCheckPolicyTab scope={scope} />)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useState).mockReset()
  switches.length = 0
})

describe.each(['group', 'friend'] as const)('official %s status policy', (scope) => {
  it('allows only official rows with an incomplete roster and keeps bulk controls locked', () => {
    const html = renderPolicy(scope)
    expect(switches.slice(0, 3).every((control) => !control.disabled)).toBe(true)
    expect(switches.slice(3).map((control) => control.disabled)).toEqual([false, true])
    const bulk = html.match(/<button[^>]*disabled=""[^>]*>全部(?:启用|关闭)<\/button>/g)
    expect(bulk).toHaveLength(2)
    expect(html).toContain('官方会话可独立配置')
  })

  it('keeps every row locked in global mode until the roster is complete', () => {
    renderPolicy(scope, { restrict: false })
    expect(switches.slice(3).every((control) => control.disabled)).toBe(true)
    expect(switches.slice(0, 3).every((control) => !control.disabled)).toBe(true)
  })

  it('keeps the whitelist when enabling the last observed official session', async () => {
    renderPolicy(scope, { enabledIds: [], numericRow: false })
    switches[3].onChange(true)
    await Promise.resolve()
    const update = scope === 'group' ? updateGroupStatusPolicy : updatePrivateStatusPolicy
    expect(update).toHaveBeenCalledWith({
      restrict: true,
      [scope === 'group' ? 'enabled_group_ids' : 'enabled_user_ids']: ['official'],
    })
  })

  it('retains normal OneBot row edits with a complete roster', () => {
    renderPolicy(scope, { available: true })
    expect(switches.slice(3).every((control) => !control.disabled)).toBe(true)
  })
})
