import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useSidebar } from '../contexts/SidebarContext'
import { getAbout } from '../api/client'
import type { AboutInfo } from '../api/types'
import { ThemeModeSwitch } from './ThemeModeSwitch'
import { BotConnectionStatus } from './BotConnectionStatus'
import { Icon, type IconName } from './Icon'
import { AppBrand, AppFooter } from './AppBrand'

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

function navIcon(path: string): IconName {
  if (path === '/') return 'home'
  if (path === '/live') return 'video'
  if (path === '/dynamic' || path === '/x') return 'play'
  if (path.startsWith('/templates')) return 'messages'
  if (path === '/groups' || path === '/private') return 'users'
  if (path === '/settings') return 'settings'
  if (path === '/logs') return 'document'
  if (path === '/rust-rcon') return 'command'
  return 'info'
}

const RAIL_WIDTH_CLASS = 'w-12'
const SIDEBAR_WIDTH_CLASS = 'w-60'
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
  try {
    localStorage.setItem(NAV_SECTION_COLLAPSED_KEY, JSON.stringify([...collapsed]))
  } catch {
    // 隐私模式 / 配额满时仍保留内存态，不影响折叠交互
  }
}

/** 展开含当前路由的分组；直达/刷新时也要跑，不能只靠 pathname 变化。 */
function expandActiveSection(collapsed: Set<string>, pathname: string): Set<string> {
  const active = navSections.find((group) => pathInSection(pathname, group.items))
  if (!active || !collapsed.has(active.section)) return collapsed
  const next = new Set(collapsed)
  next.delete(active.section)
  persistCollapsedSections(next)
  return next
}

export function Layout() {
  const { user, logout } = useAuth()
  const { navCollapsed, setNavCollapsed } = useSidebar()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [navHoverExpanded, setNavHoverExpanded] = useState(false)
  const [prevPathname, setPrevPathname] = useState(location.pathname)
  const [about, setAbout] = useState<AboutInfo | null>(null)
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(() =>
    expandActiveSection(loadCollapsedSections(), location.pathname),
  )

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
    const next = expandActiveSection(collapsedSections, location.pathname)
    if (next !== collapsedSections) setCollapsedSections(next)
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
    ? 'invisible -translate-x-full lg:visible lg:translate-x-0'
    : sidebarOpen
      ? 'translate-x-0'
      : 'invisible -translate-x-full lg:visible lg:translate-x-0'

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
    <div className="console-shell min-h-screen bg-background">
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
          className={`relative flex min-h-22 shrink-0 items-center border-b border-sidebar-border ${
            showFullNav ? 'gap-3 px-4 py-4' : 'justify-center px-0'
          }`}
        >
          {!showFullNav && <img src="/brand-avatar.png" alt="机器草头像" className="size-9 rounded-xl border border-border" width={36} height={36} />}
          {showFullNav && <button type="button" aria-label={navCollapsed ? '展开导航' : '收起导航'} title={navCollapsed ? '展开导航' : '收起导航'} onClick={toggleNavCollapsed} className="btn-ghost absolute top-3 right-1 hidden min-h-7 px-1 lg:inline-flex"><Icon name="chevron-down" className="size-3 rotate-90" /></button>}
          {showFullNav && (
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <AppBrand compact version={versionLine ?? undefined} subtitle="机器人管理后台" />
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
              </div>
            </div>
          )}
        </div>

        {showFullNav ? (
          <>
            <nav className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
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
                      className="flex w-full items-center justify-between rounded-lg px-3 py-1.5 text-left text-sm font-semibold text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
                    >
                      <span>{group.section}</span>
                      <span
                        className={`text-xs font-normal text-muted-foreground transition-transform ${
                          expanded ? 'rotate-180' : ''
                        }`}
                        aria-hidden
                      >
                        <Icon name="chevron-down" className="size-3" />
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
                            <Icon name={navIcon(item.to)} className="size-5 shrink-0" />
                            <span>{item.label}</span>
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
          navCollapsed ? 'lg:pl-12' : 'lg:pl-60'
        }`}
      >
        <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-2 border-b border-transparent bg-background/95 px-3 py-2 backdrop-blur-sm sm:px-4 lg:pointer-events-none lg:bg-transparent lg:px-12 lg:backdrop-blur-none">
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              className={navCollapsed ? "btn-ghost pointer-events-auto hidden text-sm lg:inline-flex" : "hidden"}
              onClick={toggleNavCollapsed}
            >
              {navCollapsed ? '展开导航' : '收起导航'}
            </button>
            <button
              type="button"
              className="btn-ghost px-2 text-sm lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              菜单
            </button>
          </div>
          <div className="pointer-events-auto flex items-center gap-2 sm:gap-4">
            <BotConnectionStatus />
            <ThemeModeSwitch />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1560px] min-w-0 flex-1 px-4 py-6 lg:-mt-10 lg:px-12 lg:pb-10 lg:pt-2">
          <Outlet />
        </main>
        <AppFooter />
      </div>
    </div>
  )
}
