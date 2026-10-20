import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SettingsLayout } from './SettingsLayout'

vi.mock('./SettingsContext', () => ({
  SettingsProvider: ({ children }: { children: ReactNode }) => children,
  useSettingsForm: () => ({ settings: {}, saving: false, loading: false, showLogoutConfirm: false }),
}))

describe('settings follow their sidebar destination', () => {
  it.each([
    ['/bilibili/settings', 'B 站订阅参数'], ['/bilibili/settings/', 'B 站订阅参数'],
    ['/x/settings', 'X订阅参数'], ['/bilibili/account', 'B 站账号'],
    ['/system/permissions', '权限'], ['/system/advanced', '高级配置'],
  ])('labels %s without a duplicate settings sidebar', (path, title) => {
    const html = renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><SettingsLayout /></MemoryRouter>)
    expect(html).toContain(`>${title}</h2>`)
    expect(html).not.toContain('设置分类')
    expect(html).not.toContain('/settings/')
  })

  it('leaves account-specific save actions to the account page', () => {
    const html = renderToStaticMarkup(<MemoryRouter initialEntries={['/bilibili/account/']}><SettingsLayout /></MemoryRouter>)
    expect(html).not.toContain('form="monitor-settings"')
  })
})
