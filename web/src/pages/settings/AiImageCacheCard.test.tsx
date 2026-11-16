import { Children, isValidElement, useEffect, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { deleteAiImageCacheEntry, getAiImageCachePreview, updateAiImageCacheEntry } from '../../api/client'
import type { AiImageCacheEntry } from '../../api/types'
import { AiImageCacheCard } from './AiImageCacheCard'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(), useEffect: vi.fn(),
}))
vi.mock('../../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  deleteAiImageCacheEntry: vi.fn(),
  getAiImageCachePreview: vi.fn(),
  updateAiImageCacheEntry: vi.fn(),
}))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

const entry: AiImageCacheEntry = {
  id: 7,
  sha256: 'ab'.repeat(32),
  media_type: 'image/png',
  size_bytes: 2_500_000,
  has_preview: true,
  result: '图片 AI 检测\n本地 C2PA：未检出嵌入式凭证。\n结论：无法判断是否为 AI 图片。\n未检出不代表非 AI。',
  edited: false,
  stale: true,
  hit_count: 3,
  created_at: '2026-11-16T08:00:00Z',
  used_at: '2026-11-16T09:00:00Z',
  edited_at: null,
}
const DRAFT = 1
const BUSY = 2
const CONFIRM = 3
const PREVIEW = 4
let state: unknown[]
let stateIndex: number
const onSaved = vi.fn()
const onDeleted = vi.fn()

function renderCard() {
  stateIndex = 0
  return AiImageCacheCard({ entry, onSaved, onDeleted })
}

function find(predicate: (item: Record<string, unknown>) => boolean) {
  return elements(renderCard()).find(predicate)!
}

function expandAndType(value: string) {
  ;(find((item) => item['aria-expanded'] !== undefined).onClick as () => void)()
  ;(find((item) => item.id === 'ai-cache-7-result').onChange as (event: unknown) => void)({ target: { value } })
}

function submit() {
  ;(find((item) => Boolean(item.onSubmit)).onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
}

describe('AI image cache card', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    state = []
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(state[index]) : next
      }]
    }) as typeof useState)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('summarizes the conclusion and loads the preview through the API session', async () => {
    const collapsed = renderToStaticMarkup(renderCard())
    expect(collapsed).toContain('结论：无法判断是否为 AI 图片。')
    expect(collapsed).toContain('配置已变更')
    expect(collapsed).toContain(`${'ab'.repeat(6)} · `)
    expect(collapsed).toContain('复用 3 次')
    expect(collapsed).not.toContain('ai-cache-7-result')

    vi.mocked(getAiImageCachePreview).mockResolvedValue(new Blob(['jpeg']))
    const created = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview')
    const revoked = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    // 直接调用组件取卡片自己的 effect；静态渲染时最后注册的是 ConfirmDialog 的。
    renderCard()
    const cleanup = (vi.mocked(useEffect).mock.calls.at(-1)![0] as () => () => void)()
    await vi.waitFor(() => expect(state[PREVIEW]).toBe('blob:preview'))
    expect(getAiImageCachePreview).toHaveBeenCalledWith(7, expect.any(AbortSignal))
    expect(created).toHaveBeenCalledOnce()
    expect(renderToStaticMarkup(renderCard())).toContain('src="blob:preview"')
    cleanup()
    expect(revoked).toHaveBeenCalledWith('blob:preview')
  })

  it('saves an edited reply and hands the saved entry back', async () => {
    expandAndType('  结论：管理员复核为 AI 生成。 ')
    const opened = renderToStaticMarkup(renderCard())
    expect(opened).toContain('ab'.repeat(32))
    expect(opened).toContain('有未保存修改')
    const saved = { ...entry, result: '结论：管理员复核为 AI 生成。', edited: true, stale: false, edited_at: '2026-11-16T10:00:00Z' }
    vi.mocked(updateAiImageCacheEntry).mockResolvedValue(saved)
    submit()
    await vi.waitFor(() => expect(state[BUSY]).toBeNull())
    expect(updateAiImageCacheEntry).toHaveBeenCalledWith(7, '结论：管理员复核为 AI 生成。')
    expect(onSaved).toHaveBeenCalledWith(saved)
    expect(state[DRAFT]).toBe(saved.result)
  })

  it('refuses an empty reply and deletes only after confirmation', async () => {
    expandAndType('   ')
    submit()
    expect(showToast).toHaveBeenCalledWith('error', '回复内容不能为空')
    expect(updateAiImageCacheEntry).not.toHaveBeenCalled()

    ;(find((item) => item.children === '删除').onClick as () => void)()
    expect(state[CONFIRM]).toBe(true)
    vi.mocked(deleteAiImageCacheEntry).mockResolvedValue(undefined)
    ;(find((item) => typeof item.onConfirm === 'function').onConfirm as () => void)()
    await vi.waitFor(() => expect(onDeleted).toHaveBeenCalledOnce())
    expect(deleteAiImageCacheEntry).toHaveBeenCalledWith(7)
    expect(state[CONFIRM]).toBe(false)
  })
})
