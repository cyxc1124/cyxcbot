import type { Group } from '../api/types'

interface GroupSelectorProps {
  groups: Group[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  helperText?: string
}

export function GroupSelector({ groups, selected, onChange, disabled, helperText }: GroupSelectorProps) {
  const list = Array.isArray(groups) ? groups : []

  const toggle = (groupId: string) => {
    if (selected.includes(groupId)) {
      onChange(selected.filter((id) => id !== groupId))
    } else {
      onChange([...selected, groupId])
    }
  }

  if (list.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        暂无可用群组，请确保机器人已连接 OneBot 并在线。
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        {helperText ?? '可多选，消息将推送到所有已选群组'}
        {selected.length > 0 && (
          <span className="ml-1 font-medium text-brand-600 dark:text-brand-400">
            （已选 {selected.length} 个）
          </span>
        )}
      </p>
      <div className="flex flex-wrap gap-2">
        {list.map((group) => {
          const isSelected = selected.includes(group.group_id)
          const label = group.group_name ?? group.group_id
          return (
            <button
              key={group.group_id}
              type="button"
              disabled={disabled}
              onClick={() => toggle(group.group_id)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                isSelected
                  ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300'
              }`}
            >
              <span
                className={`h-4 w-4 shrink-0 rounded border ${
                  isSelected
                    ? 'border-brand-500 bg-brand-500'
                    : 'border-slate-300 dark:border-slate-500'
                }`}
              />
              <span className="truncate">{label}</span>
              {group.group_name && (
                <span className="shrink-0 font-mono text-xs opacity-60">{group.group_id}</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
