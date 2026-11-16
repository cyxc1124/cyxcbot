import { useState } from 'react'
import {
  clearXBearer,
  saveXBearer,
  testXBearer,
} from '../../api/client'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { ProxySettingCard } from './ProxySettingCard'
import { useSettingsForm } from './SettingsContext'

export function SettingsXAccountPage() {
  const { showToast } = useToast()
  const { settings, formDisabled, load } = useSettingsForm()
  const [bearerText, setBearerText] = useState('')
  const [savingBearer, setSavingBearer] = useState(false)
  const [clearingBearer, setClearingBearer] = useState(false)
  const [testingBearer, setTestingBearer] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)

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

      <ProxySettingCard
        field="x_proxy_id"
        title="出站代理"
        description="推文订阅、X 链接解析以及在后台添加博主时查询 X 用户，都通过这里选择的代理访问 X API 和推文媒体。国内服务器通常需要选择代理。"
      />

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
