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
        。未单独配置的{scope === 'group' ? '群' : '用户'}将继承全局设置（在「系统设置 → 监控」中修改）。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-slate-500">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置链接解析。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-slate-500">
          仅显示已启用「私聊消息」的好友；关闭私聊消息的用户不会响应任何指令，也无法配置链接解析。
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
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())

  const markSaving = (groupId: string, saving: boolean) => {
    setSavingIds((current) => {
      const next = new Set(current)
      if (saving) next.add(groupId)
      else next.delete(groupId)
      return next
    })
  }

  const applyGroupItem = (item: LinkParserGroupPolicyItem, policy: LinkParserGlobalPolicy) => {
    setGroups((current) =>
      current.map((row) =>
        row.group_id === item.group_id
          ? { ...item, group_name: item.group_name ?? row.group_name, member_count: item.member_count ?? row.member_count }
          : row,
      ),
    )
    setGlobalPolicy(policy)
  }

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
    groupId: string,
    patch: Partial<Pick<LinkParserGroupPolicyItem, 'enabled' | 'video_enabled' | 'live_enabled'>>,
  ) => {
    let payload: Pick<LinkParserGroupPolicyItem, 'enabled' | 'video_enabled' | 'live_enabled'> | null = null

    setGroups((current) =>
      current.map((row) => {
        if (row.group_id !== groupId) return row
        const next = { ...row, ...patch, customized: true }
        payload = {
          enabled: next.enabled,
          video_enabled: next.video_enabled,
          live_enabled: next.live_enabled,
        }
        return next
      }),
    )

    if (!payload) return

    markSaving(groupId, true)
    try {
      const data = await updateLinkParserGroupPolicy(groupId, payload)
      applyGroupItem(data.item, data.global_policy)
    } catch (err) {
      void load()
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      markSaving(groupId, false)
    }
  }

  const handleReset = async (groupId: string) => {
    markSaving(groupId, true)
    try {
      const data = await resetLinkParserGroupPolicy(groupId)
      applyGroupItem(data.item, data.global_policy)
      showToast('success', '已恢复为全局默认')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      markSaving(groupId, false)
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
                const saving = savingIds.has(group.group_id)
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
                      {saving && (
                        <span className="ml-2 text-[10px] text-slate-400">保存中…</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">{group.group_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="链接解析"
                        checked={group.enabled}
                        disabled={false}
                        onChange={(checked) => void patchGroup(group.group_id, { enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="视频"
                        checked={group.video_enabled}
                        disabled={false}
                        onChange={(checked) => void patchGroup(group.group_id, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="直播"
                        checked={group.live_enabled}
                        disabled={false}
                        onChange={(checked) => void patchGroup(group.group_id, { live_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 text-right">
                      {group.customized && (
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          disabled={saving}
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
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())

  const markSaving = (userId: string, saving: boolean) => {
    setSavingIds((current) => {
      const next = new Set(current)
      if (saving) next.add(userId)
      else next.delete(userId)
      return next
    })
  }

  const applyUserItem = (item: LinkParserUserPolicyItem, policy: LinkParserGlobalPolicy) => {
    setUsers((current) =>
      current.map((row) =>
        row.user_id === item.user_id
          ? { ...item, nickname: item.nickname ?? row.nickname, name: item.name ?? row.name }
          : row,
      ),
    )
    setGlobalPolicy(policy)
  }

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
    userId: string,
    patch: Partial<Pick<LinkParserUserPolicyItem, 'enabled' | 'video_enabled' | 'live_enabled'>>,
  ) => {
    let saved:
      | {
          enabled: boolean
          video_enabled: boolean
          live_enabled: boolean
        }
      | undefined
    let note: string | null = null

    setUsers((current) =>
      current.map((row) => {
        if (row.user_id !== userId) return row
        const next = { ...row, ...patch, customized: true }
        note = row.name
        saved = {
          enabled: next.enabled,
          video_enabled: next.video_enabled,
          live_enabled: next.live_enabled,
        }
        return next
      }),
    )

    if (!saved) return

    markSaving(userId, true)
    try {
      const data = await updateLinkParserUserPolicy(userId, {
        name: note ?? undefined,
        enabled: saved.enabled,
        video_enabled: saved.video_enabled,
        live_enabled: saved.live_enabled,
      })
      applyUserItem(data.item, data.global_policy)
    } catch (err) {
      void load()
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      markSaving(userId, false)
    }
  }

  const handleReset = async (userId: string) => {
    markSaving(userId, true)
    try {
      const data = await resetLinkParserUserPolicy(userId)
      applyUserItem(data.item, data.global_policy)
      showToast('success', '已恢复为全局默认')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      markSaving(userId, false)
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
          暂无已启用私聊消息的好友。请先在「私聊消息」Tab 中启用对应好友，或确保机器人已连接 OneBot。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                <th className="pb-3 pr-4 font-medium">昵称</th>
                <th className="pb-3 pr-4 font-medium">QQ 号</th>
                <th className="pb-3 pr-4 font-medium">链接解析</th>
                <th className="pb-3 pr-4 font-medium">视频</th>
                <th className="pb-3 pr-4 font-medium">直播</th>
                <th className="pb-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const saving = savingIds.has(user.user_id)
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
                      {saving && (
                        <span className="ml-2 text-[10px] text-slate-400">保存中…</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-slate-500">{user.user_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="链接解析"
                        checked={user.enabled}
                        disabled={false}
                        onChange={(checked) => void patchUser(user.user_id, { enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="视频"
                        checked={user.video_enabled}
                        disabled={false}
                        onChange={(checked) => void patchUser(user.user_id, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        label="直播"
                        checked={user.live_enabled}
                        disabled={false}
                        onChange={(checked) => void patchUser(user.user_id, { live_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 text-right">
                      {user.customized && (
                        <button
                          type="button"
                          className="btn-secondary text-xs"
                          disabled={saving}
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
