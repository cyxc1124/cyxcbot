import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useSidebar } from '../contexts/SidebarContext'
import {
  applyTheme,
  getSavedColorTheme,
  getSavedFontFamily,
  getSavedThemeMode,
  type ColorTheme,
  type FontFamily,
  type ThemeMode,
} from '../lib/theme'

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
  { to: '/logs', label: '运行日志' },
  { to: '/about', label: '关于' },
]

const RAIL_WIDTH_CLASS = 'w-12'
const SIDEBAR_WIDTH_CLASS = 'w-64'

export function Layout() {
  const { user, logout } = useAuth()
  const { navCollapsed, setNavCollapsed } = useSidebar()
  const location = useLocation()
  const [mode, setMode] = useState<ThemeMode>(() => getSavedThemeMode())
  const [colorTheme, setColorTheme] = useState<ColorTheme>(() => getSavedColorTheme())
  const [fontFamily, setFontFamily] = useState<FontFamily>(() => getSavedFontFamily())
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [navHoverExpanded, setNavHoverExpanded] = useState(false)
  const [prevPathname, setPrevPathname] = useState(location.pathname)

  if (location.pathname !== prevPathname) {
    setPrevPathname(location.pathname)
    setNavHoverExpanded(false)
    setNavCollapsed(false)
  }

  const showFullNav = !navCollapsed || navHoverExpanded

  const toggleMode = () => {
    const next: ThemeMode = mode === 'dark' ? 'light' : 'dark'
    setMode(next)
    applyTheme(next, colorTheme, fontFamily)
  }

  const handleColorThemeChange = (next: ColorTheme) => {
    setColorTheme(next)
    applyTheme(mode, next, fontFamily)
  }

  const handleFontChange = (next: FontFamily) => {
    setFontFamily(next)
    applyTheme(mode, colorTheme, next)
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
    <div className="min-h-screen bg-background">
      {sidebarOpen && !navCollapsed && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-label="关闭侧边栏"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen flex-col overflow-hidden border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width,transform,box-shadow] duration-200 ${asideWidthClass} ${asideTranslateClass} ${
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
          className={`flex h-16 shrink-0 items-center border-b border-sidebar-border ${
            showFullNav ? 'gap-3 px-6' : 'justify-center px-0'
          }`}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            C
          </span>
          {showFullNav && (
            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold text-sidebar-foreground">机器草</h1>
              <p className="truncate text-xs text-muted-foreground">Web 管理面板</p>
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
                    isActive ? 'nav-link nav-link-active' : 'nav-link'
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <div className="shrink-0 border-t border-sidebar-border p-4">
              <div className="mb-3 text-sm">
                <p className="font-medium text-sidebar-foreground">{user?.username}</p>
                <p className="text-xs text-muted-foreground">{user?.is_admin ? '管理员' : '用户'}</p>
              </div>
              <button type="button" onClick={logout} className="btn-secondary w-full text-sm">
                退出登录
              </button>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <span
              className="select-none text-[10px] tracking-widest text-muted-foreground [writing-mode:vertical-rl]"
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
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-border bg-background/80 px-4 backdrop-blur lg:px-8">
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
          <div className="ml-auto flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="hidden sm:inline">字体</span>
              <select
                className="input w-auto min-w-[7rem] py-1.5 text-sm"
                value={fontFamily}
                onChange={(e) => handleFontChange(e.target.value as FontFamily)}
                aria-label="字体"
              >
                <option value="maple">Maple Mono</option>
                <option value="system">系统字体</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="hidden sm:inline">配色</span>
              <select
                className="input w-auto min-w-[7rem] py-1.5 text-sm"
                value={colorTheme}
                onChange={(e) => handleColorThemeChange(e.target.value as ColorTheme)}
                aria-label="配色方案"
              >
                <option value="default">默认</option>
                <option value="claude">Claude</option>
              </select>
            </label>
            <button
              type="button"
              onClick={toggleMode}
              className="btn-ghost text-sm"
              title="切换浅色/深色"
            >
              {mode === 'dark' ? '浅色' : '深色'}
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
