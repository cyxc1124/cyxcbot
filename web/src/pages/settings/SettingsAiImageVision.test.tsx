import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AiImageVisionProvider, Settings, VisionProvidersResult } from '../../api/types'
import type { VisionProviderDraft } from './aiImageVisionForm'
import { useSettingsForm } from './SettingsContext'
import { SettingsAiImageVisionPage } from './SettingsAiImageVision'

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
  provider?: AiImageVisionProvider
  initialDraft?: VisionProviderDraft
  index: number
  onProvidersChange: (result: VisionProvidersResult) => void
  onDiscardNew?: () => void
}

const providers: AiImageVisionProvider[] = [
  { id: 'p1', name: 'GPT', api_type: 'openai', base_url: '', model: 'gpt-4o', enabled: true, proxy_id: '', api_key_configured: true },
  { id: 'p2', name: 'Claude', api_type: 'anthropic', base_url: '', model: 'claude', enabled: false, proxy_id: '', api_key_configured: true },
]
let state: unknown[]
let stateIndex: number
let settings: Settings
const setSettings = vi.fn((next: unknown) => {
  settings = typeof next === 'function' ? (next as (value: Settings) => Settings)(settings) : next as Settings
})

function renderPage() { stateIndex = 0; return SettingsAiImageVisionPage() }

function cards() {
  return elements(renderPage()).filter((item) => typeof item.onProvidersChange === 'function') as CardProps[]
}

function addProvider() {
  ;(elements(renderPage()).find((item) => item.children === '添加视觉模型')!.onClick as () => void)()
}

describe('AI image vision providers page', () => {
  beforeEach(() => {
    state = []
    settings = { ai_image_vision_providers: providers } as Settings
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

  it('lists every saved provider as its own collapsible card and explains costs', () => {
    const html = renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)
    expect(html).toContain('数量不设上限')
    expect(html).toContain('每个模型单独保存')
    expect(html).toContain('已保存 2 个，启用 1 个')
    expect(html.match(/aria-expanded="false"/g)).toHaveLength(2)
    expect(cards().map((card) => card.provider?.id)).toEqual(['p1', 'p2'])
  })

  it('adds unsaved cards without a cap and swaps them for the saved provider', () => {
    for (let index = 0; index < 10; index += 1) addProvider()
    const added = cards().filter((card) => card.initialDraft)
    expect(added).toHaveLength(10)
    expect(added[0].index).toBe(2)

    const created = { ...providers[0], id: 'p3', name: 'New' }
    added[0].onProvidersChange({ id: 'p3', providers: [...providers, created] })
    expect(settings.ai_image_vision_providers?.map((provider) => provider.id)).toEqual(['p1', 'p2', 'p3'])
    expect(cards().filter((card) => card.initialDraft)).toHaveLength(9)

    cards().find((card) => card.initialDraft)!.onDiscardNew!()
    expect(cards().filter((card) => card.initialDraft)).toHaveLength(8)
  })

  it('applies one provider\'s change without resetting other unsaved cards', () => {
    addProvider()
    cards()[0].onProvidersChange({ id: 'p1', providers: [{ ...providers[0], enabled: false }, providers[1]] })
    expect(settings.ai_image_vision_providers?.[0].enabled).toBe(false)
    expect(cards().filter((card) => card.initialDraft)).toHaveLength(1)
    expect(renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)).toContain('已保存 2 个，启用 0 个')
  })

  it('shows an empty state before anything is added', () => {
    settings = { ai_image_vision_providers: [] as AiImageVisionProvider[] } as Settings
    expect(renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)).toContain('尚未添加视觉模型')
  })
})
