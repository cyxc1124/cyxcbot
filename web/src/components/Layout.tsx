import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useSidebar } from '../contexts/SidebarContext'

const navItems = [
  { to: '/', label: '仪表盘' },
  { to: '/dynamic', label: '动态订阅' },
  { to: '/live', label: '直播订阅' },
  { to: '/templates', label: '消息模板' },
  { to: '/groups', label: '群组' },
  { to: '/private', label: '好友' },
  { to: '/settings', label: '系统设置' },
  { to: '/audit', label: '审计日志' },
  { to: '/events', label: '系统事件' },
  { to: '/about', label: '关于' },
]

const RAIL_WIDTH_CLASS = 'w-12'
const SIDEBAR_WIDTH_CLASS = 'w-64'

export function Layout() {
  const { user, logout } = useAuth()
  const { navCollapsed, setNavCollapsed } = useSidebar()
  const location = useLocation()
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains('dark'),
  )
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [navHoverExpanded, setNavHoverExpanded] = useState(false)

  useEffect(() => {
    setNavCollapsed(false)
    setNavHoverExpanded(false)
  }, [location.pathname, setNavCollapsed])

  useEffect(() => {
    if (!navCollapsed) setNavHoverExpanded(false)
  }, [navCollapsed])

  const showFullNav = !navCollapsed || navHoverExpanded

  const toggleDark = () => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('cyxcbot_theme', next ? 'dark' : 'light')
  }

  const toggleNavCollapsed = () => {
    if (navCollapsed) {
      setNavCollapsed(false)
    } else {
      setNavHoverExpanded(false)
      setNavCollapsed(true)
    }
  }

  const asideWidthClass = navCollapsed
    ? navHoverExpanded
      ? SIDEBAR_WIDTH_CLASS
      : RAIL_WIDTH_CLASS
    : SIDEBAR_WIDTH_CLASS

  const asideTranslateClass = navCollapsed
    ? '-translate-x-full lg:translate-x-0'
    : sidebarOpen
      ? 'translate-x-0'
      : '-translate-x-full lg:translate-x-0'

  return (
    <div className="min-h-screen">
      {sidebarOpen && !navCollapsed && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭侧边栏"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen flex-col overflow-hidden border-r border-slate-200 bg-white transition-[width,transform,box-shadow] duration-200 dark:border-slate-700 dark:bg-slate-900 ${asideWidthClass} ${asideTranslateClass} ${
          navCollapsed && navHoverExpanded ? 'shadow-xl' : ''
        }`}
        onMouseEnter={() => {
          if (navCollapsed) setNavHoverExpanded(true)
        }}
        onMouseLeave={() => {
          if (navCollapsed) setNavHoverExpanded(false)
        }}
      >
        <div
          className={`flex h-16 shrink-0 items-center border-b border-slate-200 dark:border-slate-700 ${
            showFullNav ? 'gap-3 px-6' : 'justify-center px-0'
          }`}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            C
          </span>
          {showFullNav && (
            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold text-slate-900 dark:text-white">机器草</h1>
              <p className="truncate text-xs text-slate-500">Web 管理面板</p>
            </div>
          )}
        </div>

        {showFullNav ? (
          <>
            <nav className="flex-1 space-y-1 overflow-y-auto p-4">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={() => {
                    setSidebarOpen(false)
                    setNavHoverExpanded(false)
                  }}
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

            <div className="shrink-0 border-t border-slate-200 p-4 dark:border-slate-700">
              <div className="mb-3 text-sm">
                <p className="font-medium text-slate-900 dark:text-white">{user?.username}</p>
                <p className="text-xs text-slate-500">{user?.is_admin ? '管理员' : '用户'}</p>
              </div>
              <button type="button" onClick={logout} className="btn-secondary w-full text-sm">
                退出登录
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <span
              className="select-none text-[10px] tracking-widest text-slate-400 [writing-mode:vertical-rl]"
              aria-hidden
            >
              导航
            </span>
          </div>
        )}
      </aside>

      <div
        className={`flex min-h-screen flex-col transition-[padding] duration-200 ${
          navCollapsed ? 'lg:pl-12' : 'lg:pl-64'
        }`}
      >
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-700 dark:bg-slate-900/80 lg:px-8">
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost text-sm"
              onClick={toggleNavCollapsed}
            >
              {navCollapsed ? '展开导航' : '收起导航'}
            </button>
            <button
              type="button"
              className="btn-ghost text-sm lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              菜单
            </button>
          </div>
          <button
            type="button"
            onClick={toggleDark}
            className="btn-ghost ml-auto text-sm"
            title="切换主题"
          >
            {dark ? '浅色' : '深色'}
          </button>
        </header>

        <main className="flex-1 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
