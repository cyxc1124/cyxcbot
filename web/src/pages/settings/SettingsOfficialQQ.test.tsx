import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { patchSettings } from '../../api/client'
import type { Settings } from '../../api/types'
import { useSettingsForm } from './SettingsContext'
import { SettingsOfficialQQPage } from './SettingsOfficialQQ'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
}))
vi.mock('../../api/client', () => ({ patchSettings: vi.fn() }))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)]
    : [])
}

let state: unknown[]
let stateIndex: number
const settings = {
  official_qq: {
    app_id: 'test-app',
    secret: { configured: true, preview: null },
    is_sandbox: true,
    use_websocket: false,
  },
} as Settings
let context: ReturnType<typeof useSettingsForm>

function renderPage() {
  stateIndex = 0
  return SettingsOfficialQQPage()
}

async function save() {
  const button = elements(renderPage()).find((props) => props.className === 'btn-primary')!
  ;(button.onClick as () => void)()
  await vi.waitFor(() => expect(context.load).toHaveBeenCalledOnce())
}

describe('official QQ 1.7.3 settings', () => {
  beforeEach(() => {
    state = []
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], (next: unknown) => { state[index] = next }]
    }) as typeof useState)
    context = {
      settings,
      setSettings: vi.fn(),
      load: vi.fn(),
      formDisabled: false,
    } as unknown as ReturnType<typeof useSettingsForm>
    vi.mocked(useSettingsForm).mockReturnValue(context)
    vi.mocked(patchSettings).mockReset().mockResolvedValue({
      ...settings,
      official_qq: { ...settings.official_qq, is_sandbox: false },
    })
  })

  it('removes the sandbox control and saves legacy settings without overwriting the secret', async () => {
    const html = renderToStaticMarkup(renderPage())
    expect(html).not.toContain('official-qq-sandbox-label')
    expect(html).toContain('官方 QQ 已统一 API')
    expect(html).toContain('official-qq-websocket-label')

    await save()
    expect(patchSettings).toHaveBeenCalledWith({
      official_qq_app_id: 'test-app',
      official_qq_is_sandbox: false,
      official_qq_use_websocket: false,
    })
    expect(context.setSettings).toHaveBeenCalledOnce()
  })

  it('continues to save WebSocket changes', async () => {
    const toggle = elements(renderPage()).find((props) => props.ariaLabelledBy === 'official-qq-websocket-label')!
    ;(toggle.onChange as (checked: boolean) => void)(true)

    await save()
    expect(patchSettings).toHaveBeenCalledWith({
      official_qq_app_id: 'test-app',
      official_qq_is_sandbox: false,
      official_qq_use_websocket: true,
    })
  })

  it('continues to clear credentials with legacy sandbox data', async () => {
    const dialog = elements(renderPage()).find((props) => props.title === '清除官方 Bot 凭证')!
    ;(dialog.onConfirm as () => void)()
    await vi.waitFor(() => expect(context.load).toHaveBeenCalledOnce())
    expect(patchSettings).toHaveBeenCalledWith({
      official_qq_app_id: '',
      official_qq_app_secret: '',
    })
  })
})
