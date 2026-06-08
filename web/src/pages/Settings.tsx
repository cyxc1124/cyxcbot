import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getSettings, patchSettings, testCookie } from '../api/client'
import type { Settings } from '../api/types'
import { BilibiliQrLogin } from '../components/BilibiliQrLogin'
import { ErrorAlert } from '../components/ErrorAlert'
import { PageLoading } from '../components/LoadingSpinner'
import { useToast } from '../contexts/ToastContext'

export function SettingsPage() {
  const { showToast } = useToast()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [cookieInput, setCookieInput] = useState('')
  const [showCookie, setShowCookie] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getSettings()
      setSettings(data)
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
      if (cookieInput.trim()) {
        payload.bilibili_cookie = cookieInput.trim()
      }
      const updated = await patchSettings(payload)
      setSettings(updated)
      setCookieInput('')
      showToast('success', '设置已保存')
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTestCookie = async () => {
    setTesting(true)
    try {
      if (cookieInput.trim()) {
        await patchSettings({ bilibili_cookie: cookieInput.trim() })
      }
      const result = await testCookie()
      showToast(result.success ? 'success' : 'error', result.message)
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '测试失败')
    } finally {
      setTesting(false)
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
        <p className="mt-1 text-sm text-slate-500">监控间隔、功能开关与 Cookie 配置</p>
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
          <h3 className="font-semibold text-slate-900 dark:text-white">B 站 Cookie</h3>
          <BilibiliQrLogin
            onSuccess={() => {
              showToast('success', 'B 站扫码登录成功')
              void load()
            }}
            onError={(msg) => showToast('error', msg)}
          />
          <p className="text-sm text-slate-500">
            状态：
            {settings.bilibili_cookie.configured ? (
              <span className="ml-1 text-emerald-600">
                已配置
                {settings.bilibili_cookie.preview && (
                  <code className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">
                    {settings.bilibili_cookie.preview}
                  </code>
                )}
              </span>
            ) : (
              <span className="ml-1 text-amber-600">未配置</span>
            )}
          </p>
          <div>
            <label className="label" htmlFor="cookie">
              更新 Cookie（留空则不修改）
            </label>
            <div className="flex gap-2">
              <input
                id="cookie"
                type={showCookie ? 'text' : 'password'}
                className="input font-mono text-xs"
                value={cookieInput}
                onChange={(e) => setCookieInput(e.target.value)}
                placeholder="SESSDATA=...; DedeUserID=...; bili_jct=..."
              />
              <button
                type="button"
                className="btn-secondary shrink-0"
                onClick={() => setShowCookie((v) => !v)}
              >
                {showCookie ? '隐藏' : '显示'}
              </button>
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary"
            disabled={testing}
            onClick={handleTestCookie}
          >
            {testing ? '测试中…' : '测试 Cookie 有效性'}
          </button>
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
    </div>
  )
}
