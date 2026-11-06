import { Outlet, useLocation } from 'react-router-dom'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { PageLoading } from '../../components/LoadingSpinner'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { findNavigation } from '../../constants/navigation'
import { SettingsProvider, useSettingsForm } from './SettingsContext'

function SettingsLayoutContent() {
  const { loading, error, retryLoad, settings, loggingOut, showLogoutConfirm, setShowLogoutConfirm, handleLogout } = useSettingsForm()
  const current = findNavigation(useLocation().pathname)

  if (loading && !settings && !error) return <PageLoading />

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">
          {current?.item.title ?? (current?.section === '系统' ? current.item.label : `${current?.section ?? ''}${current?.item.label ?? '设置'}`)}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{current?.item.description}</p>
      </div>
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}
      <Outlet />
      <ConfirmDialog
        open={showLogoutConfirm}
        title="移除全部 B 站账号"
        message="确定移除全部 B 站账号？所有已保存的登录凭据将被清除，相关监控功能可能受到影响。"
        confirmLabel="移除全部"
        loading={loggingOut}
        onCancel={() => { if (!loggingOut) setShowLogoutConfirm(false) }}
        onConfirm={() => void handleLogout()}
      />
    </div>
  )
}

export function SettingsLayout() {
  return <SettingsProvider><SettingsLayoutContent /></SettingsProvider>
}
