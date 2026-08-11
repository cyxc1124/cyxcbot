import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useSidebar } from '../contexts/SidebarContext'
import { getAbout } from '../api/client'
import type { AboutInfo } from '../api/types'
import {
  applyTheme,
  getSavedColorTheme,
  getSavedFontFamily,
  getSavedThemeMode,
  type ColorTheme,
  type FontFamily,
  type ThemeMode,
} from '../lib/theme'

type NavItem = { to: string; label: string }
type NavSection = { section: string; items: NavItem[] }

const navSections: NavSection[] = [
  { section: '概览', items: [{ to: '/', label: '仪表盘' }] },
  {
    section: 'B 站',
    items: [
      { to: '/dynamic', label: '动态订阅' },
      { to: '/live', label: '直播订阅' },
      { to: '/templates/bilibili', label: '消息模板' },
    ],
  },
  {
    section: 'X',
    items: [
      { to: '/x', label: '推文订阅' },
      { to: '/templates/x', label: '消息模板' },
    ],
  },
  { section: '抖音', items: [{ to: '/templates/douyin', label: '消息模板' }] },
  {
    section: '会话',
    items: [
      { to: '/groups', label: '群组' },
      { to: '/private', label: '好友' },
    ],
  },
  { section: '游戏', items: [{ to: '/rust-rcon', label: 'Rust 群管' }] },
  {
    section: '系统',
    items: [
      { to: '/settings', label: '系统设置' },
      { to: '/logs', label: '运行日志' },
      { to: '/about', label: '关于' },
    ],
  },
]

const RAIL_WIDTH_CLASS = 'w-12'
const SIDEBAR_WIDTH_CLASS = 'w-64'
const NAV_SECTION_COLLAPSED_KEY = 'cyxcbot.navSectionCollapsed'

function pathInSection(pathname: string, items: NavItem[]): boolean {
  return items.some((item) =>
    item.to === '/'
      ? pathname === '/'
      : pathname === item.to || pathname.startsWith(`${item.to}/`),
  )
}

function loadCollapsedSections(): Set<string> {
  try {
    const raw = localStorage.getItem(NAV_SECTION_COLLAPSED_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((v): v is string => typeof v === 'string'))
  } catch {
    return new Set()
  }
}

function persistCollapsedSections(collapsed: Set<string>) {
  localStorage.setItem(NAV_SECTION_COLLAPSED_KEY, JSON.stringify([...collapsed]))
}

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
  const [about, setAbout] = useState<AboutInfo | null>(null)
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(loadCollapsedSections)

  useEffect(() => {
    let cancelled = false
    const fetchAbout = () => getAbout().then(data => { if (!cancelled) setAbout(data) })

    fetchAbout().catch(() => {})
    // ponytail: refetch once after 3s to pick up async update check result
    const timer = setTimeout(() => { fetchAbout().catch(() => {}) }, 3000)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [])

  if (location.pathname !== prevPathname) {
    setPrevPathname(location.pathname)
    setNavHoverExpanded(false)
    setNavCollapsed(false)
    // 当前路由所在分组保持展开，避免折叠后找不到当前位置
    const active = navSections.find((group) =>
      pathInSection(location.pathname, group.items),
    )
    if (active && collapsedSections.has(active.section)) {
      const next = new Set(collapsedSections)
      next.delete(active.section)
      persistCollapsedSections(next)
      setCollapsedSections(next)
    }
  }

  const toggleSection = (section: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev)
      if (next.has(section)) next.delete(section)
      else next.add(section)
      persistCollapsedSections(next)
      return next
    })
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

  const GITHUB_REPO = 'https://github.com/cyxc1124/cyxcbot'

  const versionLine = (() => {
    if (!about) return null
    const id = about.git_tag ?? (about.git_branch === 'develop' ? 'develop' : about.build_version === 'dev' ? 'dev' : (about.build_version || null))
    if (!id) return null
    const commit = about.git_commit
    const shortCommit = commit?.slice(0, 7)

    return (
      <>
        {about.git_tag ? (
          <a href={`${GITHUB_REPO}/releases/tag/${about.git_tag}`} target="_blank" rel="noopener noreferrer" className="hover:underline">{id}</a>
        ) : (
          id
        )}
        {shortCommit && commit && (
          <>
            {' · '}
            <a href={`${GITHUB_REPO}/commit/${commit}`} target="_blank" rel="noopener noreferrer" className="hover:underline">{shortCommit}</a>
          </>
        )}
      </>
    )
  })()

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
              <h1 className="flex items-center gap-1.5 truncate text-sm font-bold text-sidebar-foreground">
                <span>机器草</span>
                {about?.update_available && about?.update_url && (
                  <a
                    href={about.update_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded bg-amber-500/15 px-1.5 py-px text-[10px] font-medium text-amber-600 hover:underline dark:text-amber-400"
                  >
                    有新版本
                  </a>
                )}
              </h1>
              <p className="truncate text-xs text-muted-foreground">
                {versionLine}
              </p>
            </div>
          )}
        </div>

        {showFullNav ? (
          <>
            <nav className="flex-1 space-y-2 overflow-y-auto p-4">
              {navSections.map((group) => {
                const expanded = !collapsedSections.has(group.section)
                const panelId = `nav-section-${group.section}`
                return (
                  <div key={group.section} className="space-y-1">
                    <button
                      type="button"
                      onClick={() => toggleSection(group.section)}
                      aria-expanded={expanded}
                      aria-controls={panelId}
                      className="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-sm font-semibold text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
                    >
                      <span>{group.section}</span>
                      <span
                        className={`text-xs font-normal text-muted-foreground transition-transform ${
                          expanded ? 'rotate-90' : ''
                        }`}
                        aria-hidden
                      >
                        ›
                      </span>
                    </button>
                    {expanded && (
                      <div id={panelId} className="space-y-0.5 pl-1">
                        {group.items.map((item) => (
                          <NavLink
                            key={item.to}
                            to={item.to}
                            end={item.to === '/'}
                            onClick={() => {
                              setSidebarOpen(false)
                              setNavHoverExpanded(false)
                            }}
                            className={({ isActive }) =>
                              isActive
                                ? 'nav-link nav-link-active text-[13px]'
                                : 'nav-link text-[13px]'
                            }
                          >
                            {item.label}
                          </NavLink>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
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
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-border bg-background/80 px-4 backdrop-blur-sm lg:px-8">
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
                className="input w-auto min-w-28 py-1.5 text-sm"
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
                className="input w-auto min-w-28 py-1.5 text-sm"
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
