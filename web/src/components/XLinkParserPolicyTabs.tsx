import { useCallback, useState } from 'react'
import {
  getXLinkParserGroupPolicies,
  getXLinkParserUserPolicies,
  resetXLinkParserGroupPolicy,
  resetXLinkParserUserPolicy,
  updateXLinkParserGroupPolicy,
  updateXLinkParserUserPolicy,
} from '../api/client'
import type {
  OneBotListStatus,
  XLinkParserGroupPolicyItem,
  XLinkParserUserPolicyItem,
} from '../api/types'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { formatApiError } from '../utils/apiError'
import { resolveOneBotListStatus } from '../utils/rosterStatus'
import { useToast } from '../contexts/ToastContext'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'

function Hint({ scope }: { scope: 'group' | 'user' }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">
        在下方为每个{scope === 'group' ? '群' : '好友'}单独开启 X 链接解析；关闭时不解析。
        需先在「设置 → X 账号」配置 Bearer Token。
      </p>
      {scope === 'group' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「群消息」的群；关闭群消息的群不会响应任何消息，也无法配置。
        </p>
      )}
      {scope === 'user' && (
        <p className="text-sm text-muted-foreground">
          仅显示已启用「好友消息」的好友；关闭好友消息的用户不会响应任何指令，也无法配置。
        </p>
      )}
    </div>
  )
}

export function XLinkParserGroupPolicyTab() {
  const { showToast } = useToast()
  const [items, setItems] = useState<XLinkParserGroupPolicyItem[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange('x-link-groups')
  const [error, setError] = useState('')
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [listAvailable, setListAvailable] = useState(true)
  const [listStatus, setListStatus] = useState<OneBotListStatus>('ok')

  const load = useCallback(async () => {
    try {
      const data = await getXLinkParserGroupPolicies()
      setItems(data.groups)
      setListAvailable(data.group_list_available)
      setListStatus(resolveOneBotListStatus(data.onebot_list_status, data.group_list_available))
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(load)
  const retryLoad = createRetryHandler(load, setLoading)

  const handleToggle = async (groupId: string, enabled: boolean) => {
    const prev = items
    setItems((current) =>
      current.map((row) =>
        row.group_id === groupId ? { ...row, enabled, customized: enabled } : row,
      ),
    )
    setSavingIds((s) => new Set(s).add(groupId))
    try {
      const data = enabled
        ? await updateXLinkParserGroupPolicy(groupId, { enabled: true })
        : await resetXLinkParserGroupPolicy(groupId)
      setItems((current) =>
        current.map((row) => (row.group_id === groupId ? data.item : row)),
      )
    } catch (err) {
      setItems(prev)
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSavingIds((s) => {
        const next = new Set(s)
        next.delete(groupId)
        return next
      })
    }
  }

  if (loading && items.length === 0 && !error) return <PageLoading />

  return (
    <div className="space-y-4">
      <Hint scope="group" />
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}
      {listStatus === 'offline' && !error && (
        <p className="text-sm text-muted-foreground">
          当前未连接 OneBot；已缓存的官方 QQ Bot 群可直接配置。
        </p>
      )}
      {listStatus === 'incomplete' && !error && (
        <p className="text-sm text-amber-600 dark:text-amber-400">
          OneBot 群列表同步不完整，数字 QQ 群暂时只读；官方 QQ Bot 群仍可配置。
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="pb-3 pr-4 font-medium">群名称</th>
              <th className="pb-3 pr-4 font-medium">群号 / OpenID</th>
              <th className="pb-3 font-medium">X 链接</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const saving = savingIds.has(item.group_id)
              return (
                <tr key={item.group_id} className="border-b border-border last:border-0">
                  <td className="py-3.5 pr-4 font-medium text-foreground">
                    {item.group_name ?? '—'}
                    {item.source === 'official' && (
                      <span className="ml-2 text-xs text-muted-foreground">官方 QQ Bot</span>
                    )}
                    {saving && (
                      <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                    )}
                  </td>
                  <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                    {item.group_id}
                  </td>
                  <td className="py-3.5">
                    <div className="inline-flex items-center gap-2">
                      <span
                        className={`text-xs ${item.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
                      >
                        {item.enabled ? '已启用' : '已关闭'}
                      </span>
                      <ToggleSwitch
                        checked={item.enabled}
                        disabled={saving || !(item.editable ?? listAvailable)}
                        onChange={(checked) => void handleToggle(item.group_id, checked)}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {items.length === 0 && !error && (
          <p className="py-6 text-sm text-muted-foreground">暂无可配置的群</p>
        )}
      </div>
    </div>
  )
}

export function XLinkParserUserPolicyTab() {
  const { showToast } = useToast()
  const [items, setItems] = useState<XLinkParserUserPolicyItem[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange('x-link-users')
  const [error, setError] = useState('')
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [listAvailable, setListAvailable] = useState(true)
  const [listStatus, setListStatus] = useState<OneBotListStatus>('ok')

  const load = useCallback(async () => {
    try {
      const data = await getXLinkParserUserPolicies()
      setItems(data.users)
      setListAvailable(data.friend_list_available)
      setListStatus(resolveOneBotListStatus(data.onebot_list_status, data.friend_list_available))
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  useMountAsync(load)
  const retryLoad = createRetryHandler(load, setLoading)

  const handleToggle = async (userId: string, enabled: boolean) => {
    const prev = items
    setItems((current) =>
      current.map((row) =>
        row.user_id === userId ? { ...row, enabled, customized: enabled } : row,
      ),
    )
    setSavingIds((s) => new Set(s).add(userId))
    try {
      const data = enabled
        ? await updateXLinkParserUserPolicy(userId, { enabled: true })
        : await resetXLinkParserUserPolicy(userId)
      setItems((current) =>
        current.map((row) => (row.user_id === userId ? data.item : row)),
      )
    } catch (err) {
      setItems(prev)
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSavingIds((s) => {
        const next = new Set(s)
        next.delete(userId)
        return next
      })
    }
  }

  if (loading && items.length === 0 && !error) return <PageLoading />

  return (
    <div className="space-y-4">
      <Hint scope="user" />
      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}
      {listStatus === 'offline' && !error && (
        <p className="text-sm text-muted-foreground">
          当前未连接 OneBot；已缓存的官方 QQ Bot 用户可直接配置。
        </p>
      )}
      {listStatus === 'incomplete' && !error && (
        <p className="text-sm text-amber-600 dark:text-amber-400">
          OneBot 好友列表同步不完整，数字 QQ 用户暂时只读；官方 QQ Bot 用户仍可配置。
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="pb-3 pr-4 font-medium">昵称</th>
              <th className="pb-3 pr-4 font-medium">QQ / OpenID</th>
              <th className="pb-3 font-medium">X 链接</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const saving = savingIds.has(item.user_id)
              return (
                <tr key={item.user_id} className="border-b border-border last:border-0">
                  <td className="py-3.5 pr-4 font-medium text-foreground">
                    {item.nickname ?? item.name ?? '—'}
                    {item.source === 'official' && (
                      <span className="ml-2 text-xs text-muted-foreground">官方 QQ Bot</span>
                    )}
                    {saving && (
                      <span className="ml-2 text-[10px] text-muted-foreground">保存中…</span>
                    )}
                  </td>
                  <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">
                    {item.user_id}
                  </td>
                  <td className="py-3.5">
                    <div className="inline-flex items-center gap-2">
                      <span
                        className={`text-xs ${item.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}
                      >
                        {item.enabled ? '已启用' : '已关闭'}
                      </span>
                      <ToggleSwitch
                        checked={item.enabled}
                        disabled={saving || !(item.editable ?? listAvailable)}
                        onChange={(checked) => void handleToggle(item.user_id, checked)}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {items.length === 0 && !error && (
          <p className="py-6 text-sm text-muted-foreground">暂无可配置的好友</p>
        )}
      </div>
    </div>
  )
}
