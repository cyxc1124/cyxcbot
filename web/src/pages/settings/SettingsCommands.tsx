import { useState, type FormEvent } from 'react'
import { patchSettings } from '../../api/client'
import type { Settings } from '../../api/types'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { COMMAND_FIELDS, type CommandField, type CommandId } from '../../constants/commandAliases'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

type CommandFormValue = { enabled: boolean; text: string }
type CommandForm = Record<CommandId, CommandFormValue>

function parseTriggers(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

function buildForm(settings: Settings | null): CommandForm {
  const result = {} as CommandForm
  for (const field of COMMAND_FIELDS) {
    const entry = settings?.command_aliases?.[field.id]
    const triggers = entry && entry.triggers.length > 0 ? entry.triggers : field.defaultTriggers
    result[field.id] = {
      enabled: entry?.enabled ?? true,
      text: triggers.join('\n'),
    }
  }
  return result
}

function CommandCard({
  field,
  value,
  disabled,
  onToggle,
  onTextChange,
  onReset,
}: {
  field: CommandField
  value: CommandFormValue
  disabled: boolean
  onToggle: (enabled: boolean) => void
  onTextChange: (text: string) => void
  onReset: () => void
}) {
  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-semibold text-foreground">{field.label}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{field.description}</p>
          {field.hint && <p className="mt-1 text-xs text-muted-foreground">{field.hint}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`text-xs ${
              value.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'
            }`}
          >
            {value.enabled ? '已启用' : '已关闭'}
          </span>
          <ToggleSwitch checked={value.enabled} disabled={disabled} onChange={onToggle} />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <label className="label" htmlFor={`command-${field.id}`}>
            触发词（每行一个）
          </label>
          <button
            type="button"
            className="text-xs text-primary hover:underline disabled:opacity-50"
            disabled={disabled}
            onClick={onReset}
          >
            恢复默认
          </button>
        </div>
        <textarea
          id={`command-${field.id}`}
          className="input mt-1 min-h-24 font-mono text-sm"
          placeholder={field.defaultTriggers.join('\n')}
          value={value.text}
          disabled={disabled}
          onChange={(e) => onTextChange(e.target.value)}
        />
      </div>
    </div>
  )
}

export function SettingsCommandsPage() {
  const { showToast } = useToast()
  const { settings, setSettings, formDisabled, load } = useSettingsForm()
  const [saving, setSaving] = useState(false)
  const [syncedSettings, setSyncedSettings] = useState(settings)
  const [form, setForm] = useState<CommandForm>(() => buildForm(settings))

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    setForm(buildForm(settings))
  }

  const updateField = (id: CommandId, patch: Partial<CommandFormValue>) => {
    setForm((current) => ({ ...current, [id]: { ...current[id], ...patch } }))
  }

  const handleReset = (field: CommandField) => {
    updateField(field.id, { enabled: true, text: field.defaultTriggers.join('\n') })
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    const payload: Settings['command_aliases'] = {}
    for (const field of COMMAND_FIELDS) {
      const value = form[field.id]
      const triggers = parseTriggers(value.text)
      if (value.enabled && triggers.length === 0) {
        showToast('error', `「${field.label}」已启用但未填写触发词`)
        return
      }
      payload[field.id] = { enabled: value.enabled, triggers }
    }

    setSaving(true)
    try {
      const updated = await patchSettings({ command_aliases: payload })
      setSettings(updated)
      setForm(buildForm(updated))
      showToast('success', '命令触发词已保存')
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <p className="text-sm text-muted-foreground">
        自定义每条命令的触发词，保存后立即生效，无需重启。关闭后该命令不再响应；已填写的触发词会保留，方便随时重新启用。
      </p>

      {COMMAND_FIELDS.map((field) => (
        <CommandCard
          key={field.id}
          field={field}
          value={form[field.id]}
          disabled={formDisabled || saving}
          onToggle={(enabled) => updateField(field.id, { enabled })}
          onTextChange={(text) => updateField(field.id, { text })}
          onReset={() => handleReset(field)}
        />
      ))}

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
