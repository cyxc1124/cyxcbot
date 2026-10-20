import { Icon, type IconName } from '../../components/Icon'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { PageLoading } from '../../components/LoadingSpinner'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { SettingsProvider, useSettingsForm } from './SettingsContext'

type SettingsNavItem = { to: string; label: string; description: string }
type SettingsNavSection = { title: string; items: SettingsNavItem[] }

const settingsNavSections: SettingsNavSection[] = [
  {
    title: 'B 站',
    items: [
      {
        to: '/settings/bilibili-monitor',
        label: '监控参数',
        description: '动态与直播检查间隔、功能开关',
      },
      {
        to: '/settings/account',
        label: '账号',
        description: '扫码登录与 Cookie 管理',
      },
    ],
  },
  {
    title: 'X',
    items: [
      {
        to: '/settings/x-monitor',
        label: '监控参数',
        description: '推文检查间隔与分散检查',
      },
      {
        to: '/settings/x-account',
        label: '账号与代理',
        description: 'Bearer Token 与出站代理',
      },
    ],
  },
  {
    title: '抖音',
    items: [
      {
        to: '/settings/douyin-account',
        label: '账号',
        description: '扫码登录与 Cookie 管理',
      },
    ],
  },
  {
    title: '通用',
    items: [
      {
        to: '/settings/official-qq',
        label: '官方 Bot',
        description: 'QQ 开放平台 AppID / Secret',
      },
      {
        to: '/settings/bot',
        label: '机器人',
        description: 'QQ 命令权限与状态查询',
      },
      {
        to: '/settings/commands',
        label: '命令',
        description: '自定义命令触发词与开关',
      },
    ],
  },
]

function settingsIcon(path: string): IconName {
  if (path.includes('monitor')) return 'play'
  if (path.includes('account')) return 'user'
  if (path.includes('official')) return 'settings'
  return 'command'
}

function SettingsLayoutContent() {
  const {
    loading,
    saving,
    error,
    retryLoad,
    settings,
    loggingOut,
    showLogoutConfirm,
    setShowLogoutConfirm,
    handleLogout,
  } = useSettingsForm()

  const { pathname } = useLocation()
  const isMonitor = pathname === '/settings/bilibili-monitor' || pathname === '/settings/x-monitor'

  if (loading && !settings && !error) return <PageLoading />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">系统设置</h2>
        <p className="mt-1 text-sm text-muted-foreground">按平台管理监控、账号与通用配置</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="shrink-0 lg:sticky lg:top-24 lg:flex lg:min-h-[calc(100dvh-12rem)] lg:w-58 lg:flex-col lg:justify-between lg:gap-6">
          <nav aria-label="设置分类" className="flex gap-2 overflow-x-auto rounded-3xl border border-border bg-card p-2 shadow-xs lg:flex-col lg:gap-4 lg:p-3">
            {settingsNavSections.map((section) => (
              <div key={section.title} className="flex shrink-0 gap-1 lg:flex-col lg:gap-1">
                <p className="hidden px-3 py-1 text-sm font-semibold text-foreground lg:block">
                  {section.title}
                </p>
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    title={item.description}
                    className={({ isActive }) =>
                      `flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors lg:w-full ${
                        isActive
                          ? 'bg-sidebar-accent font-medium text-sidebar-primary'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      }`
                    }
                  >
                    <Icon name={settingsIcon(item.to)} className="hidden size-5 shrink-0 lg:block" />
                    <span className="block">
                      <span className="lg:hidden text-muted-foreground">{section.title} · </span>
                      {item.label}
                    </span>

                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          {isMonitor && <button type="submit" form="monitor-settings" disabled={!settings || saving} className="btn-primary hidden w-full lg:inline-flex">{saving ? '保存中…' : '保存设置'}</button>}
        </aside>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>

      <ConfirmDialog
        open={showLogoutConfirm}
        title="退出 B 站登录"
        message="确定退出 B 站登录？登录状态将被清除，相关监控功能可能受到影响。"
        confirmLabel="退出登录"
        loading={loggingOut}
        onCancel={() => {
          if (!loggingOut) setShowLogoutConfirm(false)
        }}
        onConfirm={() => void handleLogout()}
      />
    </div>
  )
}

export function SettingsLayout() {
  return (
    <SettingsProvider>
      <SettingsLayoutContent />
    </SettingsProvider>
  )
}
