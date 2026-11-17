import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createVisionProvider,
  deleteVisionProvider,
  getVisionBalance,
  listVisionModels,
  testVisionProvider,
  updateVisionProvider,
} from '../../api/client'
import type { AiImageVisionProvider, ProxyEntry } from '../../api/types'
import { newDraft, type VisionProviderDraft } from './aiImageVisionForm'
import { VisionProviderCard } from './VisionProviderCard'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('../../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  createVisionProvider: vi.fn(),
  deleteVisionProvider: vi.fn(),
  getVisionBalance: vi.fn(),
  listVisionModels: vi.fn(),
  testVisionProvider: vi.fn(),
  updateVisionProvider: vi.fn(),
}))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

const saved: AiImageVisionProvider = {
  id: 'p1', name: 'DeepSeek', api_type: 'openai', base_url: 'https://api.deepseek.com', model: 'deepseek-flash',
  enabled: true, proxy_id: '', api_key_configured: true,
}
const PROXY: ProxyEntry = {
  id: 'px', name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: '', password_configured: false,
}
const BUSY = 2
let state: unknown[]
let stateIndex: number
let props: Parameters<typeof VisionProviderCard>[0]
const onProvidersChange = vi.fn()
const onDiscardNew = vi.fn()

function renderCard() {
  stateIndex = 0
  return VisionProviderCard(props)
}

function find(predicate: (item: Record<string, unknown>) => boolean) {
  return elements(renderCard()).find(predicate)
}

function button(label: string) {
  return find((item) => item.children === label)!
}

function html() {
  return renderToStaticMarkup(<MemoryRouter>{renderCard()}</MemoryRouter>)
}

function type(field: string, value: string) {
  ;(find((item) => item.id === `vision-${(state[0] as VisionProviderDraft).key}-${field}`)!.onChange as (event: unknown) => void)({ target: { value } })
}

function expand() {
  ;(find((item) => item['aria-expanded'] !== undefined)!.onClick as () => void)()
}

async function settle() {
  await vi.waitFor(() => expect(state[BUSY]).toBeNull())
}

async function submit() {
  ;(find((item) => Boolean(item.onSubmit))!.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
  await settle()
}

function result(providers: AiImageVisionProvider[], id: string | null = 'p1') {
  return { id, providers }
}

describe('vision provider card', () => {
  beforeEach(() => {
    state = []
    props = { provider: saved, index: 0, proxies: [PROXY], disabled: false, onProvidersChange, onDiscardNew }
    onProvidersChange.mockReset()
    onDiscardNew.mockReset()
    showToast.mockReset()
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(state[index]) : next
      }]
    }) as typeof useState)
    for (const mock of [createVisionProvider, deleteVisionProvider, getVisionBalance, listVisionModels, testVisionProvider, updateVisionProvider]) {
      vi.mocked(mock).mockReset()
    }
  })

  it('starts collapsed with a one-line summary and expands on demand', () => {
    const collapsed = html()
    expect(collapsed).toContain('aria-expanded="false"')
    expect(collapsed).toContain('OpenAI 兼容 · deepseek-flash · api.deepseek.com · 已配置密钥 · 直接连接')
    expect(collapsed).not.toContain('vision-p1-name')
    expand()
    const opened = html()
    expect(opened).toContain('aria-expanded="true"')
    expect(opened).toContain('id="vision-p1-name"')
    expect(opened).toContain('已配置，留空保留原密钥')
    expect(opened).not.toContain('sk-')
  })

  it('saves only this provider and collapses with the saved values', async () => {
    expand()
    type('model', 'deepseek-v4-pro')
    expect(html()).toContain('有未保存修改')
    const updated = { ...saved, model: 'deepseek-v4-pro' }
    vi.mocked(updateVisionProvider).mockResolvedValue(result([updated, { ...saved, id: 'p2', name: '其他' }]))
    await submit()
    expect(updateVisionProvider).toHaveBeenCalledWith('p1', {
      name: 'DeepSeek', api_type: 'openai', base_url: 'https://api.deepseek.com', model: 'deepseek-v4-pro', proxy_id: '',
    })
    expect(onProvidersChange).toHaveBeenCalledWith(result([updated, { ...saved, id: 'p2', name: '其他' }]))
    expect(state[1]).toBe(false)
    expect((state[0] as VisionProviderDraft).model).toBe('deepseek-v4-pro')
    expect(showToast).toHaveBeenCalledWith('success', '已保存「DeepSeek」')
  })

  it('keeps edits after a failed save and can discard them', async () => {
    expand()
    type('model', 'typo model')
    vi.mocked(updateVisionProvider).mockRejectedValue(new Error('模型不能包含空白字符'))
    await submit()
    expect(showToast).toHaveBeenCalledWith('error', '模型不能包含空白字符')
    expect(state[1]).toBe(true)
    expect((state[0] as VisionProviderDraft).model).toBe('typo model')
    ;(button('放弃修改').onClick as () => void)()
    expect((state[0] as VisionProviderDraft).model).toBe('deepseek-flash')
    expect(html()).not.toContain('有未保存修改')
  })

  it('switches enabled immediately without saving other unsaved edits', async () => {
    expand()
    type('model', 'unsaved-model')
    vi.mocked(updateVisionProvider).mockResolvedValue(result([{ ...saved, enabled: false }]))
    ;(find((item) => item.ariaLabelledBy === 'vision-p1-title')!.onChange as (checked: boolean) => void)(false)
    await settle()
    expect(updateVisionProvider).toHaveBeenCalledWith('p1', { enabled: false })
    expect(onProvidersChange).toHaveBeenCalledOnce()
    expect((state[0] as VisionProviderDraft).model).toBe('unsaved-model')
  })

  it('asks before deleting and reports the remaining list', async () => {
    expand()
    ;(button('删除').onClick as () => void)()
    const dialog = find((item) => item.title === '删除视觉模型')!
    expect(dialog.open).toBe(true)
    vi.mocked(deleteVisionProvider).mockResolvedValue(result([], null))
    ;(dialog.onConfirm as () => void)()
    await settle()
    expect(deleteVisionProvider).toHaveBeenCalledWith('p1')
    expect(onProvidersChange).toHaveBeenCalledWith(result([], null))
    expect(state[5]).toBe(false)
  })

  it('creates a new provider from an expanded draft or cancels it', async () => {
    props = { ...props, provider: undefined, initialDraft: newDraft('anthropic'), index: 1 }
    const opened = html()
    expect(opened).toContain('aria-expanded="true"')
    expect(opened).toContain('新视觉模型 2')
    expect(opened).toContain('新建，未保存')
    ;(find((item) => typeof item.ariaLabelledBy === 'string' && item.ariaLabelledBy.endsWith('-title'))!.onChange as (checked: boolean) => void)(false)
    expect(updateVisionProvider).not.toHaveBeenCalled()
    type('name', 'Claude')
    type('model', 'claude-test')
    type('api-key', 'sk-ant-test-only')
    const created = { ...saved, id: 'new-id', name: 'Claude', api_type: 'anthropic' as const, base_url: '', model: 'claude-test', enabled: false }
    vi.mocked(createVisionProvider).mockResolvedValue(result([saved, created], 'new-id'))
    await submit()
    expect(createVisionProvider).toHaveBeenCalledWith({
      name: 'Claude', api_type: 'anthropic', base_url: '', model: 'claude-test', enabled: false, proxy_id: '',
      api_key: 'sk-ant-test-only',
    })
    expect(onProvidersChange).toHaveBeenCalledWith(result([saved, created], 'new-id'))

    state = []
    ;(button('取消添加').onClick as () => void)()
    expect(onDiscardNew).toHaveBeenCalledOnce()
    expect(elements(renderCard()).some((item) => item.children === '删除')).toBe(false)
  })

  it('validates locally and asks for the key again before probing or saving a moved endpoint', async () => {
    expand()
    type('base-url', 'https://collector.test/v1')
    await submit()
    expect(updateVisionProvider).not.toHaveBeenCalled()
    expect(showToast).toHaveBeenCalledWith('error', expect.stringContaining('重新填写 API Key'))
    await (button('测试响应').onClick as () => Promise<void>)()
    expect(testVisionProvider).not.toHaveBeenCalled()
    expect(html()).toContain('请先重新填写 API Key')
  })

  it('fetches models, tests the response and reads the balance with unsaved values', async () => {
    expand()
    type('model', 'typed-model')
    ;(find((item) => item.id === 'vision-p1-proxy')!.onChange as (proxyId: string) => void)('px')
    expect((state[0] as VisionProviderDraft).proxy_id).toBe('px')
    expect(html()).toContain('有未保存修改')
    vi.mocked(listVisionModels).mockResolvedValue({
      success: true, message: '已获取 2 个模型，其中 1 个声明支持图片输入',
      models: [{ id: 'deepseek-chat', name: '', vision: false }, { id: 'deepseek-flash', name: 'Flash', vision: true }],
    })
    ;(button('获取模型列表').onClick as () => void)()
    await settle()
    expect(listVisionModels).toHaveBeenCalledWith({
      id: 'p1', api_type: 'openai', base_url: 'https://api.deepseek.com', model: 'typed-model', proxy_id: 'px',
    })
    let output = html()
    expect(output.indexOf('deepseek-flash（Flash） · 支持图片')).toBeLessThan(output.indexOf('deepseek-chat · 不支持图片'))
    ;(find((item) => item.id === 'vision-p1-model-list')!.onChange as (event: unknown) => void)({ target: { value: 'deepseek-flash' } })
    expect((state[0] as VisionProviderDraft).model).toBe('deepseek-flash')

    vi.mocked(testVisionProvider).mockResolvedValue({
      success: true, message: 'ok', latency_ms: 1640, verdict: 'ai', confidence: 70,
      reason: '', input_tokens: 812, output_tokens: 41,
    })
    ;(button('测试响应').onClick as () => void)()
    await settle()
    vi.mocked(getVisionBalance).mockRejectedValue(new Error('后端异常'))
    ;(button('查询 DeepSeek 余额').onClick as () => void)()
    await settle()
    output = html()
    expect(output).toContain('响应正常，用时 1.6 秒；测试图判断：倾向 AI 生成（置信度 70%）')
    expect(output).toContain('输入 812 tokens，输出 41 tokens')
    expect(output).toContain('后端异常')
  })
})
