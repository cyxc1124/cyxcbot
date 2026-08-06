import { useCallback, useState } from 'react'
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
  const [groupListAvailable, setGroupListAvailable] = useState(true)

  const loadGroups = useCallback(async () => {
    const data = await getLinkParserGroupPolicies()
    setGroupListAvailable(data.group_list_available)
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

  const policyEditable = groupListAvailable

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
      {!groupListAvailable && groups.length > 0 && (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          群列表尚未完整同步（例如部分机器人离线），当前展示可能不完整，暂不可修改链接解析开关；待连接恢复后再调整。
        </p>
      )}
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {groupListAvailable
            ? '暂无已启用群消息的群组。请先在「群消息」Tab 中启用对应群组，或确保机器人已连接 OneBot。'
            : '暂无群组数据。请确保机器人已连接 OneBot，或等待群列表同步完成。'}
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
          editable={policyEditable}
          onPatch={patchItem}
          onReset={handleReset}
        />
      )}
    </div>
  )
}

export function LinkParserUserPolicyTab() {
  const [friendListAvailable, setFriendListAvailable] = useState(true)

  const loadUsers = useCallback(async () => {
    const data = await getLinkParserUserPolicies()
    setFriendListAvailable(data.friend_list_available)
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
        send_video_enabled: payload.send_video_enabled,
      }),
    resetItem: resetLinkParserUserPolicy,
    toggleAllSuccessMessage: (enabled) =>
      enabled ? '已为全部好友启用链接解析' : '已为全部好友关闭链接解析',
  })

  const policyEditable = friendListAvailable

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
      {!friendListAvailable && users.length > 0 && (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          好友列表尚未完整同步（例如部分机器人离线），当前展示可能不完整，暂不可修改链接解析开关；待连接恢复后再调整。
        </p>
      )}
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      {users.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {friendListAvailable
            ? '暂无已启用好友消息的好友。请先在「好友消息」Tab 中启用对应好友，或确保机器人已连接 OneBot。'
            : '暂无好友数据。请确保机器人已连接 OneBot，或等待好友列表同步完成。'}
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
          editable={policyEditable}
          onPatch={patchItem}
          onReset={handleReset}
        />
      )}
    </div>
  )
}
