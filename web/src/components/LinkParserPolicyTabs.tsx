import { useCallback } from 'react'
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
import { useLinkParserPolicies } from '../hooks/useLinkParserPolicies'
import { LoadErrorBanner } from './LoadErrorBanner'
import { GlobalPolicyHint, LinkParserPolicyTable } from './LinkParserPolicyTable'
import { PageLoading } from './LoadingSpinner'

function mergeGroupItem(
  existing: LinkParserGroupPolicyItem,
  incoming: LinkParserGroupPolicyItem,
): LinkParserGroupPolicyItem {
  return {
    ...incoming,
    group_name: incoming.group_name ?? existing.group_name,
    member_count: incoming.member_count ?? existing.member_count,
  }
}

function mergeUserItem(
  existing: LinkParserUserPolicyItem,
  incoming: LinkParserUserPolicyItem,
): LinkParserUserPolicyItem {
  return {
    ...incoming,
    nickname: incoming.nickname ?? existing.nickname,
    name: incoming.name ?? existing.name,
  }
}

export function LinkParserGroupPolicyTab() {
  const loadGroups = useCallback(async () => {
    const data = await getLinkParserGroupPolicies()
    return data.groups
  }, [])

  const {
    items: groups,
    loading,
    error,
    retryLoad,
    savingIds,
    togglingAll,
    patchItem,
    handleReset,
    handleToggleAll,
    allEnabled,
    noneEnabled,
    busy,
  } = useLinkParserPolicies({
    loadingKey: 'link-parser-groups',
    loadItems: loadGroups,
    getItemId: (item) => item.group_id,
    mergeItem: mergeGroupItem,
    updateItem: (id, payload) => updateLinkParserGroupPolicy(id, payload),
    resetItem: resetLinkParserGroupPolicy,
    toggleAllSuccessMessage: (enabled) =>
      enabled ? '已为全部群组启用链接解析' : '已为全部群组关闭链接解析',
  })

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
        <LinkParserPolicyTable
          items={groups}
          getItemId={(group) => group.group_id}
          getDisplayName={(group) => group.group_name}
          idColumnLabel="群号"
          nameColumnLabel="群名称"
          savingIds={savingIds}
          togglingAll={togglingAll}
          onPatch={patchItem}
          onReset={handleReset}
        />
      )}
    </div>
  )
}

export function LinkParserUserPolicyTab() {
  const loadUsers = useCallback(async () => {
    const data = await getLinkParserUserPolicies()
    return data.users
  }, [])

  const {
    items: users,
    loading,
    error,
    retryLoad,
    savingIds,
    togglingAll,
    patchItem,
    handleReset,
    handleToggleAll,
    allEnabled,
    noneEnabled,
    busy,
  } = useLinkParserPolicies({
    loadingKey: 'link-parser-users',
    loadItems: loadUsers,
    getItemId: (item) => item.user_id,
    mergeItem: mergeUserItem,
    updateItem: (id, payload, row) =>
      updateLinkParserUserPolicy(id, {
        name: row.name ?? undefined,
        video_enabled: payload.video_enabled,
        live_enabled: payload.live_enabled,
        dynamic_enabled: payload.dynamic_enabled,
      }),
    resetItem: resetLinkParserUserPolicy,
    toggleAllSuccessMessage: (enabled) =>
      enabled ? '已为全部好友启用链接解析' : '已为全部好友关闭链接解析',
  })

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
        <LinkParserPolicyTable
          items={users}
          getItemId={(user) => user.user_id}
          getDisplayName={(user) => user.nickname ?? user.name}
          idColumnLabel="QQ 号"
          nameColumnLabel="昵称"
          savingIds={savingIds}
          togglingAll={togglingAll}
          onPatch={patchItem}
          onReset={handleReset}
        />
      )}
    </div>
  )
}
