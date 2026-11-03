import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettingsForm } from './SettingsContext'
import { SettingsAdvancedPage } from './SettingsAdvanced'

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
const settings = {
  link_parser_shared_media_dir: '/media',
  ai_image_openai_api_key: { configured: true, preview: null },
}
const savePartial = vi.fn()

function renderPage() { stateIndex = 0; return SettingsAdvancedPage() }

function submit() {
  const form = elements(renderPage()).find((props) => props.onSubmit)!
  ;(form.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
}

describe('AI image detection settings', () => {
  beforeEach(() => {
    state = []
    savePartial.mockReset()
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], (next: unknown) => { state[index] = next }]
    }) as typeof useState)
    vi.mocked(useSettingsForm).mockReturnValue({
      settings, savePartial, saving: false, formDisabled: false,
    } as unknown as ReturnType<typeof useSettingsForm>)
  })

  it('explains image uploads and preserves the stored key when the field is blank', () => {
    const html = renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)
    expect(html).toContain('原图还会上传 OpenAI')
    expect(html).toContain('已配置，留空保留原密钥')
    expect(html).toContain('type="password"')
    submit()
    expect(savePartial).toHaveBeenCalledWith({ link_parser_shared_media_dir: '/media' })
  })

  it('only sends a replacement key after it is entered', () => {
    const input = elements(renderPage()).find((props) => props.id === 'ai_image_openai_api_key')!
    ;(input.onChange as (event: unknown) => void)({ target: { value: '  sk-test-only  ' } })
    submit()
    expect(savePartial).toHaveBeenCalledWith({
      link_parser_shared_media_dir: '/media', ai_image_openai_api_key: 'sk-test-only',
    })
  })

  it('clears the key explicitly without changing another setting', () => {
    const button = elements(renderPage()).find((props) => props.type === 'button')!
    ;(button.onClick as () => void)()
    expect(savePartial).toHaveBeenCalledWith({ ai_image_openai_api_key: '' })
  })
})
