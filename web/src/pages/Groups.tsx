import { useCallback, useEffect, useState } from 'react'
import { getMessagePolicy, updateMessagePolicy } from '../api/client'
import type { Group, GroupMessagePolicy } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { GroupSelector } from '../components/GroupSelector'
import { PageLoading } from '../components/LoadingSpinner'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'

function isGroupEnabled(groupId: string, policy: GroupMessagePolicy): boolean {
  if (!policy.restrict) return true
  return policy.enabled_group_ids.includes(groupId)
}

export function GroupsPage() {
  const { showToast } = useToast()
  const [policy, setPolicy] = useState<GroupMessagePolicy | null>(null)
  const [restrict, setRestrict] = useState(false)
  const [enabledIds, setEnabledIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getMessagePolicy()
      setPolicy(data)
      setRestrict(data.restrict)
      setEnabledIds(data.enabled_group_ids)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateMessagePolicy({
        restrict,
        enabled_group_ids: enabledIds,
      })
      setPolicy(updated)
      setRestrict(updated.restrict)
      setEnabledIds(updated.enabled_group_ids)
      showToast('success', '群组消息策略已保存')
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const dirty =
    policy !== null &&
    (restrict !== policy.restrict ||
      enabledIds.length !== policy.enabled_group_ids.length ||
      enabledIds.some((id) => !policy.enabled_group_ids.includes(id)))

  if (loading && !policy && !error) return <PageLoading />

  const groups: Group[] = policy?.groups ?? []

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">群组管理</h2>
        <p className="mt-1 text-sm text-slate-500">
          查看机器人已加入的 QQ 群，并控制处理哪些群的消息
        </p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="card space-y-6">
        <div>
          <h3 className="text-lg font-semibold">消息处理策略</h3>
          <p className="mt-1 text-sm text-slate-500">
            关闭限制时，机器人会处理所有群的消息；开启后仅处理下方选定的群。
          </p>
        </div>

        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            checked={restrict}
            onChange={(e) => setRestrict(e.target.checked)}
            disabled={saving}
          />
          <span>
            <span className="block text-sm font-medium text-slate-900 dark:text-white">
              仅处理选定群组的消息
            </span>
            <span className="block text-xs text-slate-500">
              私聊消息不受此设置影响
            </span>
          </span>
        </label>

        {restrict && (
          <GroupSelector
            groups={groups}
            selected={enabledIds}
            onChange={setEnabledIds}
            disabled={saving}
            helperText="选择需要机器人响应群消息的群组"
          />
        )}

        <div className="flex justify-end">
          <button
            type="button"
            className="btn-primary"
            disabled={saving || !dirty}
            onClick={() => void handleSave()}
          >
            {saving ? '保存中…' : '保存策略'}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="mb-4">
          <h3 className="text-lg font-semibold">QQ 群列表</h3>
          <p className="mt-1 text-sm text-slate-500">
            来自 OneBot 接口，需机器人与 QQ 客户端在线
          </p>
        </div>

        {groups.length === 0 ? (
          <p className="text-sm text-slate-500">
            {error
              ? '数据暂时无法加载'
              : '暂无可用群组，请确保机器人已连接 OneBot 并在线。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700">
                  <th className="pb-3 pr-4 font-medium">群名称</th>
                  <th className="pb-3 pr-4 font-medium">群号</th>
                  <th className="pb-3 pr-4 font-medium">成员数</th>
                  <th className="pb-3 font-medium">消息处理</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => {
                  const enabled = policy
                    ? isGroupEnabled(group.group_id, { ...policy, restrict, enabled_group_ids: enabledIds })
                    : false
                  return (
                    <tr
                      key={group.group_id}
                      className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                    >
                      <td className="py-3 pr-4">{group.group_name ?? '—'}</td>
                      <td className="py-3 pr-4 font-mono text-xs">{group.group_id}</td>
                      <td className="py-3 pr-4">{group.member_count ?? '—'}</td>
                      <td className="py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                            enabled
                              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                          }`}
                        >
                          {enabled ? '已启用' : '已忽略'}
                        </span>
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
