import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createProxy, deleteProxy, testProxy, updateProxy } from '../../api/client'
import type { ProxyEntry } from '../../api/types'
import { ProxyCard } from './ProxyCard'
import { newProxyDraft, type ProxyDraft } from './proxyForm'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('../../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  createProxy: vi.fn(), deleteProxy: vi.fn(), testProxy: vi.fn(), updateProxy: vi.fn(),
}))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

const saved: ProxyEntry = {
  id: 'p1', name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: 'user', password_configured: true,
}
const BUSY = 2
let state: unknown[]
let stateIndex: number
let props: Parameters<typeof ProxyCard>[0]
const onProxiesChange = vi.fn()
const onDiscardNew = vi.fn()

function renderCard() { stateIndex = 0; return ProxyCard(props) }
function find(predicate: (item: Record<string, unknown>) => boolean) { return elements(renderCard()).find(predicate) }
function html() { return renderToStaticMarkup(<MemoryRouter>{renderCard()}</MemoryRouter>) }
function draft() { return state[0] as ProxyDraft }

function type(field: string, value: string) {
  ;(find((item) => item.id === `proxy-${draft().key}-${field}`)!.onChange as (event: unknown) => void)({ target: { value } })
}

function expand() { ;(find((item) => item['aria-expanded'] !== undefined)!.onClick as () => void)() }

async function settle() { await vi.waitFor(() => expect(state[BUSY]).toBeNull()) }

async function submit() {
  ;(find((item) => Boolean(item.onSubmit))!.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
  await settle()
}

describe('proxy card', () => {
  beforeEach(() => {
    state = []
    props = { proxy: saved, index: 0, usages: [], disabled: false, onProxiesChange, onDiscardNew }
    onProxiesChange.mockReset()
    onDiscardNew.mockReset()
    showToast.mockReset()
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(state[index]) : next
      }]
    }) as typeof useState)
    for (const mock of [createProxy, deleteProxy, testProxy, updateProxy]) vi.mocked(mock).mockReset()
  })

  it('starts collapsed with a summary and usage count, never showing the password', () => {
    props = { ...props, usages: [{ label: 'X（推文订阅、链接解析）', proxyId: 'p1', to: '/x/account' }] }
    const collapsed = html()
    expect(collapsed).toContain('aria-expanded="false"')
    expect(collapsed).toContain('SOCKS5 · hk.proxy.test:1080 · 需要认证')
    expect(collapsed).toContain('1 项功能在用')
    expect(collapsed).not.toContain('proxy-p1-host')
    expand()
    const opened = html()
    expect(opened).toContain('已配置，留空保留原密码')
    expect(opened).toContain('href="/x/account"')
  })

  it('saves only this proxy and collapses', async () => {
    expand()
    type('port', '1081')
    expect(html()).toContain('有未保存修改')
    const updated = { ...saved, port: 1081 }
    vi.mocked(updateProxy).mockResolvedValue({ id: 'p1', proxies: [updated] })
    await submit()
    expect(updateProxy).toHaveBeenCalledWith('p1', {
      name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1081, username: 'user',
    })
    expect(onProxiesChange).toHaveBeenCalledWith({ id: 'p1', proxies: [updated] })
    expect(state[1]).toBe(false)
    expect(draft().port).toBe(1081)
  })

  it('requires the password again before saving or testing a new host', async () => {
    expand()
    type('host', 'other.test')
    await submit()
    expect(updateProxy).not.toHaveBeenCalled()
    expect(showToast).toHaveBeenCalledWith('error', expect.stringContaining('重新填写密码'))
    ;(find((item) => item.children === '测试连接')!.onClick as () => void)()
    expect(testProxy).not.toHaveBeenCalled()
    expect(html()).toContain('修改主机后，请先重新填写密码')
  })

  it('tests the unsaved values and shows per-service results', async () => {
    expand()
    type('password', 'typed-pass')
    vi.mocked(testProxy).mockResolvedValue({
      success: true, message: '经此代理可访问 1/1 个服务',
      targets: [{ name: 'X API', url: 'https://x', reachable: true, message: '可访问（HTTP 200）', status_code: 200, latency_ms: 80 }],
    })
    ;(find((item) => item.children === '测试连接')!.onClick as () => void)()
    await settle()
    expect(testProxy).toHaveBeenCalledWith({
      id: 'p1', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: 'user', password: 'typed-pass',
    })
    expect(html()).toContain('X API：可访问（HTTP 200），80 ms')
  })

  it('blocks deleting a proxy that features still use and deletes unused ones after confirmation', async () => {
    props = { ...props, usages: [{ label: 'X（推文订阅、链接解析）', proxyId: 'p1', to: '/x/account' }] }
    expand()
    expect(find((item) => item.children === '删除')!.disabled).toBe(true)
    expect(html()).toContain('仍有功能在使用此代理')

    props = { ...props, usages: [] }
    ;(find((item) => item.children === '删除')!.onClick as () => void)()
    vi.mocked(deleteProxy).mockResolvedValue({ id: null, proxies: [] })
    ;(find((item) => item.title === '删除代理')!.onConfirm as () => void)()
    await settle()
    expect(deleteProxy).toHaveBeenCalledWith('p1')
    expect(onProxiesChange).toHaveBeenCalledWith({ id: null, proxies: [] })
  })

  it('creates a new proxy or discards it', async () => {
    props = { ...props, proxy: undefined, initialDraft: newProxyDraft(), index: 1 }
    expect(html()).toContain('新代理 2')
    type('name', '本地')
    type('host', '127.0.0.1')
    const created = { ...saved, id: 'p2', name: '本地', scheme: 'http' as const, host: '127.0.0.1', port: 7890, username: '', password_configured: false }
    vi.mocked(createProxy).mockResolvedValue({ id: 'p2', proxies: [saved, created] })
    await submit()
    expect(createProxy).toHaveBeenCalledWith({ name: '本地', scheme: 'http', host: '127.0.0.1', port: 7890, username: '' })
    expect(onProxiesChange).toHaveBeenCalledOnce()

    state = []
    ;(find((item) => item.children === '取消添加')!.onClick as () => void)()
    expect(onDiscardNew).toHaveBeenCalledOnce()
  })
})
