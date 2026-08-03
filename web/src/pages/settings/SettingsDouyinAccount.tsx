import { useState } from 'react'
import { clearDouyinCookie, saveDouyinCookie } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

export function SettingsDouyinAccountPage() {
  const { showToast } = useToast()
  const { settings, formDisabled, load } = useSettingsForm()
  const [cookieText, setCookieText] = useState('')
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)

  const configured = Boolean(settings?.douyin_cookie?.configured)

  const handleSave = async () => {
    const value = cookieText.trim()
    if (!value) {
      showToast('error', '请粘贴 Cookie 字符串')
      return
    }
    setSaving(true)
    try {
      await saveDouyinCookie(value)
      setCookieText('')
      showToast('success', '抖音 Cookie 已保存')
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
      await clearDouyinCookie()
      showToast('success', '已清除抖音 Cookie')
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
        <h3 className="font-semibold text-foreground">抖音账号</h3>
        <p className="text-sm text-muted-foreground">
          用于解析抖音分享链接并下载视频。请从浏览器开发者工具复制 Cookie 字符串粘贴保存。
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

        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground" htmlFor="douyin-cookie">
            Cookie
          </label>
          <textarea
            id="douyin-cookie"
            className="input min-h-28 w-full font-mono text-xs"
            placeholder="ttwid=...; odin_tt=...; passport_csrf_token=...; ..."
            value={cookieText}
            disabled={formDisabled || saving}
            onChange={(e) => setCookieText(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            必填字段：ttwid、odin_tt、passport_csrf_token（msToken 可缺，将自动生成）
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={formDisabled || saving || !cookieText.trim()}
            onClick={() => void handleSave()}
          >
            {saving ? '保存中…' : '保存 Cookie'}
          </button>
          {configured && (
            <button
              type="button"
              className="btn-danger"
              disabled={formDisabled || clearing}
              onClick={() => void handleClear()}
            >
              {clearing ? '清除中…' : '清除 Cookie'}
            </button>
          )}
        </div>
      </div>

      <div className="card space-y-3 opacity-70">
        <h3 className="font-semibold text-foreground">扫码登录</h3>
        <p className="text-sm text-muted-foreground">
          扫码登录即将支持，请先粘贴 Cookie。
        </p>
        <button type="button" className="btn-secondary" disabled>
          扫码登录（即将支持）
        </button>
      </div>
    </div>
  )
}
