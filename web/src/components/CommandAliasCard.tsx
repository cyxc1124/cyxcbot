import { ToggleSwitch } from './ToggleSwitch'
import type { CommandField } from '../constants/commandAliases'
import type { CommandFormValue } from '../pages/settings/commandsForm'

export function CommandAliasCard({
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
