import { useMemo, useState } from 'react'
import type { Group } from '../api/types'

interface GroupSelectorProps {
  groups: Group[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  helperText?: string
}

type GroupLike = Pick<Group, 'group_id' | 'group_name'>

/** 随视口高度变化，小屏少显示、大屏多显示 */
const PANEL_HEIGHT =
  'h-[clamp(10rem,35dvh,16rem)] sm:h-[clamp(12rem,42dvh,24rem)] lg:h-[clamp(14rem,48dvh,32rem)]'

export function GroupSelector({ groups, selected, onChange, disabled, helperText }: GroupSelectorProps) {
  const [query, setQuery] = useState('')
  const list = Array.isArray(groups) ? groups : []

  const groupMap = useMemo(() => {
    const map = new Map<string, Group>()
    for (const group of list) {
      map.set(group.group_id, group)
    }
    return map
  }, [list])

  const available = useMemo(() => {
    const q = query.trim().toLowerCase()
    return list.filter((group) => {
      if (selected.includes(group.group_id)) return false
      if (!q) return true
      const name = (group.group_name ?? '').toLowerCase()
      const id = group.group_id.toLowerCase()
      return name.includes(q) || id.includes(q)
    })
  }, [list, selected, query])

  const selectedGroups = useMemo((): GroupLike[] => {
    return selected.map(
      (id) => groupMap.get(id) ?? { group_id: id, group_name: null },
    )
  }, [selected, groupMap])

  const addGroup = (groupId: string) => {
    if (disabled || selected.includes(groupId)) return
    onChange([...selected, groupId])
  }

  const removeGroup = (groupId: string) => {
    if (disabled) return
    onChange(selected.filter((id) => id !== groupId))
  }

  if (list.length === 0 && selected.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        暂无可用群组，请确保机器人已连接 OneBot 并在线。
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500">
        {helperText ?? '点击左侧群组添加到推送列表'}
        {selected.length > 0 && (
          <span className="ml-1 font-medium text-brand-600 dark:text-brand-400">
            （已选 {selected.length} 个）
          </span>
        )}
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 ${PANEL_HEIGHT}`}
        >
          <div className="border-b border-slate-200 p-2 dark:border-slate-700">
            <input
              type="search"
              className="input py-1.5 text-sm"
              placeholder="搜索群名或群号"
              value={query}
              disabled={disabled}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 dark:border-slate-800">
            <span className="text-xs font-medium text-slate-500">可选群组</span>
            <span className="text-xs text-slate-400">{available.length} 个</span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {available.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-slate-400">
                {query.trim() ? '没有匹配的群组' : '已全部添加'}
              </li>
            ) : (
              available.map((group) => (
                <li key={group.group_id}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => addGroup(group.group_id)}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-800"
                  >
                    <span className="min-w-0 flex-1 truncate text-slate-900 dark:text-white">
                      {group.group_name ?? group.group_id}
                    </span>
                    {group.group_name && (
                      <span className="shrink-0 font-mono text-xs text-slate-400">
                        {group.group_id}
                      </span>
                    )}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>

        <div
          className={`flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900 ${PANEL_HEIGHT}`}
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-700">
            <span className="text-xs font-medium text-slate-500">已选群组</span>
            <span className="text-xs text-slate-400">{selectedGroups.length} 个</span>
          </div>
          <ul className="flex-1 overflow-y-auto p-1">
            {selectedGroups.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-slate-400">
                点击左侧群组添加
              </li>
            ) : (
              selectedGroups.map((group) => (
                <li
                  key={group.group_id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-slate-900 dark:text-white">
                      {group.group_name ?? group.group_id}
                    </p>
                    {group.group_name && (
                      <p className="font-mono text-xs text-slate-400">{group.group_id}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label={`移除 ${group.group_name ?? group.group_id}`}
                    onClick={() => removeGroup(group.group_id)}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-slate-700 dark:hover:text-slate-200"
                  >
                    <span className="text-base leading-none" aria-hidden>
                      ×
                    </span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
