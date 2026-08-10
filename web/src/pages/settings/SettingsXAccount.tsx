import { useEffect, useState } from 'react'
import {
  clearXBearer,
  patchSettings,
  saveXBearer,
  testXBearer,
} from '../../api/client'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

const PROXY_SCHEMES = ['http', 'https', 'socks5'] as const

export function SettingsXAccountPage() {
  const { showToast } = useToast()
  const { settings, setSettings, formDisabled, load } = useSettingsForm()
  const [bearerText, setBearerText] = useState('')
  const [savingBearer, setSavingBearer] = useState(false)
  const [clearingBearer, setClearingBearer] = useState(false)
  const [testingBearer, setTestingBearer] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  const [proxyEnabled, setProxyEnabled] = useState(false)
  const [proxyScheme, setProxyScheme] = useState<string>('http')
  const [proxyHost, setProxyHost] = useState('')
  const [proxyPort, setProxyPort] = useState(7890)
  const [proxyUsername, setProxyUsername] = useState('')
  const [proxyPassword, setProxyPassword] = useState('')
  const [savingProxy, setSavingProxy] = useState(false)

  useEffect(() => {
    if (!settings?.x_proxy) return
    setProxyEnabled(settings.x_proxy.enabled)
    setProxyScheme(settings.x_proxy.scheme || 'http')
    setProxyHost(settings.x_proxy.host || '')
    setProxyPort(settings.x_proxy.port || 7890)
    setProxyUsername(settings.x_proxy.username || '')
    setProxyPassword('')
  }, [settings?.x_proxy])

  const configured = Boolean(settings?.x_api_bearer?.configured)

  const handleSaveBearer = async () => {
    const value = bearerText.trim()
    if (!value) {
      showToast('error', '请粘贴 Bearer Token')
      return
    }
    setSavingBearer(true)
    try {
      const result = await saveXBearer(value)
      setBearerText('')
      showToast('success', result.message || 'Bearer Token 已保存')
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSavingBearer(false)
    }
  }

  const handleClearBearer = async () => {
    setClearingBearer(true)
    try {
      const result = await clearXBearer()
      showToast('success', result.message || '已清除 Bearer Token')
      setShowClearConfirm(false)
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '清除失败'))
    } finally {
      setClearingBearer(false)
    }
  }

  const handleTestBearer = async () => {
    setTestingBearer(true)
    try {
      const result = await testXBearer('X')
      showToast(result.success ? 'success' : 'error', result.message)
    } catch (err) {
      showToast('error', formatApiError(err, '测试失败'))
    } finally {
      setTestingBearer(false)
    }
  }

  const handleSaveProxy = async () => {
    if (proxyEnabled && !proxyHost.trim()) {
      showToast('error', '启用代理时请填写主机地址')
      return
    }
    setSavingProxy(true)
    try {
      const payload: Parameters<typeof patchSettings>[0] = {
        x_proxy_enabled: proxyEnabled,
        x_proxy_scheme: proxyScheme,
        x_proxy_host: proxyHost.trim(),
        x_proxy_port: proxyPort,
        x_proxy_username: proxyUsername.trim(),
      }
      if (proxyPassword.length > 0) {
        payload.x_proxy_password = proxyPassword
      }
      const updated = await patchSettings(payload)
      setSettings(updated)
      setProxyPassword('')
      showToast('success', '代理设置已保存')
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSavingProxy(false)
    }
  }

  const handleClearProxyPassword = async () => {
    setSavingProxy(true)
    try {
      const updated = await patchSettings({ x_proxy_password: '' })
      setSettings(updated)
      setProxyPassword('')
      showToast('success', '代理密码已清除')
    } catch (err) {
      showToast('error', formatApiError(err, '清除失败'))
    } finally {
      setSavingProxy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">X API Bearer Token</h3>
        <p className="text-sm text-muted-foreground">
          用于调用 X API v2 查询用户与拉取推文。请在 X Developer Portal 创建 App 并复制
          Bearer Token。
        </p>

        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
          <span className="text-muted-foreground">状态：</span>
          {configured ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              已配置
              {settings?.x_api_bearer?.preview
                ? `（${settings.x_api_bearer.preview}）`
                : ''}
            </span>
          ) : (
            <span className="text-muted-foreground">未配置</span>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="x-bearer">
            Bearer Token
          </label>
          <textarea
            id="x-bearer"
            className="input min-h-24 w-full font-mono text-xs"
            placeholder="AAAA..."
            value={bearerText}
            disabled={formDisabled || savingBearer}
            onChange={(e) => setBearerText(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={formDisabled || savingBearer || !bearerText.trim()}
            onClick={() => void handleSaveBearer()}
          >
            {savingBearer ? '保存中…' : '保存 Token'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={formDisabled || testingBearer || !configured}
            onClick={() => void handleTestBearer()}
          >
            {testingBearer ? '测试中…' : '测试连接'}
          </button>
          {configured && (
            <button
              type="button"
              className="btn-danger"
              disabled={formDisabled || clearingBearer}
              onClick={() => setShowClearConfirm(true)}
            >
              {clearingBearer ? '清除中…' : '清除 Token'}
            </button>
          )}
        </div>
      </div>

      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">出站代理</h3>
        <p className="text-sm text-muted-foreground">
          访问 X API 时使用的 HTTP/HTTPS/SOCKS5 代理。国内网络通常需要启用。
        </p>

        <div className="flex items-center gap-4 py-1">
          <span className="min-w-0 flex-1 text-sm text-foreground">启用代理</span>
          <ToggleSwitch
            checked={proxyEnabled}
            disabled={formDisabled || savingProxy}
            onChange={setProxyEnabled}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="x-proxy-scheme">
              协议
            </label>
            <select
              id="x-proxy-scheme"
              className="input"
              value={proxyScheme}
              disabled={formDisabled || savingProxy}
              onChange={(e) => setProxyScheme(e.target.value)}
            >
              {PROXY_SCHEMES.map((scheme) => (
                <option key={scheme} value={scheme}>
                  {scheme}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="x-proxy-port">
              端口
            </label>
            <input
              id="x-proxy-port"
              type="number"
              min={1}
              max={65535}
              className="input"
              value={proxyPort}
              disabled={formDisabled || savingProxy}
              onChange={(e) => setProxyPort(Number(e.target.value))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="x-proxy-host">
              主机
            </label>
            <input
              id="x-proxy-host"
              className="input"
              placeholder="127.0.0.1"
              value={proxyHost}
              disabled={formDisabled || savingProxy}
              onChange={(e) => setProxyHost(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="x-proxy-username">
              用户名（可选）
            </label>
            <input
              id="x-proxy-username"
              className="input"
              value={proxyUsername}
              disabled={formDisabled || savingProxy}
              onChange={(e) => setProxyUsername(e.target.value)}
              autoComplete="off"
            />
          </div>
          <div>
            <label className="label" htmlFor="x-proxy-password">
              密码（可选）
            </label>
            <input
              id="x-proxy-password"
              type="password"
              className="input"
              placeholder={
                settings?.x_proxy?.password_configured
                  ? '已配置，留空则不修改'
                  : '未配置'
              }
              value={proxyPassword}
              disabled={formDisabled || savingProxy}
              onChange={(e) => setProxyPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={formDisabled || savingProxy}
            onClick={() => void handleSaveProxy()}
          >
            {savingProxy ? '保存中…' : '保存代理'}
          </button>
          {settings?.x_proxy?.password_configured && (
            <button
              type="button"
              className="btn-secondary"
              disabled={formDisabled || savingProxy}
              onClick={() => void handleClearProxyPassword()}
            >
              清除代理密码
            </button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="清除 Bearer Token"
        message="确定清除 X API Bearer Token？清除后将无法拉取推文，直至重新配置。"
        confirmLabel="清除"
        loading={clearingBearer}
        onConfirm={() => void handleClearBearer()}
        onCancel={() => {
          if (!clearingBearer) setShowClearConfirm(false)
        }}
      />
    </div>
  )
}
