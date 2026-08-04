import { useState } from 'react'
import { DouyinQrLogin } from '../../components/DouyinQrLogin'
import { clearDouyinCookie, logoutDouyin, saveDouyinCookie } from '../../api/client'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

export function SettingsDouyinAccountPage() {
  const { showToast } = useToast()
  const { settings, formDisabled, load } = useSettingsForm()
  const [cookieText, setCookieText] = useState('')
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)

  const configured = Boolean(settings?.douyin_cookie?.configured)

  const handleSave = async () => {
    const value = cookieText.trim()
    if (!value) {
      showToast('error', '请粘贴 Cookie 字符串')
      return
    }
    setSaving(true)
    try {
      const result = await saveDouyinCookie(value)
      setCookieText('')
      showToast('success', result.message || '抖音 Cookie 已保存')
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
      await logoutDouyin().catch(async () => {
        await clearDouyinCookie()
      })
      showToast('success', '已退出抖音登录')
      setShowLogoutConfirm(false)
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '退出失败'))
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">抖音账号</h3>
        <p className="text-sm text-muted-foreground">
          用于解析抖音分享链接并下载视频。未配置时仍会尝试游客态解析；建议扫码登录或粘贴
          Cookie 以提高成功率。
        </p>

        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
          <span className="text-muted-foreground">状态：</span>
          {configured ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              已配置
              {settings?.douyin_cookie?.preview
                ? `（${settings.douyin_cookie.preview}）`
                : ''}
            </span>
          ) : (
            <span className="text-muted-foreground">未配置</span>
          )}
        </div>

        {configured && (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="btn-danger"
              disabled={formDisabled || clearing}
              onClick={() => setShowLogoutConfirm(true)}
            >
              {clearing ? '退出中…' : '退出抖音登录'}
            </button>
          </div>
        )}
      </div>

      {!formDisabled && (
        <DouyinQrLogin
          onSuccess={() => {
            showToast('success', '抖音扫码登录成功')
            void load()
          }}
          onError={(msg) => showToast('error', msg)}
        />
      )}

      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">手动粘贴 Cookie</h3>
        <p className="text-sm text-muted-foreground">
          扫码失败时可从浏览器开发者工具复制 Cookie 字符串作为兜底。
        </p>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="douyin-cookie">
            Cookie
          </label>
          <textarea
            id="douyin-cookie"
            className="input min-h-28 w-full font-mono text-xs"
            placeholder="ttwid=...; odin_tt=...; passport_csrf_token=...; sessionid=..."
            value={cookieText}
            disabled={formDisabled || saving}
            onChange={(e) => setCookieText(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            建议字段：ttwid、odin_tt、passport_csrf_token、sessionid；可选 sid_guard。msToken
            可缺，将自动生成。
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          disabled={formDisabled || saving || !cookieText.trim()}
          onClick={() => void handleSave()}
        >
          {saving ? '保存中…' : '保存 Cookie'}
        </button>
      </div>

      <ConfirmDialog
        open={showLogoutConfirm}
        title="退出抖音登录"
        message="确定退出抖音登录？登录状态将被清除，链接解析将回退到游客态。"
        confirmLabel="退出登录"
        loading={clearing}
        onConfirm={() => void handleClear()}
        onCancel={() => {
          if (!clearing) setShowLogoutConfirm(false)
        }}
      />
    </div>
  )
}
