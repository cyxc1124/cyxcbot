import type { Friend, Group } from '../api/types'
import { formatDateTime } from '../utils/format'
import { ToggleSwitch } from './ToggleSwitch'
import {
  getTargetDisplayName,
  getTargetId,
  type SubscriptionTarget,
  type TargetType,
} from './targetMapping/types'

interface TargetDetailProps {
  target: SubscriptionTarget
  type: TargetType
  targetLabel: string
  groups: Group[]
  friends: Friend[]
  rowBusy: boolean
  onClearSelection: () => void
  onToggleEnabled: (target: SubscriptionTarget, enabled: boolean) => void
  onToggleAtAll: (target: SubscriptionTarget, atAll: boolean) => void
  onEdit: (target: SubscriptionTarget) => void
  onDelete: (id: number) => void
}

export function TargetDetail({
  target,
  type,
  targetLabel,
  groups,
  friends,
  rowBusy,
  onClearSelection,
  onToggleEnabled,
  onToggleAtAll,
  onEdit,
  onDelete,
}: TargetDetailProps) {
  const targetId = getTargetId(target, type)
  const displayName = getTargetDisplayName(target, type, targetLabel)

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4 border-border">
        <div className="min-w-0 flex-1">
          <button
            type="button"
            className="mb-2 text-sm text-primary hover:underline"
            onClick={onClearSelection}
          >
            ← 返回列表
          </button>
          <h3 className="truncate text-lg font-semibold text-foreground">{displayName}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="badge-neutral font-mono text-xs">{targetId}</span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            创建于 {formatDateTime(target.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-4">
          <div className="inline-flex items-center gap-2">
            <span
              className={`text-xs ${target.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
            >
              {target.enabled ? '已启用' : '已禁用'}
            </span>
            <ToggleSwitch
              checked={target.enabled}
              disabled={rowBusy}
              onChange={(checked) => void onToggleEnabled(target, checked)}
            />
          </div>
          <div className="inline-flex items-center gap-2">
            <span
              className={`text-xs ${target.at_all ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
            >
              {target.at_all ? '@全体' : '不@全体'}
            </span>
            <ToggleSwitch
              checked={target.at_all}
              disabled={rowBusy}
              onChange={(checked) => void onToggleAtAll(target, checked)}
            />
          </div>
          <button
            type="button"
            className="btn-secondary text-sm"
            disabled={rowBusy}
            onClick={() => onEdit(target)}
          >
            编辑
          </button>
          <button
            type="button"
            className="btn-secondary text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            disabled={rowBusy}
            onClick={() => void onDelete(target.id)}
          >
            删除
          </button>
        </div>
      </div>

      <div className="flex-1 space-y-6 pt-6">
        <div>
          <h4 className="mb-3 text-sm font-medium text-foreground">
            推送群组
            <span className="ml-2 font-normal text-muted-foreground">
              （{target.group_ids.length} 个）
            </span>
          </h4>
          {target.group_ids.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚未配置推送群组</p>
          ) : (
            <ul className="space-y-2">
              {target.group_ids.map((groupId) => {
                const group = groups.find((g) => g.group_id === groupId)
                const name = group?.group_name ?? groupId
                const hasName = group?.group_name
                return (
                  <li
                    key={groupId}
                    className="flex items-center justify-between rounded-lg border border-border px-4 py-3 border-border"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">
                        {hasName ? name : `群 ${groupId}`}
                      </p>
                      {hasName && (
                        <p className="mt-0.5 font-mono text-xs text-muted-foreground">{groupId}</p>
                      )}
                    </div>
                    {group?.member_count != null && (
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {group.member_count} 人
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div>
          <h4 className="mb-3 text-sm font-medium text-foreground">
            推送好友
            <span className="ml-2 font-normal text-muted-foreground">
              （{target.user_ids.length} 个）
            </span>
          </h4>
          {target.user_ids.length === 0 ? (
            <p className="text-sm text-muted-foreground">尚未配置推送好友</p>
          ) : (
            <ul className="space-y-2">
              {target.user_ids.map((userId) => {
                const friend = friends.find((f) => f.user_id === userId)
                const name = friend?.nickname ?? userId
                const hasName = friend?.nickname
                return (
                  <li
                    key={userId}
                    className="flex items-center justify-between rounded-lg border border-border px-4 py-3 border-border"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">
                        {hasName ? name : `QQ ${userId}`}
                      </p>
                      {hasName && (
                        <p className="mt-0.5 font-mono text-xs text-muted-foreground">{userId}</p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
