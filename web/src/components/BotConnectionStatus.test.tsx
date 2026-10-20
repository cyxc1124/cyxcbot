import { renderToStaticMarkup } from 'react-dom/server'
import type { AnchorHTMLAttributes } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getBotConnectionsStatus } from '../api/client'
import type { BotConnectionsStatus } from '../api/types'
import { BotConnectionStatus } from './BotConnectionStatus'

const hooks = vi.hoisted(() => ({
  states: [] as unknown[],
  cursor: 0,
  effects: [] as (() => (() => void))[],
  details: { current: null as HTMLDetailsElement | null },
}))

vi.mock('react', async (original) => ({
  ...await original<typeof import('react')>(),
  useState(initial: unknown) {
    const index = hooks.cursor++
    if (!(index in hooks.states)) hooks.states[index] = initial
    return [hooks.states[index], (value: unknown) => { hooks.states[index] = value }]
  },
  useEffect(effect: () => (() => void)) { hooks.effects.push(effect) },
  useRef: () => hooks.details,
  useId: () => 'bot-connections',
}))
vi.mock('react-router-dom', () => ({
  Link: ({ to, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }) => <a href={to} {...props} />,
}))
vi.mock('../api/client', () => ({ getBotConnectionsStatus: vi.fn() }))

const status: BotConnectionsStatus = {
  qq: { connected: true, bot_count: 1, bots: [{ qq: '10001', nickname: '示例机器人' }], message: '已连接 1 个 QQ 账号' },
  official_qq: { connected: false, configured: false, app_id: '', is_sandbox: false, use_websocket: true, message: '未配置官方 Bot' },
}
let cleanups: (() => void)[] = []
let listeners: Map<string, EventListener>

function render() {
  hooks.cursor = 0
  hooks.effects = []
  return renderToStaticMarkup(BotConnectionStatus())
}

function mount() {
  render()
  cleanups = hooks.effects.map(effect => effect())
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
  hooks.states = []
  hooks.details.current = null
  listeners = new Map()
  vi.stubGlobal('window', { setInterval, clearInterval, setTimeout, clearTimeout })
  vi.stubGlobal('document', {
    visibilityState: 'visible',
    addEventListener: (name: string, listener: EventListener) => listeners.set(name, listener),
    removeEventListener: (name: string) => listeners.delete(name),
  })
  vi.mocked(getBotConnectionsStatus).mockResolvedValue(status)
})

afterEach(() => {
  cleanups.forEach(cleanup => cleanup())
  cleanups = []
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Bot connection indicator', () => {
  it('starts with checking states and gives the compact trigger a complete accessible label', () => {
    const html = render()
    expect(html).toContain('aria-label="Bot 连接：OneBot 检查中，官方 Bot 检查中"')
    expect(html).toContain('aria-controls="bot-connections"')
    expect(html).toContain('href="/settings/official-qq"')
  })

  it.each([
    [false, false, true, '未配置'],
    [false, true, true, '等待连接'],
    [true, true, true, '已连接'],
    [false, true, false, '等待连接'],
    [true, true, false, '已连接'],
  ])('distinguishes configured and connected official bots (%s, %s, %s)', (connected, configured, use_websocket, label) => {
    hooks.states = [{ ...status, official_qq: { ...status.official_qq, connected, configured, use_websocket } }, false]
    const html = render()
    expect(html).toContain(`aria-label="Bot 连接：OneBot 已连接，官方 Bot ${label}"`)
    expect(html.includes('Webhook 按有效事件识别接入')).toBe(configured && !use_websocket)
  })

  it('polls, clears stale online state on failure, and recovers', async () => {
    mount()
    await Promise.resolve()
    expect(render()).toContain('OneBot 已连接')
    vi.mocked(getBotConnectionsStatus).mockRejectedValueOnce(new Error('offline'))
    await vi.advanceTimersByTimeAsync(30000)
    const failed = render()
    expect(failed).toContain('OneBot 状态未知')
    expect(failed).not.toContain('OneBot 已连接')
    expect(failed).toContain('role="alert"')
    await vi.advanceTimersByTimeAsync(30000)
    expect(render()).toContain('OneBot 已连接')
    expect(render()).not.toContain('role="alert"')
  })

  it('times out a stalled refresh, drops stale online state, and retries', async () => {
    mount()
    await Promise.resolve()
    vi.mocked(getBotConnectionsStatus).mockImplementation(signal => new Promise((_, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
    }))
    await vi.advanceTimersByTimeAsync(30000)
    expect(getBotConnectionsStatus).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(10000)
    expect(render()).toContain('OneBot 状态未知')
    vi.mocked(getBotConnectionsStatus).mockResolvedValue(status)
    await vi.advanceTimersByTimeAsync(20000)
    expect(getBotConnectionsStatus).toHaveBeenCalledTimes(3)
    expect(render()).toContain('OneBot 已连接')
  })

  it('skips polling while hidden and refreshes the disconnected state when visible', async () => {
    mount()
    await Promise.resolve()
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    await vi.advanceTimersByTimeAsync(60000)
    expect(getBotConnectionsStatus).toHaveBeenCalledTimes(1)
    vi.mocked(getBotConnectionsStatus).mockResolvedValue({ ...status, qq: { ...status.qq, connected: false, bot_count: 0, bots: [], message: '未连接 OneBot' } })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    listeners.get('visibilitychange')!(new Event('visibilitychange'))
    await Promise.resolve()
    expect(getBotConnectionsStatus).toHaveBeenCalledTimes(2)
    expect(render()).toContain('Bot 连接：OneBot 未连接，官方 Bot 未配置')
  })

  it('does not overlap requests or update state after unmount', async () => {
    let resolve!: (value: BotConnectionsStatus) => void
    vi.mocked(getBotConnectionsStatus).mockReturnValue(new Promise(done => { resolve = done }))
    mount()
    listeners.get('visibilitychange')!(new Event('visibilitychange'))
    listeners.get('visibilitychange')!(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(9000)
    expect(getBotConnectionsStatus).toHaveBeenCalledTimes(1)
    cleanups.forEach(cleanup => cleanup())
    cleanups = []
    expect(vi.mocked(getBotConnectionsStatus).mock.calls[0][0].aborted).toBe(true)
    resolve(status)
    await Promise.resolve()
    expect(hooks.states).toEqual([null, false])
    expect(listeners.size).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('closes on outside pointer and Escape, returning keyboard focus to the trigger', () => {
    const focus = vi.fn()
    hooks.details.current = { open: true, contains: () => false, querySelector: () => ({ focus }) } as unknown as HTMLDetailsElement
    mount()
    listeners.get('pointerdown')!({ target: {} } as Event)
    expect(hooks.details.current!.open).toBe(false)
    hooks.details.current!.open = true
    listeners.get('keydown')!({ key: 'Escape' } as unknown as Event)
    expect(hooks.details.current!.open).toBe(false)
    expect(focus).toHaveBeenCalledOnce()
  })
})
