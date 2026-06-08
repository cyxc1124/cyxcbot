import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { to: '/', label: '仪表盘' },
  { to: '/dynamic', label: '动态监控' },
  { to: '/live', label: '直播监控' },
  { to: '/groups', label: '群组管理' },
  { to: '/settings', label: '系统设置' },
  { to: '/audit', label: '审计日志' },
  { to: '/events', label: '系统事件' },
]

export function Layout() {
  const { user, logout } = useAuth()
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains('dark'),
  )
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const toggleDark = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('cyxcbot_theme', next ? 'dark' : 'light')
  }

  return (
    <div className="min-h-screen">
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭侧边栏"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 flex-col border-r border-slate-200 bg-white transition-transform dark:border-slate-700 dark:bg-slate-900 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-6 dark:border-slate-700">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            C
          </span>
          <div>
            <h1 className="text-sm font-bold text-slate-900 dark:text-white">cyxcbot</h1>
            <p className="text-xs text-slate-500">Web 管理面板</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `block rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4 dark:border-slate-700">
          <div className="mb-3 text-sm">
            <p className="font-medium text-slate-900 dark:text-white">{user?.username}</p>
            <p className="text-xs text-slate-500">{user?.is_admin ? '管理员' : '用户'}</p>
          </div>
          <button type="button" onClick={logout} className="btn-secondary w-full text-sm">
            退出登录
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80 lg:px-8">
          <button
            type="button"
            className="btn-ghost text-sm lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            菜单
          </button>
          <div className="flex-1 lg:hidden" />
          <div className="flex items-center gap-2">
            <button type="button" onClick={toggleDark} className="btn-ghost text-sm" title="切换主题">
              {dark ? '浅色' : '深色'}
            </button>
            <Link to="/" className="hidden text-sm text-slate-500 hover:text-brand-600 lg:block">
              返回首页
            </Link>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
