import { useCallback, useState, type FormEvent } from 'react'
import { getSettings, patchSettings } from '../api/client'
import type { Settings } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { useMountAsync } from '../hooks/useMountAsync'
import { formatApiError } from '../utils/apiError'
import { LOG_LEVEL_CLASS, OUTPUT_LOG_LEVELS } from '../pages/logsDisplay'
import { LoadErrorBanner } from './LoadErrorBanner'

type OutputLevels = Pick<Settings, 'log_level' | 'log_file_level'>

export function LogLevelSettings() {
  const { showToast } = useToast()
  const [saved, setSaved] = useState<OutputLevels | null>(null)
  const [draft, setDraft] = useState<OutputLevels | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getSettings()
      const levels = { log_level: data.log_level, log_file_level: data.log_file_level }
      setSaved(levels)
      setDraft(levels)
    } catch (err) {
      setError(formatApiError(err, '加载日志设置失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useMountAsync(load)

  const handleSave = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft || saving) return
    setSaving(true)
    setError('')
    try {
      const data = await patchSettings(draft)
      const levels = { log_level: data.log_level, log_file_level: data.log_file_level }
      setSaved(levels)
      setDraft(levels)
      showToast('success', '日志级别已保存并立即生效')
    } catch (err) {
      setError(formatApiError(err, '保存日志设置失败'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section aria-label="日志输出级别" className="flex flex-col gap-3 border-t border-border/70 pt-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-sm font-medium text-foreground">输出级别</h3>
        <span className="text-xs text-muted-foreground">
          {saved ? `终端 ${saved.log_level} · 文件 ${saved.log_file_level}` : loading ? '加载中…' : '未加载'}
        </span>
      </div>
      <form onSubmit={handleSave} className="flex flex-col items-start gap-3" aria-busy={loading || saving}>
        <p id="log-output-help" className="text-xs text-muted-foreground">保存后立即生效并持久化，与上方 Web 显示筛选独立。</p>
        {error && <LoadErrorBanner message={error} onRetry={saved ? undefined : () => void load()} />}
        <div className="grid w-full gap-3 xl:grid-cols-2">
          {(['log_level', 'log_file_level'] as const).map((key) => (
            <fieldset key={key} disabled={!draft || loading || saving} className="min-w-0 max-w-full" aria-describedby="log-output-help">
              <legend className="mb-2 text-xs font-medium text-foreground">{key === 'log_level' ? '终端日志级别' : '文件日志级别'}</legend>
              <div className="log-level-group">
                {OUTPUT_LOG_LEVELS.map((level) => (
                  <label key={level} className={`log-level-chip ${LOG_LEVEL_CLASS[level]}`}>
                    <input type="radio" name={key} value={level} checked={(draft?.[key] ?? 'INFO') === level} onChange={() => setDraft((current) => current && ({ ...current, [key]: level }))} className="peer sr-only" />
                    <span className="log-level-choice"><span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />{level}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <button type="submit" className="btn-primary min-h-9 px-3 py-1.5 text-xs" disabled={!draft || loading || saving}>{saving ? '保存中…' : '保存日志级别'}</button>
        <p className="text-xs text-muted-foreground">文件日志未启用时仅保存级别；较低级别会产生更多日志。</p>
      </form>
    </section>
  )
}
