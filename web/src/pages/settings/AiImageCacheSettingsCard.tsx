import { useState, type FormEvent } from 'react'
import type { Settings } from '../../api/types'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useToast } from '../../contexts/ToastContext'
import { useSettingsForm } from './SettingsContext'

/** 需与 shared/config/ai_image.py 的 CACHE_MAX_ENTRIES_* 保持一致 */
const DEFAULT_MAX_ENTRIES = 500
const MAX_ENTRIES_LIMIT = 10000

function formFrom(settings: Settings | null) {
  return {
    enabled: settings?.ai_image_cache_enabled ?? true,
    maxEntries: String(settings?.ai_image_cache_max_entries ?? DEFAULT_MAX_ENTRIES),
  }
}

/** 缓存开关与条数上限；保存后通知页面刷新列表（调低上限会立即清理）。 */
export function AiImageCacheSettingsCard({ onSaved }: { onSaved: () => void }) {
  const { showToast } = useToast()
  const { settings, formDisabled, saving, savePartial } = useSettingsForm()
  const [form, setForm] = useState(() => formFrom(settings))
  const [syncedSettings, setSyncedSettings] = useState(settings)
  const disabled = formDisabled || saving

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    setForm(formFrom(settings))
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const maxEntries = Number(form.maxEntries)
    if (!Number.isInteger(maxEntries) || maxEntries < 1 || maxEntries > MAX_ENTRIES_LIMIT) {
      showToast('error', `最多保留条数须为 1–${MAX_ENTRIES_LIMIT} 的整数`)
      return
    }
    await savePartial({ ai_image_cache_enabled: form.enabled, ai_image_cache_max_entries: maxEntries })
    onSaved()
  }

  return (
    <form className="card space-y-4" onSubmit={(event) => void handleSubmit(event)}>
      <div>
        <h3 className="font-semibold text-foreground">缓存设置</h3>
        <p className="mt-1 text-sm text-muted-foreground">保存后立即生效。</p>
      </div>
      <div className="flex items-center gap-4 rounded-lg border border-border bg-muted/30 px-3 py-3">
        <div className="min-w-0 flex-1">
          <div id="ai-image-cache-enabled" className="text-sm font-medium text-foreground">启用检测缓存</div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            关闭后每次都重新检测，也不再保存新结果；已保存的记录保留，仍可在下方查看、修改或删除。
          </p>
        </div>
        <ToggleSwitch checked={form.enabled} disabled={disabled} ariaLabelledBy="ai-image-cache-enabled"
          onChange={(enabled) => setForm({ ...form, enabled })} />
      </div>
      <div>
        <label className="label" htmlFor="ai-image-cache-max-entries">最多保留的未修改记录（条）</label>
        <input id="ai-image-cache-max-entries" type="number" min={1} max={MAX_ENTRIES_LIMIT} className="input w-40"
          value={form.maxEntries} disabled={disabled}
          onChange={(event) => setForm({ ...form, maxEntries: event.target.value })} />
        <p className="mt-2 text-xs text-muted-foreground">
          1–{MAX_ENTRIES_LIMIT}，默认 {DEFAULT_MAX_ENTRIES}。超出时删除最久没有被询问的未修改记录，修改过的记录不计入；调低后保存时立即清理。每条记录含一张预览图，通常几十 KB。
        </p>
      </div>
      <button type="submit" className="btn-primary" disabled={disabled}>{saving ? '保存中…' : '保存设置'}</button>
    </form>
  )
}
