import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getMessagePolicy, updateMessagePolicy } from '../api/client'
import type { Group } from '../api/types'
import { GroupSpecialTitlePolicyTab } from '../components/GroupSpecialTitlePolicyTab'
import { LinkParserGroupPolicyTab } from '../components/LinkParserPolicyTabs'
import { RustRconGroupPolicyTab } from '../components/RustRconPolicyTabs'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { SubPageTabs } from '../components/SubPageTabs'
import { StatusCheckPolicyTab } from '../components/StatusCheckPolicyTab'
import { ToggleSwitch } from '../components/ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import {
  computePolicyAfterToggle,
  computeToggleAllPolicy,
  isItemEnabled,
} from '../utils/restrictPolicy'

type GroupsTab = 'message' | 'link-groups' | 'rcon-groups' | 'status' | 'special-title'

export function GroupsPage() {
  const { showToast } = useToast()
  const [tab, setTab] = useState<GroupsTab>('message')
  const [groups, setGroups] = useState<Group[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange(tab)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [groupListAvailable, setGroupListAvailable] = useState(true)

  const load = useCallback(async () => {
    if (tab !== 'message') return
    try {
      const data = await getMessagePolicy()
      setGroups(data.groups)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_group_ids)
      setGroupListAvailable(data.group_list_available)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [tab, setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  const tabLabels: Record<GroupsTab, string> = {
    message: '群消息',
    'link-groups': '群链接解析',
    status: '状态查询',
    'special-title': '群头衔',
    'rcon-groups': '群 RCON',
  }

  const allGroupIds = useMemo(() => groups.map((g) => g.group_id), [groups])

  const handleToggle = async (groupId: string, enabled: boolean) => {
    const nextPolicy = computePolicyAfterToggle(
      groupId,
      enabled,
      allGroupIds,
      restrict,
      enabledIds,
    )
    const next = {
      restrict: nextPolicy.restrict,
      enabled_group_ids: nextPolicy.enabled_ids,
    }

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
      setGroupListAvailable(updated.group_list_available)
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    const nextPolicy = computeToggleAllPolicy(enabled)
    const next = {
      restrict: nextPolicy.restrict,
      enabled_group_ids: nextPolicy.enabled_ids,
    }

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
      setGroupListAvailable(updated.group_list_available)
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
  const policyEditable = groupListAvailable

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">群组</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            管理群消息响应范围、Rust RCON、状态查询与群头衔权限，以及链接解析的群级开关
          </p>
        </div>
        {tab === 'message' && groups.length > 0 && (
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={busy || !policyEditable || allEnabled}
              onClick={() => void handleToggleAll(true)}
            >
              全部启用
            </button>
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={busy || !policyEditable || noneEnabled}
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
      {!groupListAvailable && groups.length > 0 && (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          群列表尚未完整同步（例如部分机器人离线），当前展示可能不完整，暂不可修改群消息开关；待连接恢复后再调整。
        </p>
      )}
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="card">
        {groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {error
              ? '数据暂时无法加载'
              : groupListAvailable
                ? '暂无可用群组，请确保机器人已连接 OneBot 并在线。'
                : '暂无群组数据。请确保机器人已连接 OneBot，或等待群列表同步完成。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground border-border">
                  <th className="pb-3 pr-4 font-medium">群名称</th>
                  <th className="pb-3 pr-4 font-medium">群号</th>
                  <th className="pb-3 pr-4 font-medium">成员数</th>
                  <th className="pb-3 font-medium text-right">处理群消息</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const enabled = isItemEnabled(group.group_id, restrict, enabledIds)
                  const rowBusy = busy && (togglingId === group.group_id || togglingId === '__all__')
                  return (
                    <tr
                      key={group.group_id}
                      className="border-b border-border last:border-0 border-border"
                    >
                      <td className="py-3.5 pr-4 font-medium text-foreground">
                        {group.group_name ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                        {group.group_id}
                      </td>
                      <td className="py-3.5 pr-4 text-muted-foreground">
                        {group.member_count ?? '—'}
                      </td>
                      <td className="py-3.5 text-right">
                        <div className="inline-flex items-center justify-end gap-2">
                          <span
                            className={`text-xs ${enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
                          >
                            {enabled ? '已启用' : '已关闭'}
                          </span>
                          <ToggleSwitch
                            checked={enabled}
                            disabled={rowBusy || !policyEditable}
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

      {tab === 'status' && <StatusCheckPolicyTab scope="group" />}

      {tab === 'special-title' && <GroupSpecialTitlePolicyTab />}

      {tab === 'rcon-groups' && (
        <div className="card">
          <RustRconGroupPolicyTab />
        </div>
      )}
    </div>
  )
}
