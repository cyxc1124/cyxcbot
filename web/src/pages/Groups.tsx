import { useCallback, useEffect, useState } from 'react'
import { getMessagePolicy, updateMessagePolicy } from '../api/client'
import type { Group } from '../api/types'
import { LinkParserGroupPolicyTab } from '../components/LinkParserPolicyTabs'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { SubPageTabs } from '../components/SubPageTabs'
import { ToggleSwitch } from '../components/ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

type GroupsTab = 'message' | 'link-groups'

function isGroupEnabled(groupId: string, restrict: boolean, enabledIds: string[]): boolean {
  if (!restrict) return true
  return enabledIds.includes(groupId)
}

function computePolicyAfterToggle(
  groupId: string,
  enabled: boolean,
  groups: Group[],
  restrict: boolean,
  enabledIds: string[],
): { restrict: boolean; enabled_group_ids: string[] } {
  const allIds = groups.map((g) => g.group_id)

  if (enabled) {
    if (!restrict) {
      return { restrict: false, enabled_group_ids: [] }
    }
    const nextEnabled = [...new Set([...enabledIds, groupId])]
    if (nextEnabled.length >= allIds.length) {
      return { restrict: false, enabled_group_ids: [] }
    }
    return { restrict: true, enabled_group_ids: nextEnabled }
  }

  if (!restrict) {
    return {
      restrict: true,
      enabled_group_ids: allIds.filter((id) => id !== groupId),
    }
  }
  return {
    restrict: true,
    enabled_group_ids: enabledIds.filter((id) => id !== groupId),
  }
}

export function GroupsPage() {
  const { showToast } = useToast()
  const [tab, setTab] = useState<GroupsTab>('message')
  const [groups, setGroups] = useState<Group[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (tab !== 'message') return
    setLoading(true)
    setError('')
    try {
      const data = await getMessagePolicy()
      setGroups(data.groups)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_group_ids)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    void load()
  }, [load])

  const tabLabels: Record<GroupsTab, string> = {
    message: '群消息',
    'link-groups': '群链接解析',
  }

  const handleToggle = async (groupId: string, enabled: boolean) => {
    const next = computePolicyAfterToggle(groupId, enabled, groups, restrict, enabledIds)

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_group_ids)
    setTogglingId(groupId)

    try {
      const updated = await updateMessagePolicy(next)
      setGroups(updated.groups)
      setRestrict(updated.restrict)
      setEnabledIds(updated.enabled_group_ids)
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
      ? { restrict: false, enabled_group_ids: [] as string[] }
      : { restrict: true, enabled_group_ids: [] as string[] }

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_group_ids)
    setTogglingId('__all__')

    try {
      const updated = await updateMessagePolicy(next)
      setGroups(updated.groups)
      setRestrict(updated.restrict)
      setEnabledIds(updated.enabled_group_ids)
      showToast('success', enabled ? '已启用全部群组' : '已关闭全部群组')
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  if (tab === 'message' && loading && groups.length === 0 && !error) return <PageLoading />

  const allEnabled = !restrict
  const noneEnabled = restrict && enabledIds.length === 0
  const busy = togglingId !== null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">群组</h2>
          <p className="mt-1 text-sm text-slate-500">
            管理群消息响应范围，以及链接解析的群级开关
          </p>
        </div>
        {tab === 'message' && groups.length > 0 && (
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

      <SubPageTabs tabs={tabLabels} value={tab} onChange={setTab} />

      {tab === 'message' && (
      <>
      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="card">
        {groups.length === 0 ? (
          <p className="text-sm text-slate-500">
            {error
              ? '数据暂时无法加载'
              : '暂无可用群组，请确保机器人已连接 OneBot 并在线。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                  <th className="pb-3 pr-4 font-medium">群名称</th>
                  <th className="pb-3 pr-4 font-medium">群号</th>
                  <th className="pb-3 pr-4 font-medium">成员数</th>
                  <th className="pb-3 font-medium text-right">处理群消息</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const enabled = isGroupEnabled(group.group_id, restrict, enabledIds)
                  const rowBusy = busy && (togglingId === group.group_id || togglingId === '__all__')
                  return (
                    <tr
                      key={group.group_id}
                      className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                    >
                      <td className="py-3.5 pr-4 font-medium text-slate-900 dark:text-white">
                        {group.group_name ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">
                        {group.group_id}
                      </td>
                      <td className="py-3.5 pr-4 text-slate-600 dark:text-slate-400">
                        {group.member_count ?? '—'}
                      </td>
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
                            onChange={(checked) => void handleToggle(group.group_id, checked)}
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
      </>
      )}

      {tab === 'link-groups' && (
        <div className="card">
          <LinkParserGroupPolicyTab />
        </div>
      )}
    </div>
  )
}
