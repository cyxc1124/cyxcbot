import { NavLink, Outlet } from 'react-router-dom'
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

function SettingsLayoutContent() {
  const {
    loading,
    error,
    retryLoad,
    settings,
    loggingOut,
    showLogoutConfirm,
    setShowLogoutConfirm,
    handleLogout,
  } = useSettingsForm()

  if (loading && !settings && !error) return <PageLoading />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">系统设置</h2>
        <p className="mt-1 text-sm text-muted-foreground">按平台管理监控、账号与通用配置</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="shrink-0 lg:w-52">
          <nav className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-card/40 p-1 lg:flex-col lg:gap-3 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0">
            {settingsNavSections.map((section) => (
              <div key={section.title} className="flex gap-1 lg:flex-col lg:gap-1">
                <p className="hidden px-3 py-1 text-sm font-semibold text-foreground lg:block">
                  {section.title}
                </p>
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `shrink-0 rounded-md px-3 py-2.5 text-[13px] transition-colors lg:w-full ${
                        isActive
                          ? 'bg-sidebar-accent font-medium text-sidebar-primary shadow-xs'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      }`
                    }
                  >
                    <span className="block">
                      <span className="lg:hidden text-muted-foreground">{section.title} · </span>
                      {item.label}
                    </span>
                    <span className="mt-0.5 hidden text-xs font-normal text-muted-foreground lg:block">
                      {item.description}
                    </span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
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
