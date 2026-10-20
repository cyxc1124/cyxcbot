import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SidebarProvider } from '../contexts/SidebarContext'
import { Layout } from './Layout'

vi.mock('../contexts/ToastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'test-admin', is_admin: true }, logout: vi.fn() }),
}))

describe('account navigation', () => {
  it('places user information and account actions in the header', () => {
    const html = renderToStaticMarkup(<MemoryRouter><SidebarProvider><Layout /></SidebarProvider></MemoryRouter>)
    const header = html.match(/<header\b[\s\S]*?<\/header>/)?.[0]
    const sidebar = html.match(/<aside\b[\s\S]*?<\/aside>/)?.[0]
    for (const label of ['test-admin', '管理员', '修改密码', '退出登录']) {
      expect(header).toContain(label)
      expect(sidebar).not.toContain(label)
    }
    expect(header).toContain('aria-label="账户：test-admin"')
  })
})
