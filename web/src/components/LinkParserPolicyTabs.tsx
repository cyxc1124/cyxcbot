import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
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
  LinkParserUserPolicyItem,
} from '../api/types'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

function PolicyToggleRow({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className={`text-xs ${checked ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
        {checked ? '已启用' : '已关闭'}
      </span>
      <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  )
}

function GlobalPolicyHint({ scope }: { scope: 'group' | 'user' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">
        在下方为每个{scope === 'group' ? '群' : '好友'}单独开启视频链接或直播链接解析；两者都关闭时不解析。文案可在「消息模板」中配置。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置链接解析。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「好友消息」的好友；关闭好友消息的用户不会响应任何指令，也无法配置链接解析。
        </p>
      )}
    </div>
  )
}

export function LinkParserGroupPolicyTab() {
  const { showToast } = useToast()
  const [groups, setGroups] = useState<LinkParserGroupPolicyItem[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange('link-parser-groups')
  const [error, setError] = useState('')
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [togglingAll, setTogglingAll] = useState(false)

  const markSaving = (groupId: string, saving: boolean) => {
    setSavingIds((current) => {
      const next = new Set(current)
      if (saving) next.add(groupId)
      else next.delete(groupId)
      return next
    })
  }

  const applyGroupItem = (item: LinkParserGroupPolicyItem) => {
    setGroups((current) =>
      current.map((row) =>
        row.group_id === item.group_id
          ? { ...item, group_name: item.group_name ?? row.group_name, member_count: item.member_count ?? row.member_count }
          : row,
      ),
    )
  }

  const load = useCallback(async () => {
    try {
      const data = await getLinkParserGroupPolicies()
      setGroups(data.groups)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(load)

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const patchGroup = async (
    groupId: string,
    patch: Partial<Pick<LinkParserGroupPolicyItem, 'video_enabled' | 'live_enabled'>>,
  ) => {
    const normalizedId = String(groupId)
    const row = groups.find((item) => String(item.group_id) === normalizedId)
    if (!row) return

    const next = { ...row, ...patch }
    const payload = {
      video_enabled: Boolean(next.video_enabled),
      live_enabled: Boolean(next.live_enabled),
    }
    const active = payload.video_enabled || payload.live_enabled
    const prevRow = row

    setGroups((current) =>
      current.map((item) =>
        String(item.group_id) === normalizedId
          ? { ...item, ...payload, customized: active }
          : item,
      ),
    )

    markSaving(normalizedId, true)
    try {
      const data = await updateLinkParserGroupPolicy(normalizedId, payload)
      applyGroupItem(data.item)
    } catch (err) {
      setGroups((current) =>
        current.map((item) => (String(item.group_id) === normalizedId ? prevRow : item)),
      )
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      markSaving(normalizedId, false)
    }
  }

  const handleReset = async (groupId: string) => {
    markSaving(groupId, true)
    try {
      const data = await resetLinkParserGroupPolicy(groupId)
      applyGroupItem(data.item)
      showToast('success', '已恢复为默认（全部关闭）')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      markSaving(groupId, false)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    if (groups.length === 0) return

    const payload = { video_enabled: enabled, live_enabled: enabled }
    const prevGroups = groups
    setTogglingAll(true)
    setGroups((current) =>
      current.map((item) => ({
        ...item,
        ...payload,
        customized: enabled,
      })),
    )

    try {
      await Promise.all(
        groups.map((group) =>
          enabled
            ? updateLinkParserGroupPolicy(group.group_id, payload)
            : resetLinkParserGroupPolicy(group.group_id),
        ),
      )
      await load()
      showToast('success', enabled ? '已为全部群组启用链接解析' : '已为全部群组关闭链接解析')
    } catch (err) {
      setGroups(prevGroups)
      showToast('error', formatApiError(err, '批量保存失败'))
    } finally {
      setTogglingAll(false)
    }
  }

  const allEnabled = groups.length > 0 && groups.every((group) => group.video_enabled && group.live_enabled)
  const noneEnabled = groups.length > 0 && groups.every((group) => !group.video_enabled && !group.live_enabled)
  const busy = togglingAll || savingIds.size > 0

  if (loading && groups.length === 0 && !error) return <PageLoading />
  if (error && groups.length === 0) return <LoadErrorBanner message={error} onRetry={retryLoad} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <GlobalPolicyHint scope="group" />
        </div>
        {groups.length > 0 && (
          <div className="flex shrink-0 gap-2">
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
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          暂无已启用群消息的群组。请先在「群消息」Tab 中启用对应群组，或确保机器人已连接 OneBot。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground border-border">
                <th className="pb-3 pr-4 font-medium">群名称</th>
                <th className="pb-3 pr-4 font-medium">群号</th>
                <th className="pb-3 pr-4 font-medium">视频链接</th>
                <th className="pb-3 pr-4 font-medium">直播链接</th>
                <th className="pb-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => {
                const saving = savingIds.has(group.group_id) || togglingAll
                return (
                  <tr
                    key={group.group_id}
                    className="border-b border-border last:border-0 border-border"
                  >
                    <td className="py-3.5 pr-4 font-medium text-foreground">
                      {group.group_name ?? '—'}
                      {saving && (
                        <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">{group.group_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        checked={group.video_enabled}
                        disabled={saving}
                        onChange={(checked) => void patchGroup(group.group_id, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        checked={group.live_enabled}
                        disabled={saving}
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
  const [loading, setLoading] = useLoadingOnKeyChange('link-parser-users')
  const [error, setError] = useState('')
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [togglingAll, setTogglingAll] = useState(false)

  const markSaving = (userId: string, saving: boolean) => {
    setSavingIds((current) => {
      const next = new Set(current)
      if (saving) next.add(userId)
      else next.delete(userId)
      return next
    })
  }

  const applyUserItem = (item: LinkParserUserPolicyItem) => {
    setUsers((current) =>
      current.map((row) =>
        row.user_id === item.user_id
          ? { ...item, nickname: item.nickname ?? row.nickname, name: item.name ?? row.name }
          : row,
      ),
    )
  }

  const load = useCallback(async () => {
    try {
      const data = await getLinkParserUserPolicies()
      setUsers(data.users)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(load)

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const patchUser = async (
    userId: string,
    patch: Partial<Pick<LinkParserUserPolicyItem, 'video_enabled' | 'live_enabled'>>,
  ) => {
    const normalizedId = String(userId)
    const row = users.find((item) => String(item.user_id) === normalizedId)
    if (!row) return

    const next = { ...row, ...patch }
    const payload = {
      video_enabled: Boolean(next.video_enabled),
      live_enabled: Boolean(next.live_enabled),
    }
    const active = payload.video_enabled || payload.live_enabled
    const prevRow = row

    setUsers((current) =>
      current.map((item) =>
        String(item.user_id) === normalizedId
          ? { ...item, ...payload, customized: active }
          : item,
      ),
    )

    markSaving(normalizedId, true)
    try {
      const data = await updateLinkParserUserPolicy(normalizedId, {
        name: row.name ?? undefined,
        video_enabled: payload.video_enabled,
        live_enabled: payload.live_enabled,
      })
      applyUserItem(data.item)
    } catch (err) {
      setUsers((current) =>
        current.map((item) => (String(item.user_id) === normalizedId ? prevRow : item)),
      )
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      markSaving(normalizedId, false)
    }
  }

  const handleReset = async (userId: string) => {
    markSaving(userId, true)
    try {
      const data = await resetLinkParserUserPolicy(userId)
      applyUserItem(data.item)
      showToast('success', '已恢复为默认（全部关闭）')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      markSaving(userId, false)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    if (users.length === 0) return

    const payload = { video_enabled: enabled, live_enabled: enabled }
    const prevUsers = users
    setTogglingAll(true)
    setUsers((current) =>
      current.map((item) => ({
        ...item,
        ...payload,
        customized: enabled,
      })),
    )

    try {
      await Promise.all(
        users.map((user) =>
          enabled
            ? updateLinkParserUserPolicy(user.user_id, {
                name: user.name ?? undefined,
                ...payload,
              })
            : resetLinkParserUserPolicy(user.user_id),
        ),
      )
      await load()
      showToast('success', enabled ? '已为全部好友启用链接解析' : '已为全部好友关闭链接解析')
    } catch (err) {
      setUsers(prevUsers)
      showToast('error', formatApiError(err, '批量保存失败'))
    } finally {
      setTogglingAll(false)
    }
  }

  const allEnabled = users.length > 0 && users.every((user) => user.video_enabled && user.live_enabled)
  const noneEnabled = users.length > 0 && users.every((user) => !user.video_enabled && !user.live_enabled)
  const busy = togglingAll || savingIds.size > 0

  if (loading && users.length === 0 && !error) return <PageLoading />
  if (error && users.length === 0) return <LoadErrorBanner message={error} onRetry={retryLoad} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <GlobalPolicyHint scope="user" />
        </div>
        {users.length > 0 && (
          <div className="flex shrink-0 gap-2">
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
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {users.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          暂无已启用好友消息的好友。请先在「好友消息」Tab 中启用对应好友，或确保机器人已连接 OneBot。
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground border-border">
                <th className="pb-3 pr-4 font-medium">昵称</th>
                <th className="pb-3 pr-4 font-medium">QQ 号</th>
                <th className="pb-3 pr-4 font-medium">视频链接</th>
                <th className="pb-3 pr-4 font-medium">直播链接</th>
                <th className="pb-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const saving = savingIds.has(user.user_id) || togglingAll
                const displayName = user.nickname ?? user.name
                return (
                  <tr
                    key={user.user_id}
                    className="border-b border-border last:border-0 border-border"
                  >
                    <td className="py-3.5 pr-4 font-medium text-foreground">
                      {displayName ?? '—'}
                      {saving && (
                        <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">{user.user_id}</td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        checked={user.video_enabled}
                        disabled={saving}
                        onChange={(checked) => void patchUser(user.user_id, { video_enabled: checked })}
                      />
                    </td>
                    <td className="py-3.5 pr-4">
                      <PolicyToggleRow
                        checked={user.live_enabled}
                        disabled={saving}
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
