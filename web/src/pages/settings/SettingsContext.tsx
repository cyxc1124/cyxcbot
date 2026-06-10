import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { useLoadingOnKeyChange } from '../../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../../hooks/useMountAsync'
import { createRetryHandler } from '../../utils/retryLoad'
import {
  getConnectionsStatus,
  getSettings,
  logoutBilibili,
  patchSettings,
  testCookie,
} from '../../api/client'
import type { BilibiliConnectionStatus, Settings } from '../../api/types'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'

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

interface SettingsContextValue {
  settings: Settings | null
  setSettings: React.Dispatch<React.SetStateAction<Settings | null>>
  bilibili: BilibiliConnectionStatus | null
  loading: boolean
  error: string
  load: () => Promise<void>
  retryLoad: () => void
  saving: boolean
  formDisabled: boolean
  handleSubmit: (e: FormEvent) => Promise<void>
  testing: boolean
  handleTestLogin: () => Promise<void>
  loggingOut: boolean
  showLogoutConfirm: boolean
  setShowLogoutConfirm: (open: boolean) => void
  handleLogout: () => Promise<void>
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const { showToast } = useToast()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useLoadingOnKeyChange('settings')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [bilibili, setBilibili] = useState<BilibiliConnectionStatus | null>(null)

  const load = useCallback(async () => {
    try {
      const [data, connections] = await Promise.all([getSettings(), getConnectionsStatus()])
      setSettings(data)
      setBilibili(connections.bilibili)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(load)

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const handleSubmit = useCallback(async (e: FormEvent) => {
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
      }
      const updated = await patchSettings(payload)
      setSettings(updated)
      showToast('success', '设置已保存')
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }, [settings, showToast])

  const handleTestLogin = useCallback(async () => {
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
  }, [load, showToast])

  const handleLogout = useCallback(async () => {
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
  }, [load, showToast])

  const value = useMemo(
    () => ({
      settings,
      setSettings,
      bilibili,
      loading,
      error,
      load,
      retryLoad,
      saving,
      formDisabled: !settings,
      handleSubmit,
      testing,
      handleTestLogin,
      loggingOut,
      showLogoutConfirm,
      setShowLogoutConfirm,
      handleLogout,
    }),
    [
      settings,
      bilibili,
      loading,
      error,
      load,
      retryLoad,
      saving,
      handleSubmit,
      testing,
      handleTestLogin,
      loggingOut,
      showLogoutConfirm,
      handleLogout,
    ],
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettingsForm() {
  const ctx = useContext(SettingsContext)
  if (!ctx) {
    throw new Error('useSettingsForm must be used within SettingsProvider')
  }
  return ctx
}
