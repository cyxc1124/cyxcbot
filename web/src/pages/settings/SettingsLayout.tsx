import { NavLink, Outlet } from 'react-router-dom'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { PageLoading } from '../../components/LoadingSpinner'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { SettingsProvider, useSettingsForm } from './SettingsContext'

const settingsNavItems = [
  { to: '/settings/monitor', label: '监控', description: '动态与直播检查间隔、功能开关' },
  { to: '/settings/account', label: 'B 站账号', description: '扫码登录与 Cookie 管理' },
  { to: '/settings/bot', label: '机器人', description: 'QQ 命令权限与状态查询' },
  { to: '/settings/data', label: '数据保留', description: '审计日志与系统事件保留策略' },
]

function SettingsLayoutContent() {
  const {
    loading,
    error,
    load,
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
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">系统设置</h2>
        <p className="mt-1 text-sm text-slate-500">按类别管理监控、账号与数据相关配置</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="shrink-0 lg:w-52">
          <nav className="flex gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-900/40 lg:flex-col lg:overflow-visible">
            {settingsNavItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `shrink-0 rounded-md px-3 py-2.5 text-sm transition-colors lg:w-full ${
                    isActive
                      ? 'bg-white font-medium text-brand-700 shadow-sm dark:bg-slate-800 dark:text-brand-300'
                      : 'text-slate-600 hover:bg-white/80 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-white'
                  }`
                }
              >
                <span className="block">{item.label}</span>
                <span className="mt-0.5 hidden text-xs font-normal text-slate-500 lg:block">
                  {item.description}
                </span>
              </NavLink>
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
