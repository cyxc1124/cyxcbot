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
    return <span className="text-xs text-muted-foreground">{emptyText}</span>
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {groupIds.map((groupId) => {
        const name = resolveGroupName(groupId, groups)
        const hasName = name !== groupId
        return (
          <span
            key={groupId}
            className={`inline-flex max-w-full items-center gap-1 rounded-md border border-border bg-muted text-foreground border-input bg-secondary text-foreground ${
              compact ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
            }`}
            title={hasName ? `群号 ${groupId}` : undefined}
          >
            {hasName ? (
              <>
                <span className="truncate font-medium">{name}</span>
                <span className="shrink-0 font-mono text-muted-foreground">{groupId}</span>
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
