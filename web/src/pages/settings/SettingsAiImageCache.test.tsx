import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAiImageCache, getAiImageCache } from '../../api/client'
import type { AiImageCacheEntry, AiImageCachePage } from '../../api/types'
import { useMountAsync } from '../../hooks/useMountAsync'
import { SettingsAiImageCachePage } from './SettingsAiImageCache'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
  useCallback: (callback: unknown) => callback,
}))
vi.mock('../../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../api/client')>(),
  clearAiImageCache: vi.fn(),
  getAiImageCache: vi.fn(),
}))
vi.mock('../../hooks/useMountAsync', () => ({ useMountAsync: vi.fn() }))
vi.mock('./AiImageCacheCard', () => ({ AiImageCacheCard: () => null }))
vi.mock('./AiImageCacheSettingsCard', () => ({ AiImageCacheSettingsCard: () => null }))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

function entry(id: number): AiImageCacheEntry {
  return {
    id, sha256: String(id).repeat(64).slice(0, 64), media_type: 'image/png', size_bytes: 1024, has_preview: true,
    result: `结论：第 ${id} 张`, edited: false, stale: false, hit_count: 0,
    created_at: '2026-11-16T08:00:00Z', used_at: '2026-11-16T08:00:00Z', edited_at: null,
  }
}

function pageOf(items: AiImageCacheEntry[], total: number, page = 1): AiImageCachePage {
  return { items, total, page, page_size: 20 }
}

const PAGE = 0
const DATA = 1
const CONFIRM = 3
const CLEARING = 4
let state: unknown[]
let stateIndex: number

function renderPage() {
  stateIndex = 0
  return SettingsAiImageCachePage()
}

async function load() {
  renderPage()
  await (vi.mocked(useMountAsync).mock.calls.at(-1)![0] as () => Promise<void>)()
}

describe('AI image cache page', () => {
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

  it('lists a page of cached results and updates an edited one in place', async () => {
    vi.mocked(getAiImageCache).mockResolvedValue(pageOf([entry(1), entry(2)], 21))
    await load()
    expect(getAiImageCache).toHaveBeenCalledWith(1, 20)
    const cards = elements(renderPage()).filter((item) => item.entry) as {
      entry: AiImageCacheEntry
      onSaved: (entry: AiImageCacheEntry) => void
    }[]
    expect(cards.map((card) => card.entry.id)).toEqual([1, 2])
    cards[1]!.onSaved({ ...entry(2), result: '结论：已复核', edited: true })
    expect((state[DATA] as AiImageCachePage).items[1]!.result).toBe('结论：已复核')
    expect(renderToStaticMarkup(renderPage())).toContain('共 21 条')
  })

  it('reloads the list after the cache settings are saved', async () => {
    vi.mocked(getAiImageCache).mockResolvedValue(pageOf([entry(1)], 1))
    await load()
    const settingsCard = elements(renderPage()).find((item) => typeof item.onSaved === 'function' && !item.entry)!
    ;(settingsCard.onSaved as () => void)()
    await vi.waitFor(() => expect(getAiImageCache).toHaveBeenCalledTimes(2))
  })

  it('steps back when the current page becomes empty', async () => {
    state[PAGE] = 2
    vi.mocked(getAiImageCache).mockResolvedValue(pageOf([], 20, 2))
    await load()
    expect(state[PAGE]).toBe(1)
    expect(state[DATA]).toBeNull()
  })

  it('clears every entry only after confirmation', async () => {
    vi.mocked(getAiImageCache).mockResolvedValue(pageOf([entry(1)], 1))
    await load()
    ;(elements(renderPage()).find((item) => item.children === '清空全部缓存')!.onClick as () => void)()
    expect(state[CONFIRM]).toBe(true)
    vi.mocked(clearAiImageCache).mockResolvedValue({ deleted: 1 })
    vi.mocked(getAiImageCache).mockResolvedValue(pageOf([], 0))
    ;(elements(renderPage()).find((item) => typeof item.onConfirm === 'function')!.onConfirm as () => void)()
    await vi.waitFor(() => expect(state[CLEARING]).toBe(false))
    expect(showToast).toHaveBeenCalledWith('success', '已清空 1 条记录')
    expect(getAiImageCache).toHaveBeenCalledTimes(2)
    expect(renderToStaticMarkup(renderPage())).toContain('还没有缓存的检测结果')
  })
})
