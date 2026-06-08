import { useSettingsForm } from './SettingsContext'

export function SettingsDataPage() {
  const { settings, setSettings, formDisabled, saving, handleSubmit } = useSettingsForm()

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">数据保留</h3>
        <p className="text-sm text-muted-foreground">超出保留天数的记录将在清理任务中自动删除</p>
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
              value={settings?.audit_log_retention_days ?? ''}
              disabled={formDisabled}
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
              value={settings?.event_retention_days ?? ''}
              disabled={formDisabled}
              onChange={(e) =>
                setSettings((s) =>
                  s ? { ...s, event_retention_days: Number(e.target.value) } : s,
                )
              }
            />
          </div>
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
