import { useCallback, useMemo, useState } from 'react'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getPrivateMessagePolicy, updatePrivateMessagePolicy } from '../api/client'
import type { Friend } from '../api/types'
import { LinkParserUserPolicyTab } from '../components/LinkParserPolicyTabs'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { SubPageTabs } from '../components/SubPageTabs'
import { StatusCheckPolicyTab } from '../components/StatusCheckPolicyTab'
import { ToggleSwitch } from '../components/ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

type PrivateTab = 'message' | 'link-users' | 'status'

function isUserEnabled(userId: string, restrict: boolean, enabledIds: string[]): boolean {
  if (!restrict) return true
  return enabledIds.includes(userId)
}

function computePolicyAfterToggle(
  userId: string,
  enabled: boolean,
  users: Friend[],
  restrict: boolean,
  enabledIds: string[],
): { restrict: boolean; enabled_user_ids: string[] } {
  const allIds = users.map((u) => u.user_id)

  if (enabled) {
    if (!restrict) {
      return { restrict: false, enabled_user_ids: [] }
    }
    const nextEnabled = [...new Set([...enabledIds, userId])]
    if (nextEnabled.length >= allIds.length) {
      return { restrict: false, enabled_user_ids: [] }
    }
    return { restrict: true, enabled_user_ids: nextEnabled }
  }

  if (!restrict) {
    return {
      restrict: true,
      enabled_user_ids: allIds.filter((id) => id !== userId),
    }
  }
  return {
    restrict: true,
    enabled_user_ids: enabledIds.filter((id) => id !== userId),
  }
}

export function PrivatePage() {
  const { showToast } = useToast()
  const [tab, setTab] = useState<PrivateTab>('message')
  const [users, setUsers] = useState<Friend[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [trackedTab, setTrackedTab] = useState(tab)

  if (tab !== trackedTab) {
    setTrackedTab(tab)
    if (tab === 'message') setLoading(true)
  }

  const load = useCallback(async () => {
    if (tab !== 'message') return
    try {
      const data = await getPrivateMessagePolicy()
      setUsers(data.users)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_user_ids)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [tab])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load])

  useMountAsync(load)

  const tabLabels: Record<PrivateTab, string> = {
    message: '好友消息',
    'link-users': '好友链接解析',
    status: '状态查询',
  }

  const handleToggle = async (userId: string, enabled: boolean) => {
    const next = computePolicyAfterToggle(userId, enabled, users, restrict, enabledIds)

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_user_ids)
    setTogglingId(userId)

    try {
      const updated = await updatePrivateMessagePolicy(next)
      setUsers(updated.users)
      setRestrict(updated.restrict)
      setEnabledIds(updated.enabled_user_ids)
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
      ? { restrict: false, enabled_user_ids: [] as string[] }
      : { restrict: true, enabled_user_ids: [] as string[] }

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_user_ids)
    setTogglingId('__all__')

    try {
      const updated = await updatePrivateMessagePolicy(next)
      setUsers(updated.users)
      setRestrict(updated.restrict)
      setEnabledIds(updated.enabled_user_ids)
      showToast('success', enabled ? '已启用全部好友' : '已关闭全部好友')
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  if (tab === 'message' && loading && users.length === 0 && !error) return <PageLoading />

  const allEnabled = !restrict
  const noneEnabled = restrict && enabledIds.length === 0
  const busy = togglingId !== null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">好友</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            管理好友消息响应范围、状态查询权限，以及链接解析的用户级开关
          </p>
        </div>
        {tab === 'message' && users.length > 0 && (
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
          {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

          <div className="card">
            {users.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {error
                  ? '数据暂时无法加载'
                  : '暂无好友数据，请确保机器人已连接 OneBot 且协议端支持 get_friend_list。'}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[480px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground border-border">
                      <th className="pb-3 pr-4 font-medium">昵称</th>
                      <th className="pb-3 pr-4 font-medium">QQ 号</th>
                      <th className="pb-3 font-medium text-right">处理好友消息</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => {
                      const enabled = isUserEnabled(user.user_id, restrict, enabledIds)
                      const rowBusy = busy && (togglingId === user.user_id || togglingId === '__all__')
                      return (
                        <tr
                          key={user.user_id}
                          className="border-b border-border last:border-0 border-border"
                        >
                          <td className="py-3.5 pr-4 font-medium text-foreground">
                            {user.nickname ?? '—'}
                          </td>
                          <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                            {user.user_id}
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
                                disabled={rowBusy}
                                onChange={(checked) => void handleToggle(user.user_id, checked)}
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

      {tab === 'link-users' && (
        <div className="card">
          <LinkParserUserPolicyTab />
        </div>
      )}

      {tab === 'status' && <StatusCheckPolicyTab scope="friend" />}
    </div>
  )
}
