import { useState, type FormEvent, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Settings } from '../../api/types'
import { patchSettings } from '../../api/client'
import { SettingsBotPage } from './SettingsBot'
import { SettingsAdvancedPage } from './SettingsAdvanced'
import { useSettingsForm } from './SettingsContext'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
}))
vi.mock('../../api/client', () => ({ patchSettings: vi.fn() }))
vi.mock('react-router-dom', () => ({
  Link: ({ to, children }: { to: string; children: ReactNode }) => <a href={to}>{children}</a>,
}))

vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))
vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

const savedSettings = {
  nonebot_superusers: ['12345678', 'official_user_id'],
  status_check_allowed_qq: ['87654321'],
  link_parser_shared_media_dir: '/root/.config/QQ/tmp',
} as Settings

function formContext(settings: Settings | null): ReturnType<typeof useSettingsForm> {
  return {
    settings,
    setSettings: vi.fn(),
    bilibili: null,
    loading: !settings,
    error: '',
    load: vi.fn(),
    retryLoad: vi.fn(),
    saving: false,
    formDisabled: !settings,
    savePartial: vi.fn(),
    testing: false,
    handleTestLogin: vi.fn(),
    loggingOut: false,
    showLogoutConfirm: false,
    setShowLogoutConfirm: vi.fn(),
    handleLogout: vi.fn(),
  }
}

function expectSavedFields(html: string, settings: Settings) {
  expect(html).toContain(`>${settings.nonebot_superusers.join('\n')}</textarea>`)
  expect(html).toContain(`>${settings.status_check_allowed_qq.join('\n')}</textarea>`)
  expect(html).not.toContain('id="link_parser_shared_media_dir"')
}

let state: unknown[]
let stateIndex: number
let pendingRender: boolean

function renderPage(settings: Settings | null, component = SettingsBotPage) {
  vi.mocked(useSettingsForm).mockReturnValue(formContext(settings))
  let page: ReturnType<typeof SettingsBotPage>
  do {
    stateIndex = 0
    pendingRender = false
    page = component()
  } while (pendingRender)
  return page
}

describe('SettingsBotPage drafts', () => {
  beforeEach(() => {
    state = []
    vi.mocked(patchSettings).mockReset()
    // Keep hook state across renders without requiring a browser test dependency.
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) {
        state[index] = typeof initial === 'function' ? initial() : initial
      }
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? next(state[index]) : next
        pendingRender = true
      }]
    }) as typeof useState)
  })

  it('shows and saves existing permissions without writing the media directory', async () => {
    vi.mocked(patchSettings).mockResolvedValue(savedSettings)
    const page = renderPage(savedSettings)

    expectSavedFields(renderToStaticMarkup(page), savedSettings)
    await page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)

    expect(patchSettings).toHaveBeenCalledWith({
      nonebot_superusers: savedSettings.nonebot_superusers,
      status_check_allowed_qq: savedSettings.status_check_allowed_qq,
    })
  })

  it.each([null, savedSettings])('synchronizes drafts when settings refresh from %s', (initial) => {
    const updated = {
      ...savedSettings,
      nonebot_superusers: ['22334455'],
      status_check_allowed_qq: ['55667788'],
      link_parser_shared_media_dir: '/srv/qq/tmp',
    }
    renderPage(initial)

    expectSavedFields(renderToStaticMarkup(renderPage(updated)), updated)
  })

  it('saves only the media directory from advanced settings', () => {
    const page = renderPage({ ...savedSettings, link_parser_shared_media_dir: '  /srv/qq/tmp  ' }, SettingsAdvancedPage)
    const html = renderToStaticMarkup(page)
    expect(html).toContain('id="link_parser_shared_media_dir"')
    expect(html).not.toContain('id="nonebot_superusers"')
    page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(vi.mocked(useSettingsForm).mock.results.at(-1)?.value.savePartial).toHaveBeenCalledWith({ link_parser_shared_media_dir: '/srv/qq/tmp' })
    expect(patchSettings).not.toHaveBeenCalled()
  })

  it('refreshes the media draft and allows clearing it to restore the default', () => {
    renderPage(savedSettings, SettingsAdvancedPage)
    const page = renderPage({ ...savedSettings, link_parser_shared_media_dir: '' }, SettingsAdvancedPage)
    expect(renderToStaticMarkup(page)).toContain('value=""')
    page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(vi.mocked(useSettingsForm).mock.results.at(-1)?.value.savePartial).toHaveBeenCalledWith({ link_parser_shared_media_dir: '' })
  })
})
