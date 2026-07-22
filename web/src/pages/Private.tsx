import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getPrivateMessagePolicy, updatePrivateMessagePolicy } from '../api/client'
import type { Friend } from '../api/types'
import { LinkParserUserPolicyTab } from '../components/LinkParserPolicyTabs'
import { RustRconUserPolicyTab } from '../components/RustRconPolicyTabs'
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

type PrivateTab = 'message' | 'link-users' | 'rcon-users' | 'status'

export function PrivatePage() {
  const { showToast } = useToast()
  const [tab, setTab] = useState<PrivateTab>('message')
  const [users, setUsers] = useState<Friend[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange(tab)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [friendListAvailable, setFriendListAvailable] = useState(true)

  const load = useCallback(async () => {
    if (tab !== 'message') return
    try {
      const data = await getPrivateMessagePolicy()
      setUsers(data.users)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_user_ids)
      setFriendListAvailable(data.friend_list_available)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [tab, setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  const tabLabels: Record<PrivateTab, string> = {
    message: '好友消息',
    'link-users': '好友链接解析',
    status: '状态查询',
    'rcon-users': '好友 RCON',
  }

  const allUserIds = useMemo(() => users.map((u) => u.user_id), [users])

  const handleToggle = async (userId: string, enabled: boolean) => {
    const nextPolicy = computePolicyAfterToggle(
      userId,
      enabled,
      allUserIds,
      restrict,
      enabledIds,
    )
    const next = {
      restrict: nextPolicy.restrict,
      enabled_user_ids: nextPolicy.enabled_ids,
    }

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
      setFriendListAvailable(updated.friend_list_available)
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
      enabled_user_ids: nextPolicy.enabled_ids,
    }

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
      setFriendListAvailable(updated.friend_list_available)
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
  const policyEditable = friendListAvailable

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">好友</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            管理好友消息响应范围、Rust RCON、状态查询权限，以及链接解析的用户级开关
          </p>
        </div>
        {tab === 'message' && users.length > 0 && (
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
          {!friendListAvailable && users.length > 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-300">
              好友列表尚未完整同步（例如部分机器人离线），当前展示可能不完整，暂不可修改好友消息开关；待连接恢复后再调整。
            </p>
          )}
          {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

          <div className="card">
            {users.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {error
                  ? '数据暂时无法加载'
                  : friendListAvailable
                    ? '暂无好友数据，请确保机器人已连接 OneBot 且协议端支持 get_friend_list。'
                    : '暂无好友数据。请确保机器人已连接 OneBot，或等待好友列表同步完成。'}
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
                      const enabled = isItemEnabled(user.user_id, restrict, enabledIds)
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
                                disabled={rowBusy || !policyEditable}
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

      {tab === 'rcon-users' && (
        <div className="card">
          <RustRconUserPolicyTab />
        </div>
      )}
    </div>
  )
}
