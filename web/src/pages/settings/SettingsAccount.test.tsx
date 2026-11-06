import { useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { SettingsAccountPage } from './SettingsAccount'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
}))
vi.mock('./SettingsContext', () => ({
  useSettingsForm: () => ({
    settings: { bilibili_cookie: { configured: true } },
    bilibili: { logged_in: true },
    formDisabled: false,
    loggingOut: false,
  }),
}))
vi.mock('../../contexts/ToastContext', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))
vi.mock('../../components/BilibiliQrLogin', () => ({
  BilibiliQrLogin: () => <button>获取二维码</button>,
}))

describe('Bilibili account management', () => {
  it('keeps QR login available with existing accounts and targets each row by UID', () => {
    vi.mocked(useState).mockImplementation(((initial?: unknown) => [initial, vi.fn()]) as typeof useState)
    vi.mocked(useState).mockImplementationOnce(() => [[
      { uid: '100', username: '账号一' },
      { uid: '200', username: '账号二' },
    ], vi.fn()])
    const html = renderToStaticMarkup(<SettingsAccountPage />)
    expect(html).toContain('已保存 2 个账号')
    expect(html).toContain('获取二维码')
    for (const uid of ['100', '200']) {
      expect(html).toContain(`aria-label="验证账号 ${uid}"`)
      expect(html).toContain(`aria-label="移除账号 ${uid}"`)
    }
    expect(html).toContain('移除全部账号')
    expect(html.match(/截图 \/ 弹幕账号/g)).toHaveLength(1)
  })
})
