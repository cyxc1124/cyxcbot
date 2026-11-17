import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProxiesResult, ProxyEntry, Settings } from '../../api/types'
import type { ProxyDraft, ProxyUsage } from './proxyForm'
import { useSettingsForm } from './SettingsContext'
import { SettingsProxiesPage } from './SettingsProxies'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

type CardProps = {
  proxy?: ProxyEntry
  initialDraft?: ProxyDraft
  usages: ProxyUsage[]
  onProxiesChange: (result: ProxiesResult) => void
  onDiscardNew?: () => void
}

const hk: ProxyEntry = { id: 'p1', name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: '', password_configured: false }
const local: ProxyEntry = { id: 'p2', name: '本地', scheme: 'http', host: '127.0.0.1', port: 7890, username: '', password_configured: false }
let state: unknown[]
let stateIndex: number
let settings: Settings
const setSettings = vi.fn((next: unknown) => {
  settings = typeof next === 'function' ? (next as (value: Settings) => Settings)(settings) : next as Settings
})

function renderPage() { stateIndex = 0; return SettingsProxiesPage() }
function html() { return renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>) }
function cards() { return elements(renderPage()).filter((item) => typeof item.onProxiesChange === 'function') as CardProps[] }

describe('shared proxies page', () => {
  beforeEach(() => {
    state = []
    settings = {
      proxies: [hk, local],
      x_proxy_id: 'p1',
      ai_image_openai_proxy_id: 'deleted',
      ai_image_vision_providers: [{ id: 'v1', name: 'GPT', proxy_id: 'p1' }],
    } as unknown as Settings
    setSettings.mockClear()
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(state[index]) : next
      }]
    }) as typeof useState)
    vi.mocked(useSettingsForm).mockImplementation(() => ({
      settings, setSettings, formDisabled: false,
    }) as unknown as ReturnType<typeof useSettingsForm>)
  })

  it('shows which proxy every feature uses with links to change it', () => {
    const output = html()
    expect(output).toContain('X（推文订阅、链接解析）')
    expect(output).toContain('「香港」SOCKS5 hk.proxy.test:1080')
    expect(output).toContain('所选代理已删除，当前直接连接')
    expect(output).toContain('AI 图片检测 · 视觉模型「GPT」')
    expect(output).toContain('href="/x/account"')
    expect(output).toContain('href="/ai-image/sources"')
    expect(output).toContain('href="/ai-image/vision"')
    expect(output.match(/aria-expanded="false"/g)).toHaveLength(2)
  })

  it('passes each card only the features that use it', () => {
    const [first, second] = cards()
    expect(first.usages.map((usage) => usage.label)).toEqual(['X（推文订阅、链接解析）', 'AI 图片检测 · 视觉模型「GPT」'])
    expect(second.usages).toEqual([])
  })

  it('adds new proxies and replaces only the proxy list after saving', () => {
    ;(elements(renderPage()).find((item) => item.children === '添加代理')!.onClick as () => void)()
    ;(elements(renderPage()).find((item) => item.children === '添加代理')!.onClick as () => void)()
    const drafts = cards().filter((card) => card.initialDraft)
    expect(drafts).toHaveLength(2)
    const created = { ...local, id: 'p3', name: '新' }
    drafts[0].onProxiesChange({ id: 'p3', proxies: [hk, local, created] })
    expect(settings.proxies.map((proxy) => proxy.id)).toEqual(['p1', 'p2', 'p3'])
    expect(settings.x_proxy_id).toBe('p1')
    expect(cards().filter((card) => card.initialDraft)).toHaveLength(1)
    cards().find((card) => card.initialDraft)!.onDiscardNew!()
    expect(cards().filter((card) => card.initialDraft)).toHaveLength(0)
  })

  it('explains that nothing uses a proxy until a feature selects it', () => {
    settings = { ...settings, proxies: [], x_proxy_id: '', ai_image_openai_proxy_id: '', ai_image_vision_providers: [] }
    const output = html()
    expect(output).toContain('还没有添加代理，所有功能都直接连接')
    expect(output).toContain('代理本身不会自动生效')
  })
})
