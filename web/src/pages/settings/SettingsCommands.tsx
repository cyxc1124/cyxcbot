import { useState, type FormEvent } from 'react'
import { patchSettings } from '../../api/client'
import type { Settings } from '../../api/types'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import {
  COMMAND_FIELDS,
  DEFAULT_EXTRA_PREFIXES,
  type CommandField,
  type CommandId,
} from '../../constants/commandAliases'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { useSettingsForm } from './SettingsContext'

type CommandFormValue = { enabled: boolean; text: string }
type CommandForm = Record<CommandId, CommandFormValue>

function parseLines(text: string): string[] {
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

function buildExtraPrefixesText(settings: Settings | null): string {
  return (settings?.command_extra_prefixes ?? DEFAULT_EXTRA_PREFIXES).join('\n')
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

function ExtraPrefixesCard({
  text,
  disabled,
  onTextChange,
  onReset,
}: {
  text: string
  disabled: boolean
  onTextChange: (text: string) => void
  onReset: () => void
}) {
  return (
    <div className="card space-y-3">
      <div>
        <h3 className="font-semibold text-foreground">习惯性前缀</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          除部署配置的 <code className="font-mono">COMMAND_START</code>{' '}
          外，额外始终生效的命令前缀，留空表示不启用任何习惯性前缀。
        </p>
      </div>
      <div>
        <div className="flex items-center justify-between">
          <label className="label" htmlFor="command-extra-prefixes">
            前缀（每行一个）
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
          id="command-extra-prefixes"
          className="input mt-1 min-h-20 font-mono text-sm"
          placeholder={DEFAULT_EXTRA_PREFIXES.join('\n')}
          value={text}
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
  const [extraPrefixesText, setExtraPrefixesText] = useState(() =>
    buildExtraPrefixesText(settings),
  )

  if (settings !== syncedSettings) {
    setSyncedSettings(settings)
    setForm(buildForm(settings))
    setExtraPrefixesText(buildExtraPrefixesText(settings))
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
      const triggers = parseLines(value.text)
      if (value.enabled && triggers.length === 0) {
        showToast('error', `「${field.label}」已启用但未填写触发词`)
        return
      }
      payload[field.id] = { enabled: value.enabled, triggers }
    }
    const extraPrefixes = parseLines(extraPrefixesText)

    setSaving(true)
    try {
      const updated = await patchSettings({
        command_aliases: payload,
        command_extra_prefixes: extraPrefixes,
      })
      setSettings(updated)
      setForm(buildForm(updated))
      setExtraPrefixesText(buildExtraPrefixesText(updated))
      showToast('success', '命令设置已保存')
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

      {settings && settings.command_prefixes.length > 0 && (
        <p className="text-xs text-muted-foreground">
          当前生效的命令前缀：
          <code className="mx-1 rounded bg-secondary px-1.5 py-0.5 font-mono">
            {settings.command_prefixes.join(' ')}
          </code>
          ，所有命令统一遵循此前缀集合。除「动态图片提取」「群头衔设置」必须带前缀外，其余命令也支持直接发送触发词或 @机器人 触发，无需前缀。前缀来自部署的{' '}
          <code className="font-mono">COMMAND_START</code>{' '}
          环境变量（改需重启）与下方「习惯性前缀」（改后立即生效）。
        </p>
      )}

      <ExtraPrefixesCard
        text={extraPrefixesText}
        disabled={formDisabled || saving}
        onTextChange={setExtraPrefixesText}
        onReset={() => setExtraPrefixesText(DEFAULT_EXTRA_PREFIXES.join('\n'))}
      />

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
