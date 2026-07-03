import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import {
  getGroupSpecialTitlePolicy,
  updateGroupSpecialTitlePolicy,
} from '../api/client'
import type { Group } from '../api/types'
import { LoadErrorBanner } from './LoadErrorBanner'
import { PageLoading } from './LoadingSpinner'
import { ToggleSwitch } from './ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import {
  computePolicyAfterToggle,
  computeToggleAllPolicy,
  isItemEnabled,
} from '../utils/restrictPolicy'

export function GroupSpecialTitlePolicyTab() {
  const { showToast } = useToast()
  const [groups, setGroups] = useState<Group[]>([])
  const [restrict, setRestrict] = useState(true)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [dailyLimit, setDailyLimit] = useState(10)
  const [dailyLimitDraft, setDailyLimitDraft] = useState('10')
  const [loading, setLoading] = useLoadingOnKeyChange('special-title-group')
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [savingDailyLimit, setSavingDailyLimit] = useState(false)

  const items = groups.map((g) => ({ id: g.group_id, name: g.group_name, extra: g.member_count }))
  const allIds = items.map((item) => item.id)

  const load = useCallback(async () => {
    try {
      const data = await getGroupSpecialTitlePolicy()
      setGroups(data.groups)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_group_ids)
      setDailyLimit(data.daily_limit)
      setDailyLimitDraft(String(data.daily_limit))
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  const applyResponse = (data: Awaited<ReturnType<typeof getGroupSpecialTitlePolicy>>) => {
    setGroups(data.groups)
    setRestrict(data.restrict)
    setEnabledIds(data.enabled_group_ids)
    setDailyLimit(data.daily_limit)
    setDailyLimitDraft(String(data.daily_limit))
  }

  const savePolicy = async (payload: {
    restrict: boolean
    enabled_group_ids: string[]
    daily_limit?: number
  }) => updateGroupSpecialTitlePolicy(payload).then(applyResponse)

  const handleToggle = async (itemId: string, enabled: boolean) => {
    const next = computePolicyAfterToggle(itemId, enabled, allIds, restrict, enabledIds)

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_ids)
    setTogglingId(itemId)

    try {
      await savePolicy({
        restrict: next.restrict,
        enabled_group_ids: next.enabled_ids,
      })
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    const next = computeToggleAllPolicy(enabled)

    const prevRestrict = restrict
    const prevEnabledIds = enabledIds
    setRestrict(next.restrict)
    setEnabledIds(next.enabled_ids)
    setTogglingId('__all__')

    try {
      await savePolicy({
        restrict: next.restrict,
        enabled_group_ids: next.enabled_ids,
      })
      showToast('success', enabled ? '已启用全部群组' : '已关闭全部群组')
    } catch (err) {
      setRestrict(prevRestrict)
      setEnabledIds(prevEnabledIds)
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setTogglingId(null)
    }
  }

  const handleSaveDailyLimit = async () => {
    const parsed = Number(dailyLimitDraft)
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 100) {
      showToast('error', '每日上限须为 1–100 的整数')
      setDailyLimitDraft(String(dailyLimit))
      return
    }

    if (parsed === dailyLimit) return

    setSavingDailyLimit(true)
    try {
      await savePolicy({
        restrict,
        enabled_group_ids: enabledIds,
        daily_limit: parsed,
      })
      showToast('success', '每日上限已保存')
    } catch (err) {
      setDailyLimitDraft(String(dailyLimit))
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSavingDailyLimit(false)
    }
  }

  if (loading && items.length === 0 && !error) return <PageLoading />

  const allEnabled = !restrict
  const noneEnabled = restrict && enabledIds.length === 0
  const busy = togglingId !== null || savingDailyLimit

  return (
    <div className="space-y-6">
      <div className="card space-y-4">
        <div>
          <h3 className="font-semibold text-foreground">每日使用上限</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            每个群每位成员每天最多可成功设置专属头衔的次数（按北京时间自然日计算，全局统一）。
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="max-w-xs flex-1">
            <label className="label" htmlFor="special_title_daily_limit">
              每人每日上限（次）
            </label>
            <input
              id="special_title_daily_limit"
              type="number"
              min={1}
              max={100}
              className="input"
              value={dailyLimitDraft}
              disabled={busy}
              onChange={(e) => setDailyLimitDraft(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn-primary text-sm"
            disabled={busy}
            onClick={() => void handleSaveDailyLimit()}
          >
            保存上限
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          配置哪些群可使用{' '}
          <code className="rounded bg-secondary px-1 py-0.5 text-xs">/头衔</code>、
          <code className="rounded bg-secondary px-1 py-0.5 text-xs">#头衔</code>{' '}
          自助设置 QQ 专属头衔。仅显示已启用「群消息」的群；需机器人为群主且协议端支持设置头衔。成功或失败均不在群内回复。
        </p>
        {items.length > 0 && (
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

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="card">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {error
              ? '数据暂时无法加载'
              : '暂无已启用群消息的群组。请先在「群消息」Tab 中启用对应群组，或确保机器人已连接 OneBot。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground border-border">
                  <th className="pb-3 pr-4 font-medium">群名称</th>
                  <th className="pb-3 pr-4 font-medium">群号</th>
                  <th className="pb-3 pr-4 font-medium">成员数</th>
                  <th className="pb-3 font-medium text-right">允许群头衔</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const enabled = isItemEnabled(item.id, restrict, enabledIds)
                  const rowBusy = busy && (togglingId === item.id || togglingId === '__all__')
                  return (
                    <tr
                      key={item.id}
                      className="border-b border-border last:border-0 border-border"
                    >
                      <td className="py-3.5 pr-4 font-medium text-foreground">
                        {item.name ?? '—'}
                      </td>
                      <td className="py-3.5 pr-4 font-mono text-xs text-muted-foreground">{item.id}</td>
                      <td className="py-3.5 pr-4 text-muted-foreground">{item.extra ?? '—'}</td>
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
                            onChange={(checked) => void handleToggle(item.id, checked)}
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
    </div>
  )
}
