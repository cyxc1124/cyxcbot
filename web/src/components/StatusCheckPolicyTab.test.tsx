import { isValidElement } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getGroupStatusPolicy,
  getPrivateStatusPolicy,
  updateGroupStatusPolicy,
  updatePrivateStatusPolicy,
} from '../api/client'
import { StatusCheckPolicyTab } from './StatusCheckPolicyTab'

// Invoke the real JSX callbacks before rerendering to cover the synchronous save lock.
const hooks = vi.hoisted(() => ({
  slots: [] as unknown[],
  cursor: 0,
  load: (() => Promise.resolve()) as () => Promise<void>,
  showToast: vi.fn(),
}))

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState(initial: unknown) {
    const index = hooks.cursor++
    if (!(index in hooks.slots)) hooks.slots[index] = initial
    return [hooks.slots[index], (value: unknown) => { hooks.slots[index] = value }]
  },
  useRef(initial: unknown) {
    const index = hooks.cursor++
    if (!(index in hooks.slots)) hooks.slots[index] = { current: initial }
    return hooks.slots[index]
  },
  useCallback: <T,>(callback: T) => callback,
  useMemo: <T,>(factory: () => T) => factory(),
}))
vi.mock('../api/client', () => ({
  getGroupStatusPolicy: vi.fn(),
  getPrivateStatusPolicy: vi.fn(),
  updateGroupStatusPolicy: vi.fn(),
  updatePrivateStatusPolicy: vi.fn(),
}))
vi.mock('../contexts/ToastContext', () => ({ useToast: () => hooks }))
vi.mock('../hooks/useLoadingOnKeyChange', () => ({
  useLoadingOnKeyChange: () => [false, vi.fn()],
}))
vi.mock('../hooks/useMountAsync', () => ({
  useMountAsync: (load: () => Promise<void>) => { hooks.load = load },
}))

type Button = ReactElement<{
  children?: ReactNode
  role?: string
  disabled?: boolean
  'aria-checked'?: boolean
  onClick: (event: { stopPropagation: () => void }) => void
}>

function buttons(node: ReactNode): Button[] {
  if (Array.isArray(node)) return node.flatMap(buttons)
  if (!isValidElement<Button['props']>(node)) return []
  if (typeof node.type === 'function') {
    return buttons((node.type as (props: Button['props']) => ReactNode)(node.props))
  }
  return [...(node.type === 'button' ? [node] : []), ...buttons(node.props.children)]
}

function click(button: Button) {
  button.props.onClick({ stopPropagation: vi.fn() })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const display = { show_detailed: true, show_uptime: true, show_memory: true }
const groupPolicy = {
  restrict: true,
  enabled_group_ids: ['1001'],
  groups: ['1001', '1002', '1003'].map((id) => ({ group_id: id, group_name: id })),
  display,
  group_list_available: true,
}
const friendPolicy = {
  restrict: true,
  enabled_user_ids: ['1001'],
  users: ['1001', '1002', '1003'].map((id) => ({ user_id: id, nickname: id })),
  display,
  friend_list_available: true,
}

beforeEach(() => {
  vi.resetAllMocks()
  hooks.slots = []
  hooks.cursor = 0
  vi.mocked(getGroupStatusPolicy).mockResolvedValue(groupPolicy)
  vi.mocked(getPrivateStatusPolicy).mockResolvedValue(friendPolicy)
})

describe.each(['group', 'friend'] as const)('%s status policy saves', (scope) => {
  function render() {
    hooks.cursor = 0
    const controls = buttons(StatusCheckPolicyTab({ scope }))
    return {
      all: controls,
      switches: controls.filter((button) => button.props.role === 'switch'),
      enableAll: controls.find((button) => button.props.children === '全部启用')!,
    }
  }

  it.each(['row', 'all', 'display'] as const)(
    'serializes %s changes and resumes with the saved policy',
    async (operation) => {
      render()
      await hooks.load()
      const controls = render()
      const groupPending = deferred<typeof groupPolicy>()
      const friendPending = deferred<typeof friendPolicy>()
      vi.mocked(updateGroupStatusPolicy).mockReturnValue(groupPending.promise)
      vi.mocked(updatePrivateStatusPolicy).mockReturnValue(friendPending.promise)
      const update = scope === 'group' ? updateGroupStatusPolicy : updatePrivateStatusPolicy

      click(operation === 'row' ? controls.switches[4]
        : operation === 'all' ? controls.enableAll : controls.switches[0])
      // These callbacks still belong to the render before the save began.
      click(controls.switches[5])
      click(controls.enableAll)
      click(controls.switches[1])
      expect(update).toHaveBeenCalledTimes(1)
      expect(render().all.every((button) => button.props.disabled)).toBe(true)

      const saved = {
        restrict: operation !== 'all',
        display: operation === 'display' ? { ...display, show_detailed: false } : display,
      }
      const savedIds = operation === 'row' ? ['1001', '1002']
        : operation === 'all' ? [] : ['1001']
      groupPending.resolve({ ...groupPolicy, ...saved, enabled_group_ids: savedIds })
      friendPending.resolve({ ...friendPolicy, ...saved, enabled_user_ids: savedIds })
      await Promise.all([groupPending.promise, friendPending.promise])

      const refreshed = render()
      expect(refreshed.switches.every((button) => !button.props.disabled)).toBe(true)
      click(refreshed.switches[5])
      expect(update).toHaveBeenCalledTimes(2)
      const nextIds = operation === 'row' ? []
        : operation === 'all' ? ['1001', '1002'] : ['1001', '1003']
      expect(update).toHaveBeenLastCalledWith(scope === 'group'
        ? { restrict: operation !== 'row', enabled_group_ids: nextIds }
        : { restrict: operation !== 'row', enabled_user_ids: nextIds })
      await Promise.all([groupPending.promise, friendPending.promise])
    },
  )

  it.each(['row', 'all', 'display'] as const)(
    'rolls back a failed %s save and releases all controls',
    async (operation) => {
      render()
      await hooks.load()
      const controls = render()
      const pending = deferred<never>()
      vi.mocked(updateGroupStatusPolicy).mockReturnValue(pending.promise)
      vi.mocked(updatePrivateStatusPolicy).mockReturnValue(pending.promise)
      const update = scope === 'group' ? updateGroupStatusPolicy : updatePrivateStatusPolicy

      click(operation === 'row' ? controls.switches[4]
        : operation === 'all' ? controls.enableAll : controls.switches[0])
      pending.reject(new Error('保存失败'))
      await pending.promise.catch(() => {})

      const restored = render()
      expect(restored.switches.every((button) => !button.props.disabled)).toBe(true)
      expect(restored.switches.map((button) => button.props['aria-checked']))
        .toEqual([true, true, true, true, false, false])
      expect(hooks.showToast).toHaveBeenCalledWith('error', '保存失败')
      click(restored.switches[4])
      expect(update).toHaveBeenCalledTimes(2)
      expect(update).toHaveBeenLastCalledWith(scope === 'group'
        ? { restrict: true, enabled_group_ids: ['1001', '1002'] }
        : { restrict: true, enabled_user_ids: ['1001', '1002'] })
      await pending.promise.catch(() => {})
    },
  )
})
