import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SettingsLayout } from './SettingsLayout'

vi.mock('./SettingsContext', () => ({
  SettingsProvider: ({ children }: { children: ReactNode }) => children,
  useSettingsForm: () => ({ settings: {}, saving: false, loading: false, showLogoutConfirm: false }),
}))

describe('monitor settings navigation', () => {
  it.each([
    '/settings/bilibili-monitor', '/settings/bilibili-monitor/',
    '/settings/x-monitor', '/settings/x-monitor/',
  ])('keeps a desktop submit button at %s', (path) => {
    const html = renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><SettingsLayout /></MemoryRouter>)
    expect(html).toContain('type="submit" form="monitor-settings"')
  })

  it('leaves account-specific save actions to the account page', () => {
    const html = renderToStaticMarkup(<MemoryRouter initialEntries={['/settings/account/']}><SettingsLayout /></MemoryRouter>)
    expect(html).not.toContain('form="monitor-settings"')
  })
})
