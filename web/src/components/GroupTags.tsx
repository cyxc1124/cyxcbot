import type { Group } from '../api/types'

interface GroupTagsProps {
  groupIds: string[]
  groups: Group[]
  emptyText?: string
  compact?: boolean
}

function resolveGroupName(groupId: string, groups: Group[]): string {
  const found = groups.find((g) => g.group_id === groupId)
  return found?.group_name ?? groupId
}

export function GroupTags({
  groupIds,
  groups,
  emptyText = '未配置群组',
  compact = false,
}: GroupTagsProps) {
  if (groupIds.length === 0) {
    return <span className="text-xs text-slate-400">{emptyText}</span>
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {groupIds.map((groupId) => {
        const name = resolveGroupName(groupId, groups)
        const hasName = name !== groupId
        return (
          <span
            key={groupId}
            className={`inline-flex max-w-full items-center gap-1 rounded-md border border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 ${
              compact ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
            }`}
            title={hasName ? `群号 ${groupId}` : undefined}
          >
            {hasName ? (
              <>
                <span className="truncate font-medium">{name}</span>
                <span className="shrink-0 font-mono text-slate-400">{groupId}</span>
              </>
            ) : (
              <span className="font-mono">{groupId}</span>
            )}
          </span>
        )
      })}
    </div>
  )
}
