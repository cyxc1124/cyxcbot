import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Settings } from '../../api/types'
import { AiImageCacheSettingsCard } from './AiImageCacheSettingsCard'
import { useSettingsForm } from './SettingsContext'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

let state: unknown[]
let stateIndex: number
let settings: Partial<Settings>
const savePartial = vi.fn()
const onSaved = vi.fn()

function renderCard() {
  stateIndex = 0
  return AiImageCacheSettingsCard({ onSaved })
}

function find(predicate: (item: Record<string, unknown>) => boolean) {
  return elements(renderCard()).find(predicate)!
}

function setLimit(value: string) {
  ;(find((item) => item.id === 'ai-image-cache-max-entries').onChange as (event: unknown) => void)({ target: { value } })
}

function submit() {
  ;(find((item) => Boolean(item.onSubmit)).onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
}

describe('AI image cache settings', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    state = []
    settings = { ai_image_cache_enabled: true, ai_image_cache_max_entries: 500 }
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(state[index]) : next
      }]
    }) as typeof useState)
    vi.mocked(useSettingsForm).mockImplementation(() => ({
      settings, savePartial, saving: false, formDisabled: false,
    }) as unknown as ReturnType<typeof useSettingsForm>)
    savePartial.mockResolvedValue(undefined)
  })

  it('shows the saved switch and limit', () => {
    const html = renderToStaticMarkup(renderCard())
    expect(html).toContain('启用检测缓存')
    expect(html).toContain('aria-checked="true"')
    expect(html).toContain('value="500"')
  })

  it('saves the switch and limit together, then refreshes the list', async () => {
    ;(find((item) => item.ariaLabelledBy === 'ai-image-cache-enabled').onChange as (checked: boolean) => void)(false)
    setLimit('120')
    submit()
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalledOnce())
    expect(savePartial).toHaveBeenCalledWith({ ai_image_cache_enabled: false, ai_image_cache_max_entries: 120 })
  })

  it.each(['0', '10001', '1.5', ''])('rejects %j as the limit', (value) => {
    setLimit(value)
    submit()
    expect(showToast).toHaveBeenCalledWith('error', '最多保留条数须为 1–10000 的整数')
    expect(savePartial).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
  })
})
