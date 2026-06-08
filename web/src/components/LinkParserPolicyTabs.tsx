import { useCallback, useEffect, useState } from 'react'
import {
  getLinkParserGroupPolicies,
  getLinkParserUserPolicies,
  resetLinkParserGroupPolicy,
  resetLinkParserUserPolicy,
  updateLinkParserGroupPolicy,
  updateLinkParserUserPolicy,
} from '../api/client'
import type {
  LinkParserGroupPolicyItem,
  LinkParserGlobalPolicy,
  LinkParserUserPolicyItem,
} from '../api/types'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

function PolicyToggleRow({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className="hidden text-xs text-slate-500 sm:inline">{label}</span>
      <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  )
}

function GlobalPolicyHint({ policy, scope }: { policy: LinkParserGlobalPolicy; scope: 'group' | 'user' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-slate-500">
        全局默认：
        {policy.enabled ? '已启用' : '已关闭'} /
        视频{policy.video_enabled ? '开' : '关'} /
        直播{policy.live_enabled ? '开' : '关'}
        {policy.private_enabled ? '' : ' / 私聊关'}
        。未单独配置的{scope === 'group' ? '群' : '用户'}将继承全局设置（在「系统设置 → 监控」中修改）。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-slate-500">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置链接解析。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-slate-500">
          列表包含好友，以及已启用「群消息」的群成员。
        </p>
      )}
    </div>
  )
}

export function LinkParserGroupPolicyTab() {
  const { showToast } = useToast()
  const [groups, setGroups] = useState<LinkParserGroupPolicyItem[]>([])
  const [globalPolicy, setGlobalPolicy] = useState<LinkParserGlobalPolicy | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getLinkParserGroupPolicies()
      setGroups(data.groups)
      setGlobalPolicy(data.global_policy)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const patchGroup = async (
    group: LinkParserGroupPolicyItem,
    patch: Partial<Pick<LinkParserGroupPolicyItem, 'enabled' | 'video_enabled' | 'live_enabled'>>,
  ) => {
    setBusyId(group.group_id)
    try {
      const data = await updateLinkParserGroupPolicy(group.group_id, {
        enabled: patch.enabled ?? group.enabled,
        video_enabled: patch.video_enabled ?? group.video_enabled,
        live_enabled: patch.live_enabled ?? group.live_enabled,
      })
      setGroups(data.groups)
      setGlobalPolicy(data.global_policy)
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusyId(null)
    }
  }

  const handleReset = async (groupId: string) => {
    setBusyId(groupId)
    try {
      const data = await resetLinkParserGroupPolicy(groupId)
      setGroups(data.groups)
      setGlobalPolicy(data.global_policy)
      showToast('success', '已恢复为全局默认')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      setBusyId(null)
    }
  }

  if (loading && groups.length === 0 && !error) return <PageLoading />
  if (error && groups.length === 0) return <LoadErrorBanner message={error} onRetry={load} />

  return (
    <div className="space-y-4">
      {globalPolicy && <GlobalPolicyHint policy={globalPolicy} scope="group" />}
      {error && <LoadErrorBanner message={error} onRetry={load} />}

      {groups.length === 0 ? (
        <p className="text-sm text-slate-500">
          暂无已启用群消息的群组。请先在「群消息」Tab 中启用对应群组，或确保机器人已连接 OneBot。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                <th className="pb-3 pr-4 font-medium">群名称</th>
                <th className="pb-3 pr-4 font-medium">群号</th>
                <th className="pb-3 pr-4 font-medium">链接解析</th>
                <th className="pb-3 pr-4 font-medium">视频</th>
                <th className="pb-3 pr-4 font-medium">直播</th>
                <th className="pb-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => {
                const busy = busyId === group.group_id
                return (
                  <tr
                    key={group.group_id}
                    className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                  >
                    <td className="py-3.5 pr-4 font-medium text-slate-900 dark:text-white">
                      {group.group_name ?? '—'}
                      {group.customized && (
                        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                          自定义
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">{group.group_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="链接解析"
                        checked={group.enabled}
                        disabled={busy}
                        onChange={(checked) => void patchGroup(group, { enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="视频"
                        checked={group.video_enabled}
                        disabled={busy || !group.enabled}
                        onChange={(checked) => void patchGroup(group, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="直播"
                        checked={group.live_enabled}
                        disabled={busy || !group.enabled}
                        onChange={(checked) => void patchGroup(group, { live_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 text-right">
                      {group.customized && (
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          disabled={busy}
                          onClick={() => void handleReset(group.group_id)}
                        >
                          恢复默认
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function LinkParserUserPolicyTab() {
  const { showToast } = useToast()
  const [users, setUsers] = useState<LinkParserUserPolicyItem[]>([])
  const [globalPolicy, setGlobalPolicy] = useState<LinkParserGlobalPolicy | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getLinkParserUserPolicies()
      setUsers(data.users)
      setGlobalPolicy(data.global_policy)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const patchUser = async (
    user: LinkParserUserPolicyItem,
    patch: Partial<
      Pick<LinkParserUserPolicyItem, 'enabled' | 'video_enabled' | 'live_enabled' | 'private_enabled'>
    >,
  ) => {
    setBusyId(user.user_id)
    try {
      const data = await updateLinkParserUserPolicy(user.user_id, {
        name: user.name ?? undefined,
        enabled: patch.enabled ?? user.enabled,
        video_enabled: patch.video_enabled ?? user.video_enabled,
        live_enabled: patch.live_enabled ?? user.live_enabled,
        private_enabled: patch.private_enabled ?? user.private_enabled,
      })
      setUsers(data.users)
      setGlobalPolicy(data.global_policy)
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusyId(null)
    }
  }

  const handleReset = async (userId: string) => {
    setBusyId(userId)
    try {
      const data = await resetLinkParserUserPolicy(userId)
      setUsers(data.users)
      setGlobalPolicy(data.global_policy)
      showToast('success', '已恢复为全局默认')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      setBusyId(null)
    }
  }

  if (loading && users.length === 0 && !error) return <PageLoading />
  if (error && users.length === 0) return <LoadErrorBanner message={error} onRetry={load} />

  return (
    <div className="space-y-4">
      {globalPolicy && <GlobalPolicyHint policy={globalPolicy} scope="user" />}
      {error && <LoadErrorBanner message={error} onRetry={load} />}

      {users.length === 0 ? (
        <p className="text-sm text-slate-500">
          暂无可用用户，请确保机器人已连接 OneBot（将拉取好友与已启用群消息的群成员）。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                <th className="pb-3 pr-4 font-medium">昵称</th>
                <th className="pb-3 pr-4 font-medium">QQ 号</th>
                <th className="pb-3 pr-4 font-medium">链接解析</th>
                <th className="pb-3 pr-4 font-medium">视频</th>
                <th className="pb-3 pr-4 font-medium">直播</th>
                <th className="pb-3 pr-4 font-medium">私聊</th>
                <th className="pb-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const busy = busyId === user.user_id
                const displayName = user.nickname ?? user.name
                return (
                  <tr
                    key={user.user_id}
                    className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                  >
                    <td className="py-3.5 pr-4 font-medium text-slate-900 dark:text-white">
                      {displayName ?? '—'}
                      {user.customized && (
                        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                          自定义
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">{user.user_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="链接解析"
                        checked={user.enabled}
                        disabled={busy}
                        onChange={(checked) => void patchUser(user, { enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="视频"
                        checked={user.video_enabled}
                        disabled={busy || !user.enabled}
                        onChange={(checked) => void patchUser(user, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="直播"
                        checked={user.live_enabled}
                        disabled={busy || !user.enabled}
                        onChange={(checked) => void patchUser(user, { live_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="私聊"
                        checked={user.private_enabled}
                        disabled={busy || !user.enabled}
                        onChange={(checked) => void patchUser(user, { private_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 text-right">
                      {user.customized && (
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          disabled={busy}
                          onClick={() => void handleReset(user.user_id)}
                        >
                          恢复默认
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
