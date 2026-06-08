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
import { GroupTags } from './GroupTags'
import { StatusBadge } from './StatusBadge'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/format'

type TargetType = 'dynamic' | 'live'

interface TargetFormState {
  id: string
  name: string
  enabled: boolean
  group_ids: string[]
}

const emptyForm = (): TargetFormState => ({
  id: '',
  name: '',
  enabled: true,
  group_ids: [],
})

interface TargetMappingSectionProps {
  type: TargetType
}

export function TargetMappingSection({ type }: TargetMappingSectionProps) {
  const { showToast } = useToast()
  const [groups, setGroups] = useState<Group[]>([])
  const [targets, setTargets] = useState<(DynamicTarget | LiveTarget)[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

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
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [isDynamic])

  useEffect(() => {
    void load()
  }, [load])

  const resetForm = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm())
  }

  const openCreate = () => {
    resetForm()
    setShowForm(true)
  }

  const openEdit = (target: DynamicTarget | LiveTarget) => {
    setEditingId(target.id)
    setForm({
      id: isDynamic ? (target as DynamicTarget).uid : (target as LiveTarget).room_id,
      name: target.name ?? '',
      enabled: target.enabled,
      group_ids: [...target.group_ids],
    })
    setShowForm(true)
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
            name: form.name || undefined,
            enabled: form.enabled,
            group_ids: form.group_ids,
          })
          showToast('success', '动态目标已更新')
        } else {
          await createDynamicTarget({
            uid: idValue,
            name: form.name || undefined,
            enabled: form.enabled,
            group_ids: form.group_ids,
          })
          showToast('success', '动态目标已创建')
        }
      } else if (editingId) {
        await updateLiveTarget(editingId, {
          name: form.name || undefined,
          enabled: form.enabled,
          group_ids: form.group_ids,
        })
        showToast('success', '直播目标已更新')
      } else {
        await createLiveTarget({
          room_id: idValue,
          name: form.name || undefined,
          enabled: form.enabled,
          group_ids: form.group_ids,
        })
        showToast('success', '直播目标已创建')
      }

      resetForm()
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除此映射吗？')) return
    try {
      if (isDynamic) {
        await deleteDynamicTarget(id)
      } else {
        await deleteLiveTarget(id)
      }
      showToast('success', '已删除')
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '删除失败')
    }
  }

  const toggleEnabled = async (target: DynamicTarget | LiveTarget) => {
    try {
      if (isDynamic) {
        await updateDynamicTarget(target.id, { enabled: !target.enabled })
      } else {
        await updateLiveTarget(target.id, { enabled: !target.enabled })
      }
      showToast('success', '状态已更新')
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '更新失败')
    }
  }

  const getTargetId = (target: DynamicTarget | LiveTarget) =>
    isDynamic ? (target as DynamicTarget).uid : (target as LiveTarget).room_id

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">推送映射</h3>
          <p className="mt-0.5 text-sm text-slate-500">
            一个{targetLabel}可推送到多个 QQ 群
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={openCreate}>
          添加映射
        </button>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      {showForm && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/50">
          <h4 className="mb-4 font-medium">
            {editingId ? '编辑' : '新建'}映射
          </h4>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label">{idLabel}</label>
                <input
                  className="input"
                  value={form.id}
                  onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                  required
                  readOnly={!!editingId}
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
              </div>
            </div>

            <div>
              <label className="label">推送群组</label>
              <GroupSelector
                groups={groups}
                selected={form.group_ids}
                onChange={(ids) => setForm((f) => ({ ...f, group_ids: ids }))}
                disabled={saving}
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
                className="rounded border-slate-300"
              />
              启用监控
            </label>

            <div className="flex gap-2">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? '保存中…' : '保存'}
              </button>
              <button type="button" className="btn-secondary" onClick={resetForm}>
                取消
              </button>
            </div>
          </form>
        </div>
      )}

      {loading && targets.length === 0 && !error ? (
        <p className="py-6 text-center text-sm text-slate-500">加载中…</p>
      ) : !loading && error && targets.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">数据暂时无法加载</p>
      ) : !loading && targets.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">暂无映射，点击上方按钮添加</p>
      ) : (
        <div className="space-y-3">
          {targets.map((target) => {
            const targetId = getTargetId(target)
            const groupCount = target.group_ids.length
            return (
              <div
                key={target.id}
                className="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-900 dark:text-white">
                        {target.name || `${targetLabel} ${targetId}`}
                      </span>
                      <span className="badge-neutral font-mono text-xs">{targetId}</span>
                      <button type="button" onClick={() => toggleEnabled(target)}>
                        <StatusBadge
                          active={target.enabled}
                          activeLabel="已启用"
                          inactiveLabel="已禁用"
                        />
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      推送到 {groupCount} 个群 · 创建于 {formatDateTime(target.created_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      className="btn-ghost px-2 py-1 text-xs"
                      onClick={() => openEdit(target)}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="btn-ghost px-2 py-1 text-xs text-red-600"
                      onClick={() => handleDelete(target.id)}
                    >
                      删除
                    </button>
                  </div>
                </div>

                <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                  <p className="mb-2 text-xs font-medium text-slate-500">推送群组</p>
                  <GroupTags groupIds={target.group_ids} groups={groups} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
