import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettingsForm } from './SettingsContext'
import { SettingsAiImageSourcesPage } from './SettingsAiImageSources'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

let state: unknown[]
let stateIndex: number
let settings: Record<string, unknown>
const savePartial = vi.fn()

function renderPage() { stateIndex = 0; return SettingsAiImageSourcesPage() }

function submit() {
  const form = elements(renderPage()).find((props) => props.onSubmit)!
  ;(form.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
}

function toggle(label: string, checked: boolean) {
  const row = elements(renderPage()).find((props) => props.label === label)!
  ;(row.onChange as (checked: boolean) => void)(checked)
}

describe('AI image detection sources', () => {
  beforeEach(() => {
    state = []
    savePartial.mockReset()
    settings = {
      ai_image_openai_api_key: { configured: true, preview: null },
      ai_image_local_c2pa_enabled: true,
      ai_image_openai_c2pa_enabled: true,
      ai_image_openai_synthid_enabled: true,
    }
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => { state[index] = next }]
    }) as typeof useState)
    vi.mocked(useSettingsForm).mockImplementation(() => ({
      settings, savePartial, saving: false, formDisabled: false,
    }) as unknown as ReturnType<typeof useSettingsForm>)
  })

  it('explains that both OpenAI signals share one upload and keeps the stored key', () => {
    const html = renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)
    expect(html).toContain('任一开启就会上传原图')
    expect(html).toContain('已配置，留空保留原密钥')
    expect(html).toContain('type="password"')
    expect(html.match(/role="switch"/g)).toHaveLength(3)
    submit()
    expect(savePartial).toHaveBeenCalledWith({
      ai_image_local_c2pa_enabled: true,
      ai_image_openai_c2pa_enabled: true,
      ai_image_openai_synthid_enabled: true,
      ai_image_openai_proxy_id: '',
    })
  })

  it('saves each switch independently together with a replacement key', () => {
    toggle('本地 C2PA', false)
    toggle('SynthID（OpenAI）', false)
    const input = elements(renderPage()).find((props) => props.id === 'ai_image_openai_api_key')!
    ;(input.onChange as (event: unknown) => void)({ target: { value: '  sk-test-only  ' } })
    submit()
    expect(savePartial).toHaveBeenCalledWith({
      ai_image_local_c2pa_enabled: false,
      ai_image_openai_c2pa_enabled: true,
      ai_image_openai_synthid_enabled: false,
      ai_image_openai_proxy_id: '',
      ai_image_openai_api_key: 'sk-test-only',
    })
  })

  it('warns when OpenAI checks are on without a key and clears the key explicitly', () => {
    settings = { ...settings, ai_image_openai_api_key: { configured: false, preview: null } }
    expect(renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)).toContain('尚未配置 OpenAI API Key')
    toggle('OpenAI C2PA', false)
    toggle('SynthID（OpenAI）', false)
    expect(renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)).not.toContain('尚未配置 OpenAI API Key')

    settings = { ...settings, ai_image_openai_api_key: { configured: true, preview: null } }
    state = []
    const button = elements(renderPage()).find((props) => props.type === 'button' && props.className === 'btn-secondary')!
    ;(button.onClick as () => void)()
    expect(savePartial).toHaveBeenCalledWith({ ai_image_openai_api_key: '' })
  })

  it('saves the OpenAI proxy choice together with the form', () => {
    const card = elements(renderPage()).find((props) => props.field === 'ai_image_openai_proxy_id')!
    expect(card.value).toBe('')
    ;(card.onChange as (proxyId: string) => void)('px')
    expect(savePartial).not.toHaveBeenCalled()
    submit()
    expect(savePartial).toHaveBeenCalledWith(expect.objectContaining({ ai_image_openai_proxy_id: 'px' }))
  })
})
