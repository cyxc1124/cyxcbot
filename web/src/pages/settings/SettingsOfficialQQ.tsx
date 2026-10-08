import { useState } from 'react'
import { patchSettings } from '../../api/client'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

export function SettingsOfficialQQPage() {
  const { showToast } = useToast()
  const { settings, setSettings, formDisabled, load } = useSettingsForm()
  const [appId, setAppId] = useState('')
  const [secret, setSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [sandboxDraft, setSandboxDraft] = useState<boolean | null>(null)
  const [websocketDraft, setWebsocketDraft] = useState<boolean | null>(null)

  const configured = Boolean(settings?.official_qq?.secret.configured)
  const currentAppId = settings?.official_qq?.app_id ?? ''
  const isSandbox = sandboxDraft ?? settings?.official_qq?.is_sandbox ?? false
  const useWebsocket = websocketDraft ?? settings?.official_qq?.use_websocket ?? false

  const handleSave = async () => {
    const nextAppId = appId.trim() || currentAppId
    if (!nextAppId) {
      showToast('error', '请填写 AppID')
      return
    }
    if (!configured && !secret.trim()) {
      showToast('error', '请填写 AppSecret')
      return
    }
    setSaving(true)
    try {
      const payload: Parameters<typeof patchSettings>[0] = {
        official_qq_app_id: nextAppId,
        official_qq_is_sandbox: isSandbox,
        official_qq_use_websocket: useWebsocket,
      }
      if (secret.trim()) {
        payload.official_qq_app_secret = secret.trim()
      }
      const updated = await patchSettings(payload)
      setSettings(updated)
      setAppId('')
      setSecret('')
      setSandboxDraft(null)
      setWebsocketDraft(null)
      showToast('success', useWebsocket ? '设置已保存，将尝试旧版 WebSocket 连接' : '设置已保存，等待官方 Webhook 回调')
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async () => {
    setClearing(true)
    try {
      const updated = await patchSettings({
        official_qq_app_id: '',
        official_qq_app_secret: '',
      })
      setSettings(updated)
      setAppId('')
      setSecret('')
      setShowClearConfirm(false)
      showToast('success', '已清除官方 Bot 凭证并断开连接')
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '清除失败'))
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">官方 QQ 机器人</h3>
        <p className="text-sm text-muted-foreground">
          在{' '}
          <a
            href="https://q.qq.com"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-primary hover:underline"
          >
            QQ 开放平台
          </a>{' '}
          创建机器人后填写 AppID 与 AppSecret。凭证加密存库，保存后立即生效，无需重启。与
          OneBot 可同时在线：官方 Bot 支持群聊和私聊的命令、链接解析回复。动态、直播和 X 可配置官方目标，主动发送能力以平台策略和回执为准。
        </p>

        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm space-y-2">
          <p>推荐使用 Webhook：将公网 HTTPS 地址的 <code>/qq/webhook</code> 转发到机器人监听端口（默认 8080），在开放平台完成回调验证、事件订阅和出口 IP 白名单配置。Web Admin 端口 8081 不接收回调。</p>
          <p>保存凭证不代表已连接；首次有效事件到达后，可在仪表盘查看连接状态。</p>
          <p>被动回复仍受平台限制：同一条用户消息最多回复 5 次，较多图片或视频可能无法一次全部返回。</p>
        </div>

        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
          <span className="text-muted-foreground">状态：</span>
          {configured ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              已配置
              {currentAppId ? `（AppID ${currentAppId}）` : ''}
            </span>
          ) : (
            <span className="text-muted-foreground">未配置</span>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="official-qq-app-id">
            AppID
          </label>
          <input
            id="official-qq-app-id"
            className="input w-full font-mono text-sm"
            placeholder={currentAppId || '开放平台 AppID'}
            value={appId}
            disabled={formDisabled || saving}
            onChange={(e) => setAppId(e.target.value)}
            autoComplete="off"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="official-qq-secret">
            AppSecret
          </label>
          <input
            id="official-qq-secret"
            type="password"
            className="input w-full font-mono text-sm"
            placeholder={configured ? '已配置，留空则不修改' : '开放平台 AppSecret'}
            value={secret}
            disabled={formDisabled || saving}
            onChange={(e) => setSecret(e.target.value)}
            autoComplete="new-password"
          />
        </div>

        <div className="flex items-center gap-4 rounded-lg border border-border bg-muted/30 px-3 py-3">
          <div className="min-w-0 flex-1">
            <div id="official-qq-sandbox-label" className="text-sm font-medium text-foreground">沙箱环境</div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              仅调试时开启；正式使用请关闭
            </p>
          </div>
          <ToggleSwitch
            ariaLabelledBy="official-qq-sandbox-label"
            checked={isSandbox}
            disabled={formDisabled || saving}
            onChange={(checked) => setSandboxDraft(checked)}
          />
        </div>

        <div className="flex items-center gap-4 rounded-lg border border-border bg-muted/30 px-3 py-3">
          <div className="min-w-0 flex-1">
            <div id="official-qq-websocket-label" className="text-sm font-medium text-foreground">旧版 WebSocket 连接</div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              默认关闭，使用 Webhook。官方已停止维护 WebSocket，仅为仍可使用旧链路的应用保留
            </p>
          </div>
          <ToggleSwitch
            ariaLabelledBy="official-qq-websocket-label"
            checked={useWebsocket}
            disabled={formDisabled || saving}
            onChange={(checked) => setWebsocketDraft(checked)}
          />
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={formDisabled || saving}
            onClick={() => void handleSave()}
          >
            {saving ? '保存中…' : '保存设置'}
          </button>
          {configured && (
            <button
              type="button"
              className="btn-danger"
              disabled={formDisabled || clearing}
              onClick={() => setShowClearConfirm(true)}
            >
              {clearing ? '清除中…' : '清除凭证'}
            </button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={showClearConfirm}
        title="清除官方 Bot 凭证"
        message="确定清除 AppID / AppSecret？清除后官方 Bot 将断开，直至重新配置。"
        confirmLabel="清除"
        loading={clearing}
        onConfirm={() => void handleClear()}
        onCancel={() => {
          if (!clearing) setShowClearConfirm(false)
        }}
      />
    </div>
  )
}
