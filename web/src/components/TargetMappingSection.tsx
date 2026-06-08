import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  createDynamicTarget,
  createLiveTarget,
  deleteDynamicTarget,
  deleteLiveTarget,
  getDynamicTargets,
  getGroups,
  getLiveTargets,
  updateDynamicTarget,
  updateLiveTarget,
} from '../api/client'
import type { DynamicTarget, Group, LiveTarget } from '../api/types'
import { LoadErrorBanner } from './LoadErrorBanner'
import { GroupSelector } from './GroupSelector'
import { ToggleSwitch } from './ToggleSwitch'
import { useToast } from '../contexts/ToastContext'
import { useSidebar } from '../contexts/SidebarContext'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/format'

type TargetType = 'dynamic' | 'live'
type SubscriptionTarget = DynamicTarget | LiveTarget

interface TargetFormState {
  id: string
  name: string
  enabled: boolean
  at_all: boolean
  group_ids: string[]
}

const emptyForm = (isDynamic: boolean): TargetFormState => ({
  id: '',
  name: '',
  enabled: true,
  at_all: !isDynamic,
  group_ids: [],
})

interface TargetMappingSectionProps {
  type: TargetType
}

function getTargetId(target: SubscriptionTarget, isDynamic: boolean) {
  return isDynamic ? (target as DynamicTarget).uid : (target as LiveTarget).room_id
}

function getTargetDisplayName(
  target: SubscriptionTarget,
  isDynamic: boolean,
  targetLabel: string,
) {
  const id = getTargetId(target, isDynamic)
  return target.name || `${targetLabel} ${id}`
}

export function TargetMappingSection({ type }: TargetMappingSectionProps) {
  const { showToast } = useToast()
  const { setNavCollapsed, setNavCollapsible } = useSidebar()
  const [groups, setGroups] = useState<Group[]>([])
  const [targets, setTargets] = useState<SubscriptionTarget[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(() => emptyForm(type === 'dynamic'))
  const [editOriginalId, setEditOriginalId] = useState('')
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  const isDynamic = type === 'dynamic'
  const idLabel = isDynamic ? 'UP 主 UID' : '直播间房间号'
  const targetLabel = isDynamic ? 'UP 主' : '直播间'

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [g, items] = await Promise.all([
        getGroups(),
        isDynamic ? getDynamicTargets() : getLiveTargets(),
      ])
      setGroups(g)
      setTargets(items)
      setSelectedId((prev) => {
        if (prev !== null && !items.some((t) => t.id === prev)) return null
        return prev
      })
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [isDynamic])

  useEffect(() => {
    const collapsible = selectedId !== null
    setNavCollapsible(collapsible)
    setNavCollapsed(collapsible)
    return () => {
      setNavCollapsible(false)
      setNavCollapsed(false)
    }
  }, [selectedId, setNavCollapsed, setNavCollapsible])

  useEffect(() => {
    void load()
  }, [load])

  const selectedTarget =
    selectedId !== null ? targets.find((t) => t.id === selectedId) ?? null : null

  const resetForm = () => {
    setShowForm(false)
    setEditingId(null)
    setEditOriginalId('')
    setForm(emptyForm(isDynamic))
  }

  const openCreate = () => {
    resetForm()
    setSelectedId(null)
    setShowForm(true)
  }

  const openEdit = (target: SubscriptionTarget) => {
    const targetId = getTargetId(target, isDynamic)
    setEditingId(target.id)
    setEditOriginalId(targetId)
    setSelectedId(target.id)
    setForm({
      id: targetId,
      name: target.name ?? '',
      enabled: target.enabled,
      at_all: target.at_all,
      group_ids: [...target.group_ids],
    })
    setShowForm(true)
  }

  const selectTarget = (target: SubscriptionTarget) => {
    setShowForm(false)
    setEditingId(null)
    setSelectedId(target.id)
  }

  const clearSelection = () => {
    setSelectedId(null)
    setShowForm(false)
    setEditingId(null)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const idValue = form.id.trim()
      if (!idValue || form.group_ids.length === 0) {
        showToast('error', `请填写${idLabel}并选择至少一个群组`)
        return
      }

      if (isDynamic) {
        if (editingId) {
          await updateDynamicTarget(editingId, {
            uid: idValue,
            name: form.name,
            enabled: form.enabled,
            at_all: form.at_all,
            group_ids: form.group_ids,
          })
          showToast('success', '订阅已更新')
        } else {
          const created = await createDynamicTarget({
            uid: idValue,
            name: form.name || undefined,
            enabled: form.enabled,
            at_all: form.at_all,
            group_ids: form.group_ids,
          })
          setSelectedId(created.id)
          showToast('success', '订阅已创建')
        }
      } else if (editingId) {
        await updateLiveTarget(editingId, {
          room_id: idValue,
          name: form.name,
          enabled: form.enabled,
          at_all: form.at_all,
          group_ids: form.group_ids,
        })
        showToast('success', '订阅已更新')
      } else {
        const created = await createLiveTarget({
          room_id: idValue,
          name: form.name || undefined,
          enabled: form.enabled,
          at_all: form.at_all,
          group_ids: form.group_ids,
        })
        setSelectedId(created.id)
        showToast('success', '订阅已创建')
      }

      resetForm()
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除此订阅吗？')) return
    try {
      if (isDynamic) {
        await deleteDynamicTarget(id)
      } else {
        await deleteLiveTarget(id)
      }
      if (selectedId === id) clearSelection()
      showToast('success', '已删除')
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '删除失败')
    }
  }

  const toggleEnabled = async (target: SubscriptionTarget, enabled: boolean) => {
    setTogglingId(target.id)
    try {
      if (isDynamic) {
        await updateDynamicTarget(target.id, { enabled })
      } else {
        await updateLiveTarget(target.id, { enabled })
      }
      showToast('success', '状态已更新')
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '更新失败')
    } finally {
      setTogglingId(null)
    }
  }

  const toggleAtAll = async (target: SubscriptionTarget, at_all: boolean) => {
    setTogglingId(target.id)
    try {
      if (isDynamic) {
        await updateDynamicTarget(target.id, { at_all })
      } else {
        await updateLiveTarget(target.id, { at_all })
      }
      showToast('success', '@全体 设置已更新')
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '更新失败')
    } finally {
      setTogglingId(null)
    }
  }

  const renderForm = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
        {editingId ? '编辑订阅' : '新建订阅'}
      </h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">{idLabel}</label>
            <input
              className="input"
              value={form.id}
              onChange={(e) => {
                const id = e.target.value
                setForm((f) => ({
                  ...f,
                  id,
                  name: editingId && id.trim() !== editOriginalId ? '' : f.name,
                }))
              }}
              required
              placeholder="12345678"
            />
          </div>
          <div>
            <label className="label">显示名称（可选）</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="留空将自动从 B 站获取"
            />
            {!editingId ? (
              <p className="mt-1 text-xs text-slate-500">
                {isDynamic
                  ? 'UID 无效且未填写名称时无法保存'
                  : '房间号无效且未填写名称时无法保存'}
              </p>
            ) : (
              <p className="mt-1 text-xs text-slate-500">
                修改 {idLabel} 后将清空名称并重新从 B 站获取
              </p>
            )}
          </div>
        </div>

        <div>
          <label className="label">订阅群组</label>
          <GroupSelector
            groups={groups}
            selected={form.group_ids}
            onChange={(ids) => setForm((f) => ({ ...f, group_ids: ids }))}
            disabled={saving}
          />
        </div>

        <div className="flex flex-wrap items-center gap-6">
          <div className="inline-flex items-center gap-2">
            <span className="text-sm text-slate-600 dark:text-slate-400">启用订阅</span>
            <ToggleSwitch
              checked={form.enabled}
              disabled={saving}
              onChange={(checked) => setForm((f) => ({ ...f, enabled: checked }))}
            />
          </div>
          <div className="inline-flex items-center gap-2">
            <span className="text-sm text-slate-600 dark:text-slate-400">@全体成员</span>
            <ToggleSwitch
              checked={form.at_all}
              disabled={saving}
              onChange={(checked) => setForm((f) => ({ ...f, at_all: checked }))}
            />
          </div>
        </div>
        <p className="text-xs text-slate-500">
          @全体成员需机器人为群管理员；否则将使用提醒文案
        </p>

        <div className="flex gap-2">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              resetForm()
            }}
          >
            取消
          </button>
        </div>
      </form>
    </div>
  )

  const renderDetail = (target: SubscriptionTarget) => {
    const targetId = getTargetId(target, isDynamic)
    const displayName = getTargetDisplayName(target, isDynamic, targetLabel)
    const rowBusy = togglingId === target.id

    return (
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-700">
          <div className="min-w-0 flex-1">
            <button
              type="button"
              className="mb-2 text-sm text-brand-600 hover:underline dark:text-brand-400"
              onClick={clearSelection}
            >
              ← 返回列表
            </button>
            <h3 className="truncate text-lg font-semibold text-slate-900 dark:text-white">
              {displayName}
            </h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="badge-neutral font-mono text-xs">{targetId}</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              创建于 {formatDateTime(target.created_at)}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-4">
            <div className="inline-flex items-center gap-2">
              <span
                className={`text-xs ${target.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}
              >
                {target.enabled ? '已启用' : '已禁用'}
              </span>
              <ToggleSwitch
                checked={target.enabled}
                disabled={rowBusy}
                onChange={(checked) => void toggleEnabled(target, checked)}
              />
            </div>
            <div className="inline-flex items-center gap-2">
              <span
                className={`text-xs ${target.at_all ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}
              >
                {target.at_all ? '@全体' : '不@全体'}
              </span>
              <ToggleSwitch
                checked={target.at_all}
                disabled={rowBusy}
                onChange={(checked) => void toggleAtAll(target, checked)}
              />
            </div>
            <button
              type="button"
              className="btn-secondary text-sm"
              disabled={rowBusy}
              onClick={() => openEdit(target)}
            >
              编辑
            </button>
            <button
              type="button"
              className="btn-secondary text-sm text-red-600 hover:text-red-700"
              disabled={rowBusy}
              onClick={() => handleDelete(target.id)}
            >
              删除
            </button>
          </div>
        </div>

        <div className="flex-1 pt-6">
          <h4 className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-300">
            推送群组
            <span className="ml-2 font-normal text-slate-500">
              （{target.group_ids.length} 个）
            </span>
          </h4>
          {target.group_ids.length === 0 ? (
            <p className="text-sm text-slate-500">尚未配置推送群组</p>
          ) : (
            <ul className="space-y-2">
              {target.group_ids.map((groupId) => {
                const group = groups.find((g) => g.group_id === groupId)
                const name = group?.group_name ?? groupId
                const hasName = group?.group_name
                return (
                  <li
                    key={groupId}
                    className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 dark:border-slate-700"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900 dark:text-white">
                        {hasName ? name : `群 ${groupId}`}
                      </p>
                      {hasName && (
                        <p className="mt-0.5 font-mono text-xs text-slate-500">{groupId}</p>
                      )}
                    </div>
                    {group?.member_count != null && (
                      <span className="shrink-0 text-xs text-slate-500">
                        {group.member_count} 人
                      </span>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    )
  }

  const showSplit = selectedId !== null || showForm
  const listHiddenOnMobile = showSplit && !showForm && selectedTarget

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          选择{targetLabel}查看推送群组，一个{targetLabel}可订阅多个 QQ 群
        </p>
        <button type="button" className="btn-primary" onClick={openCreate}>
          添加订阅
        </button>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      {loading && targets.length === 0 && !error ? (
        <p className="py-12 text-center text-sm text-slate-500">加载中…</p>
      ) : !loading && error && targets.length === 0 ? (
        <p className="py-12 text-center text-sm text-slate-500">数据暂时无法加载</p>
      ) : !loading && targets.length === 0 && !showForm ? (
        <p className="py-12 text-center text-sm text-slate-500">暂无订阅，点击上方按钮添加</p>
      ) : (
        <div
          className={`flex min-h-[28rem] overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700 ${
            showSplit ? 'divide-x divide-slate-200 dark:divide-slate-700' : ''
          }`}
        >
          {/* 左侧条目列表 */}
          <aside
            className={`shrink-0 bg-slate-50 dark:bg-slate-900/40 ${
              listHiddenOnMobile ? 'hidden lg:block' : ''
            } ${showSplit ? 'w-full lg:w-72' : 'w-full'}`}
          >
            <div className="flex h-full max-h-[32rem] flex-col lg:max-h-[36rem]">
              <div className="border-b border-slate-200 px-3 py-2.5 dark:border-slate-700">
                <p className="text-xs font-medium text-slate-500">
                  {targetLabel}列表
                  <span className="ml-1">({targets.length})</span>
                </p>
              </div>
              <ul className="flex-1 overflow-y-auto p-2">
                {targets.map((target) => {
                  const targetId = getTargetId(target, isDynamic)
                  const displayName = getTargetDisplayName(target, isDynamic, targetLabel)
                  const isSelected = selectedId === target.id
                  return (
                    <li key={target.id}>
                      <button
                        type="button"
                        onClick={() => selectTarget(target)}
                        className={`mb-1 w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                          isSelected
                            ? 'bg-brand-50 text-brand-800 dark:bg-brand-950 dark:text-brand-200'
                            : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{displayName}</p>
                            <p className="mt-0.5 font-mono text-xs text-slate-500">{targetId}</p>
                          </div>
                          <span
                            className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                              target.enabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
                            }`}
                            title={target.enabled ? '已启用' : '已禁用'}
                          />
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {target.group_ids.length} 个群
                        </p>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </aside>

          {/* 右侧详情 / 表单 */}
          {(showSplit || showForm) && (
            <main
              className={`min-w-0 flex-1 bg-white p-4 dark:bg-slate-900 ${
                showForm || selectedTarget ? 'block' : 'hidden lg:block'
              }`}
            >
              {showForm ? (
                renderForm()
              ) : selectedTarget ? (
                renderDetail(selectedTarget)
              ) : (
                <div className="flex h-full min-h-[20rem] items-center justify-center text-sm text-slate-500">
                  请从左侧选择一个{targetLabel}
                </div>
              )}
            </main>
          )}
        </div>
      )}
    </div>
  )
}
