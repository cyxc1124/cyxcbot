import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LoginPage } from '../pages/Login'
import { SetupPage } from '../pages/Setup'

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ login: vi.fn(), setup: vi.fn(), initialized: true }),
}))

function render(page: 'login' | 'setup') {
  return renderToStaticMarkup(<MemoryRouter>{page === 'login' ? <LoginPage /> : <SetupPage />}</MemoryRouter>)
}

describe.each(['login', 'setup'] as const)('%s appearance', (page) => {
  it('shares the original avatar, build version, copyright and accessible theme controls', () => {
    const html = render(page)
    expect(html).toContain('src="/brand-avatar.png"')
    expect(html).toContain(import.meta.env.VITE_BUILD_VERSION)
    expect(html).toContain('© 2026 cyxcbot. All rights reserved.')
    for (const label of ['白色', '黑色', '跟随系统']) expect(html).toContain(`aria-label="${label}"`)
    expect(html).not.toContain('bg-linear')
  })

  it('retains username validation and the correct password-manager semantics', () => {
    const html = render(page)
    const username = html.match(/<input\b[^>]*id="username"[^>]*>/)?.[0]
    for (const attribute of ['name="username"', 'minLength="3"', 'maxLength="64"', 'autoComplete="username"']) {
      expect(username).toContain(attribute)
    }
    expect(html.match(/type="password"/g)).toHaveLength(page === 'login' ? 1 : 2)
    expect(html).toContain(`autoComplete="${page === 'login' ? 'current-password' : 'new-password'}"`)
    expect(html.match(/aria-label="显示密码"/g)).toHaveLength(page === 'login' ? 1 : 2)
    expect(html).toContain('aria-controls="password"')
    if (page === 'setup') expect(html).toContain('aria-controls="confirm"')
  })
})
