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

describe('advanced settings', () => {
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

  it('only saves the shared media directory and points AI detection to its own section', () => {
    const html = renderToStaticMarkup(<MemoryRouter>{renderPage()}</MemoryRouter>)
    expect(html).toContain('href="/ai-image/sources"')
    expect(html).not.toContain('type="password"')
    const form = elements(renderPage()).find((props) => props.onSubmit)!
    ;(form.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
    expect(savePartial).toHaveBeenCalledWith({ link_parser_shared_media_dir: '/media' })
  })
})
