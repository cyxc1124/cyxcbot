import { useCallback, useEffect, useState } from 'react'
import {
  getGroupStatusPolicy,
  getPrivateStatusPolicy,
  updateGroupStatusPolicy,
  updatePrivateStatusPolicy,
} from '../api/client'
import type { Friend, Group, StatusCheckDisplayOptions } from '../api/types'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

type StatusScope = 'group' | 'friend'

interface StatusCheckPolicyTabProps {
  scope: StatusScope
}

function isItemEnabled(itemId: string, restrict: boolean, enabledIds: string[]): boolean {
  if (!restrict) return true
  return enabledIds.includes(itemId)
}

function computePolicyAfterToggle(
  itemId: string,
  enabled: boolean,
  allIds: string[],
  restrict: boolean,
  enabledIds: string[],
): { restrict: boolean; enabled_ids: string[] } {
  if (enabled) {
    if (!restrict) {
      return { restrict: false, enabled_ids: [] }
    }
    const nextEnabled = [...new Set([...enabledIds, itemId])]
    if (nextEnabled.length >= allIds.length) {
      return { restrict: false, enabled_ids: [] }
    }
    return { restrict: true, enabled_ids: nextEnabled }
  }

  if (!restrict) {
    return {
      restrict: true,
      enabled_ids: allIds.filter((id) => id !== itemId),
    }
  }
  return {
    restrict: true,
    enabled_ids: enabledIds.filter((id) => id !== itemId),
  }
}

function DisplayOptionsCard({
  display,
  disabled,
  onChange,
}: {
  display: StatusCheckDisplayOptions
  disabled: boolean
  onChange: (next: StatusCheckDisplayOptions) => void
}) {
  return (
    <div className="card space-y-4">
      <div>
        <h3 className="font-semibold text-slate-900 dark:text-white">状态回复内容</h3>
        <p className="mt-1 text-sm text-slate-500">
          控制 <code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">/status</code>{' '}
          、<code className="rounded bg-slate-100 px-1 py-0.5 text-xs dark:bg-slate-800">/状态</code>{' '}
          回复中包含的信息。群组与好友共用此设置。
        </p>
      </div>
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-slate-700 dark:text-slate-300">显示详细技术信息</span>
          <ToggleSwitch
            checked={display.show_detailed}
            disabled={disabled}
            onChange={(checked) => onChange({ ...display, show_detailed: checked })}
          />
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-slate-700 dark:text-slate-300">显示运行时长</span>
          <ToggleSwitch
            checked={display.show_uptime}
            disabled={disabled}
            onChange={(checked) => onChange({ ...display, show_uptime: checked })}
          />
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-sm text-slate-700 dark:text-slate-300">显示内存使用情况</span>
          <ToggleSwitch
            checked={display.show_memory}
            disabled={disabled}
            onChange={(checked) => onChange({ ...display, show_memory: checked })}
          />
        </div>
      </div>
    </div>
  )
}

export function StatusCheckPolicyTab({ scope }: StatusCheckPolicyTabProps) {
  const { showToast } = useToast()
  const isGroup = scope === 'group'
  const [groups, setGroups] = useState<Group[]>([])
  const [friends, setFriends] = useState<Friend[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [display, setDisplay] = useState<StatusCheckDisplayOptions>({
    show_detailed: true,
    show_uptime: true,
    show_memory: true,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [savingDisplay, setSavingDisplay] = useState(false)

  const items = isGroup
    ? groups.map((g) => ({ id: g.group_id, name: g.group_name, extra: g.member_count }))
    : friends.map((f) => ({ id: f.user_id, name: f.nickname, extra: null as number | null }))

  const allIds = items.map((item) => item.id)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (isGroup) {
        const data = await getGroupStatusPolicy()
        setGroups(data.groups)
        setRestrict(data.restrict)
        setEnabledIds(data.enabled_group_ids)
        setDisplay(data.display)
      } else {
        const data = await getPrivateStatusPolicy()
        setFriends(data.users)
        setRestrict(data.restrict)
        setEnabledIds(data.enabled_user_ids)
        setDisplay(data.display)
      }
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [isGroup])

  useEffect(() => {
    void load()
  }, [load])

  const applyGroupResponse = (data: Awaited<ReturnType<typeof getGroupStatusPolicy>>) => {
    setGroups(data.groups)
    setRestrict(data.restrict)
    setEnabledIds(data.enabled_group_ids)
    setDisplay(data.display)
  }

  const applyFriendResponse = (data: Awaited<ReturnType<typeof getPrivateStatusPolicy>>) => {
    setFriends(data.users)
    setRestrict(data.restrict)
    setEnabledIds(data.enabled_user_ids)
    setDisplay(data.display)
  }

  const handleToggle = async (itemId: string, enabled: boolean) => {
    const next = computePolicyAfterToggle(itemId, enabled, allIds, restrict, enabledIds)

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_ids)
    setTogglingId(itemId)

    try {
      if (isGroup) {
        const updated = await updateGroupStatusPolicy({
          restrict: next.restrict,
          enabled_group_ids: next.enabled_ids,
        })
        applyGroupResponse(updated)
      } else {
        const updated = await updatePrivateStatusPolicy({
          restrict: next.restrict,
          enabled_user_ids: next.enabled_ids,
        })
        applyFriendResponse(updated)
      }
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    const next = enabled
      ? { restrict: false, enabled_ids: [] as string[] }
      : { restrict: true, enabled_ids: [] as string[] }

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_ids)
    setTogglingId('__all__')

    try {
      if (isGroup) {
        const updated = await updateGroupStatusPolicy({
          restrict: next.restrict,
          enabled_group_ids: next.enabled_ids,
        })
        applyGroupResponse(updated)
      } else {
        const updated = await updatePrivateStatusPolicy({
          restrict: next.restrict,
          enabled_user_ids: next.enabled_ids,
        })
        applyFriendResponse(updated)
      }
      showToast('success', enabled ? `已启用全部${isGroup ? '群组' : '好友'}` : `已关闭全部${isGroup ? '群组' : '好友'}`)
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  const handleDisplayChange = async (next: StatusCheckDisplayOptions) => {
    const prev = display
    setDisplay(next)
    setSavingDisplay(true)
    try {
      if (isGroup) {
        const updated = await updateGroupStatusPolicy({
          restrict,
          enabled_group_ids: enabledIds,
          display: next,
        })
        applyGroupResponse(updated)
      } else {
        const updated = await updatePrivateStatusPolicy({
          restrict,
          enabled_user_ids: enabledIds,
          display: next,
        })
        applyFriendResponse(updated)
      }
    } catch (err) {
      setDisplay(prev)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSavingDisplay(false)
    }
  }

  if (loading && items.length === 0 && !error) return <PageLoading />

  const allEnabled = !restrict
  const noneEnabled = restrict && enabledIds.length === 0
  const busy = togglingId !== null || savingDisplay

  return (
    <div className="space-y-6">
      <DisplayOptionsCard
        display={display}
        disabled={busy}
        onChange={(next) => void handleDisplayChange(next)}
      />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-slate-500">
          {isGroup
            ? '配置哪些群可使用 /status、/状态 查询机器人运行状态。仅显示已启用「群消息」的群；超级用户与系统设置中的额外 QQ 号不受此限制。'
            : '配置哪些好友可使用 /status、/状态 查询机器人运行状态。仅显示已启用「好友消息」的好友；超级用户与系统设置中的额外 QQ 号不受此限制。'}
        </p>
        {items.length > 0 && (
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={busy || allEnabled}
              onClick={() => void handleToggleAll(true)}
            >
              全部启用
            </button>
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={busy || noneEnabled}
              onClick={() => void handleToggleAll(false)}
            >
              全部关闭
            </button>
          </div>
        )}
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="card">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">
            {error
              ? '数据暂时无法加载'
              : isGroup
                ? '暂无已启用群消息的群组。请先在「群消息」Tab 中启用对应群组，或确保机器人已连接 OneBot。'
                : '暂无已启用好友消息的好友。请先在「好友消息」Tab 中启用对应好友，或确保机器人已连接 OneBot。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                  <th className="pb-3 pr-4 font-medium">{isGroup ? '群名称' : '昵称'}</th>
                  <th className="pb-3 pr-4 font-medium">{isGroup ? '群号' : 'QQ 号'}</th>
                  {isGroup && <th className="pb-3 pr-4 font-medium">成员数</th>}
                  <th className="pb-3 font-medium text-right">允许状态查询</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const enabled = isItemEnabled(item.id, restrict, enabledIds)
                  const rowBusy = busy && (togglingId === item.id || togglingId === '__all__')
                  return (
                    <tr
                      key={item.id}
                      className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                    >
                      <td className="py-3.5 pr-4 font-medium text-slate-900 dark:text-white">
                        {item.name ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">{item.id}</td>
                      {isGroup && (
                        <td className="py-3.5 pr-4 text-slate-600 dark:text-slate-400">
                          {item.extra ?? '—'}
                        </td>
                      )}
                      <td className="py-3.5 text-right">
                        <div className="inline-flex items-center justify-end gap-2">
                          <span
                            className={`text-xs ${enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}
                          >
                            {enabled ? '已启用' : '已关闭'}
                          </span>
                          <ToggleSwitch
                            checked={enabled}
                            disabled={rowBusy}
                            onChange={(checked) => void handleToggle(item.id, checked)}
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
