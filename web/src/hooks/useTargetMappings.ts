import { useCallback, useMemo, useState, type FormEvent } from 'react'
import {
  createDynamicTarget,
  createLiveTarget,
  deleteDynamicTarget,
  deleteLiveTarget,
  getDynamicTargets,
  getFriends,
  getGroups,
  getLiveTargets,
  updateDynamicTarget,
  updateLiveTarget,
} from '../api/client'
import type { Friend, Group } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { useLoadingOnKeyChange } from './useLoadingOnKeyChange'
import { useMountAsync } from './useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import {
  emptyForm,
  formFromTarget,
  type SubscriptionTarget,
  type TargetFormState,
  type TargetType,
} from '../components/targetMapping/types'

interface UseTargetMappingsOptions {
  type: TargetType
  onTargetsChanged?: () => void | Promise<void>
}

export function useTargetMappings({ type, onTargetsChanged }: UseTargetMappingsOptions) {
  const { showToast } = useToast()
  const [groups, setGroups] = useState<Group[]>([])
  const [friends, setFriends] = useState<Friend[]>([])
  const [targets, setTargets] = useState<SubscriptionTarget[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange(type)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<TargetFormState>(() => emptyForm(type === 'dynamic'))
  const [editOriginalId, setEditOriginalId] = useState('')
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)

  const isDynamic = type === 'dynamic'
  const idLabel = isDynamic ? 'UP 主 UID' : '直播间房间号'
  const targetLabel = isDynamic ? 'UP 主' : '直播间'

  const load = useCallback(async () => {
    try {
      const [g, f, items] = await Promise.all([
        getGroups(),
        getFriends(),
        isDynamic ? getDynamicTargets() : getLiveTargets(),
      ])
      setGroups(g)
      setFriends(f)
      setTargets(items)
      setSelectedId((prev) => {
        if (prev !== null && !items.some((t) => t.id === prev)) return null
        return prev
      })
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [isDynamic, setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const notifyTargetsChanged = useCallback(async () => {
    if (onTargetsChanged) {
      await onTargetsChanged()
    }
  }, [onTargetsChanged])

  useMountAsync(load)

  const selectedTarget =
    selectedId !== null ? targets.find((t) => t.id === selectedId) ?? null : null

  const resetForm = useCallback(() => {
    setShowForm(false)
    setEditingId(null)
    setEditOriginalId('')
    setForm(emptyForm(isDynamic))
  }, [isDynamic])

  const openCreate = useCallback(() => {
    resetForm()
    setSelectedId(null)
    setShowForm(true)
  }, [resetForm])

  const openEdit = useCallback(
    (target: SubscriptionTarget) => {
      setEditingId(target.id)
      setEditOriginalId(formFromTarget(target, isDynamic).id)
      setSelectedId(target.id)
      setForm(formFromTarget(target, isDynamic))
      setShowForm(true)
    },
    [isDynamic],
  )

  const selectTarget = useCallback((target: SubscriptionTarget) => {
    setShowForm(false)
    setEditingId(null)
    setSelectedId(target.id)
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
    setShowForm(false)
    setEditingId(null)
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const idValue = form.id.trim()
      if (!idValue || (form.group_ids.length === 0 && form.user_ids.length === 0)) {
        showToast('error', `请填写${idLabel}并选择至少一个群组或好友`)
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
            user_ids: form.user_ids,
          })
          showToast('success', '订阅已更新')
        } else {
          const created = await createDynamicTarget({
            uid: idValue,
            name: form.name || undefined,
            enabled: form.enabled,
            at_all: form.at_all,
            group_ids: form.group_ids,
            user_ids: form.user_ids,
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
          user_ids: form.user_ids,
        })
        showToast('success', '订阅已更新')
      } else {
        const created = await createLiveTarget({
          room_id: idValue,
          name: form.name || undefined,
          enabled: form.enabled,
          at_all: form.at_all,
          group_ids: form.group_ids,
          user_ids: form.user_ids,
        })
        setSelectedId(created.id)
        showToast('success', '订阅已创建')
      }

      resetForm()
      await load()
      await notifyTargetsChanged()
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
      await notifyTargetsChanged()
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
      await notifyTargetsChanged()
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

  return {
    groups,
    friends,
    targets,
    loading,
    error,
    retryLoad,
    selectedId,
    selectedTarget,
    showForm,
    editingId,
    form,
    setForm,
    editOriginalId,
    saving,
    togglingId,
    isDynamic,
    idLabel,
    targetLabel,
    openCreate,
    openEdit,
    selectTarget,
    clearSelection,
    resetForm,
    handleSubmit,
    handleDelete,
    toggleEnabled,
    toggleAtAll,
  }
}
