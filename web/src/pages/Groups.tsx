import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getMessagePolicy, updateMessagePolicy } from '../api/client'
import type { Group, OneBotListStatus } from '../api/types'
import { resolveOneBotListStatus } from '../utils/rosterStatus'
import { GroupSpecialTitlePolicyTab } from '../components/GroupSpecialTitlePolicyTab'
import { DouyinLinkParserGroupPolicyTab } from '../components/DouyinLinkParserPolicyTabs'
import { LinkParserGroupPolicyTab } from '../components/LinkParserPolicyTabs'
import { XLinkParserGroupPolicyTab } from '../components/XLinkParserPolicyTabs'
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

type GroupsTab =
  | 'message'
  | 'link-groups'
  | 'douyin-link-groups'
  | 'x-link-groups'
  | 'status'
  | 'special-title'

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
  const [onebotListStatus, setOnebotListStatus] = useState<OneBotListStatus>('ok')

  const load = useCallback(async () => {
    if (tab !== 'message') return
    try {
      const data = await getMessagePolicy()
      setGroups(data.groups)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_group_ids)
      setGroupListAvailable(data.group_list_available)
      setOnebotListStatus(resolveOneBotListStatus(data.onebot_list_status, data.group_list_available))
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
    status: '状态查询',
    'special-title': '群头衔',
    'link-groups': 'B 站链接',
    'douyin-link-groups': '抖音链接',
    'x-link-groups': 'X 链接',
  }

  const allGroupIds = useMemo(() => groups.map((g) => g.group_id), [groups])

  const handleToggle = async (groupId: string, enabled: boolean) => {
    const nextPolicy = computePolicyAfterToggle(
      groupId,
      enabled,
      allGroupIds,
      restrict,
      enabledIds,
      groupListAvailable,
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
      setOnebotListStatus(resolveOneBotListStatus(updated.onebot_list_status, updated.group_list_available))
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
      setOnebotListStatus(resolveOneBotListStatus(updated.onebot_list_status, updated.group_list_available))
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
            管理群消息响应范围、状态查询与群头衔权限，以及链接解析的群级开关
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
      {onebotListStatus === 'incomplete' && (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          OneBot 群列表获取失败，暂不可批量调整或修改 OneBot 会话；白名单模式下，仍可单独调整已发现的官方会话。
        </p>
      )}
      {onebotListStatus === 'offline' && (
        <p className="text-sm text-muted-foreground">
          使用官方 Bot 无需连接 OneBot。官方群通过收到群事件发现；
          {restrict ? '可单独调整下方已发现的官方群，允许名单中其他会话保持不变。' : '当前为全部启用模式，官方消息已允许处理。'}
        </p>
      )}
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="card">
        {groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {error
              ? '数据暂时无法加载'
              : onebotListStatus === 'offline'
                ? '尚未发现官方会话，请先在官方群中 @机器人后刷新。使用 OneBot 时请检查协议端连接。'
                : groupListAvailable
                ? '暂无群组数据。请连接 OneBot，或在官方群中 @机器人后刷新。'
                : '暂无群组数据。请连接 OneBot，或先在官方群中 @机器人后刷新。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground border-border">
                  <th className="pb-3 pr-4 font-medium">群名称</th>
                  <th className="pb-3 pr-4 font-medium">群号 / OpenID</th>
                  <th className="pb-3 pr-4 font-medium">成员数</th>
                  <th id="group-message-heading" className="pb-3 font-medium text-right">处理群消息</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const enabled = isItemEnabled(group.group_id, restrict, enabledIds)
                  const rowEditable = policyEditable || (restrict && group.source === 'official')
                  return (
                    <tr
                      key={group.group_id}
                      className="border-b border-border last:border-0 border-border"
                    >
                      <td id={`group-name-${group.group_id}`} className="py-3.5 pr-4 font-medium text-foreground">
                        {group.group_name ?? '—'}
                        {group.source === 'official' && <span className="ml-2 text-xs text-muted-foreground">官方</span>}
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
                            disabled={busy || !rowEditable}
                            ariaLabelledBy={`group-message-heading group-name-${group.group_id}`}
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

      {tab === 'douyin-link-groups' && (
        <div className="card">
          <DouyinLinkParserGroupPolicyTab />
        </div>
      )}

      {tab === 'x-link-groups' && (
        <div className="card">
          <XLinkParserGroupPolicyTab />
        </div>
      )}

      {tab === 'status' && <StatusCheckPolicyTab scope="group" />}

      {tab === 'special-title' && <GroupSpecialTitlePolicyTab />}
    </div>
  )
}
