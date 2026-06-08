import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getConnectionsStatus, getSettings, logoutBilibili, patchSettings, testCookie } from '../api/client'
import type { BilibiliConnectionStatus, Settings } from '../api/types'
import { BilibiliAccountInfo } from '../components/BilibiliAccountInfo'
import { BilibiliQrLogin } from '../components/BilibiliQrLogin'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorAlert } from '../components/ErrorAlert'
import { PageLoading } from '../components/LoadingSpinner'
import { useToast } from '../contexts/ToastContext'

function formatVerifyToastMessage(result: {
  success: boolean
  message: string
  username?: string | null
  uid?: string | null
}): string {
  const profile =
    result.username && result.uid
      ? `${result.username}（UID ${result.uid}）`
      : result.uid
        ? `UID ${result.uid}`
        : result.username || ''

  if (result.success) {
    return profile ? `登录有效 · ${profile}` : result.message
  }
  return profile ? `${result.message} · ${profile}` : result.message
}

export function SettingsPage() {
  const { showToast } = useToast()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [bilibili, setBilibili] = useState<BilibiliConnectionStatus | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [data, connections] = await Promise.all([getSettings(), getConnectionsStatus()])
      setSettings(data)
      setBilibili(connections.bilibili)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!settings) return
    setSaving(true)
    try {
      const payload: Parameters<typeof patchSettings>[0] = {
        dynamic_monitor_interval: settings.dynamic_monitor_interval,
        dynamic_enable_screenshot: settings.dynamic_enable_screenshot,
        live_monitor_interval: settings.live_monitor_interval,
        live_monitor_include_info: settings.live_monitor_include_info,
        live_monitor_use_websocket: settings.live_monitor_use_websocket,
        audit_log_retention_days: settings.audit_log_retention_days,
        event_retention_days: settings.event_retention_days,
      }
      const updated = await patchSettings(payload)
      setSettings(updated)
      showToast('success', '设置已保存')
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTestLogin = async () => {
    setTesting(true)
    try {
      const result = await testCookie()
      showToast(result.success ? 'success' : 'error', formatVerifyToastMessage(result))
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '验证失败')
    } finally {
      setTesting(false)
    }
  }

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      const result = await logoutBilibili()
      setShowLogoutConfirm(false)
      showToast('success', result.message)
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '退出失败')
    } finally {
      setLoggingOut(false)
    }
  }

  if (loading && !settings) return <PageLoading />
  if (!settings?.bilibili_cookie) {
    return <ErrorAlert message={error || '无法加载设置'} onRetry={load} />
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">系统设置</h2>
        <p className="mt-1 text-sm text-slate-500">监控间隔、功能开关与 B 站账号</p>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card space-y-4">
          <h3 className="font-semibold text-slate-900 dark:text-white">动态监控</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="dynamic_interval">
                检查间隔（秒）
              </label>
              <input
                id="dynamic_interval"
                type="number"
                min={30}
                max={3600}
                className="input"
                value={settings.dynamic_monitor_interval}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, dynamic_monitor_interval: Number(e.target.value) } : s,
                  )
                }
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={settings.dynamic_enable_screenshot}
                  onChange={(e) =>
                    setSettings((s) =>
                      s ? { ...s, dynamic_enable_screenshot: e.target.checked } : s,
                    )
                  }
                  className="rounded border-slate-300"
                />
                启用动态截图（Playwright）
              </label>
            </div>
          </div>
        </div>

        <div className="card space-y-4">
          <h3 className="font-semibold text-slate-900 dark:text-white">直播监控</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="live_interval">
                检查间隔（秒）
              </label>
              <input
                id="live_interval"
                type="number"
                min={30}
                max={3600}
                className="input"
                value={settings.live_monitor_interval}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, live_monitor_interval: Number(e.target.value) } : s,
                  )
                }
              />
            </div>
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={settings.live_monitor_include_info}
                  onChange={(e) =>
                    setSettings((s) =>
                      s ? { ...s, live_monitor_include_info: e.target.checked } : s,
                    )
                  }
                  className="rounded border-slate-300"
                />
                通知包含详细房间信息
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={settings.live_monitor_use_websocket}
                  onChange={(e) =>
                    setSettings((s) =>
                      s ? { ...s, live_monitor_use_websocket: e.target.checked } : s,
                    )
                  }
                  className="rounded border-slate-300"
                />
                启用 WebSocket 实时监控
              </label>
            </div>
          </div>
        </div>

        <div className="card space-y-4">
          <h3 className="font-semibold text-slate-900 dark:text-white">B 站账号</h3>

          {bilibili && <BilibiliAccountInfo account={bilibili} />}

          {!bilibili?.logged_in && (
            <BilibiliQrLogin
              onSuccess={() => {
                showToast('success', 'B 站扫码登录成功')
                void load()
              }}
              onError={(msg) => showToast('error', msg)}
            />
          )}

          {settings.bilibili_cookie.configured && (
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-secondary"
                disabled={testing}
                onClick={() => void handleTestLogin()}
              >
                {testing ? '验证中…' : '验证登录状态'}
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={loggingOut}
                onClick={() => setShowLogoutConfirm(true)}
              >
                退出 B 站登录
              </button>
            </div>
          )}
        </div>

        <div className="card space-y-4">
          <h3 className="font-semibold text-slate-900 dark:text-white">数据保留</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="audit_retention">
                审计日志保留天数
              </label>
              <input
                id="audit_retention"
                type="number"
                min={1}
                max={365}
                className="input"
                value={settings.audit_log_retention_days}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, audit_log_retention_days: Number(e.target.value) } : s,
                  )
                }
              />
            </div>
            <div>
              <label className="label" htmlFor="event_retention">
                系统事件保留天数
              </label>
              <input
                id="event_retention"
                type="number"
                min={1}
                max={365}
                className="input"
                value={settings.event_retention_days}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, event_retention_days: Number(e.target.value) } : s,
                  )
                }
              />
            </div>
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? '保存中…' : '保存设置'}
        </button>
      </form>

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
