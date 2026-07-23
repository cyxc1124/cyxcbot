import { useCallback, useMemo, useState, type FormEvent } from 'react'
import {
  createRustShopItem,
  deleteRustShopItem,
  getRustShopItems,
  updateRustShopItem,
} from '../api/client'
import type { RustShopItem } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { createRetryHandler } from '../utils/retryLoad'
import { useMountAsync } from './useMountAsync'

export interface RustShopFormState {
  name: string
  item_id: string
  points_cost: string
  sort_order: string
  enabled: boolean
}

export function emptyRustShopForm(): RustShopFormState {
  return {
    name: '',
    item_id: '',
    points_cost: '1',
    sort_order: '0',
    enabled: true,
  }
}

function formFromItem(item: RustShopItem): RustShopFormState {
  return {
    name: item.name,
    item_id: item.item_id,
    points_cost: String(item.points_cost),
    sort_order: String(item.sort_order),
    enabled: item.enabled,
  }
}

export function useRustShopItems() {
  const { showToast } = useToast()
  const [items, setItems] = useState<RustShopItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<RustShopFormState>(emptyRustShopForm)
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<RustShopItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await getRustShopItems()
      setItems(data.items)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load])

  useMountAsync(load)

  const resetForm = useCallback(() => {
    setForm(emptyRustShopForm())
    setEditingId(null)
    setShowForm(false)
  }, [])

  const openCreate = useCallback(() => {
    setForm(emptyRustShopForm())
    setEditingId(null)
    setShowForm(true)
  }, [])

  const openEdit = useCallback((item: RustShopItem) => {
    setForm(formFromItem(item))
    setEditingId(item.id)
    setShowForm(true)
  }, [])

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const pointsCost = Number(form.points_cost)
      const sortOrder = Number(form.sort_order)
      if (!form.name.trim()) {
        showToast('error', '请填写商品中文名')
        return
      }
      if (!form.item_id.trim()) {
        showToast('error', '请填写物品 ID')
        return
      }
      if (!Number.isInteger(pointsCost) || pointsCost <= 0) {
        showToast('error', '所需积分须为正整数')
        return
      }
      if (!Number.isInteger(sortOrder)) {
        showToast('error', '排序须为整数')
        return
      }

      setSaving(true)
      try {
        if (editingId === null) {
          await createRustShopItem({
            name: form.name.trim(),
            item_id: form.item_id.trim(),
            points_cost: pointsCost,
            sort_order: sortOrder,
            enabled: form.enabled,
          })
          showToast('success', '商品已添加')
        } else {
          await updateRustShopItem(editingId, {
            name: form.name.trim(),
            item_id: form.item_id.trim(),
            points_cost: pointsCost,
            sort_order: sortOrder,
            enabled: form.enabled,
          })
          showToast('success', '商品已更新')
        }
        resetForm()
        await load()
      } catch (err) {
        showToast('error', formatApiError(err, '保存失败'))
      } finally {
        setSaving(false)
      }
    },
    [editingId, form, load, resetForm, showToast],
  )

  const handleToggleEnabled = useCallback(
    async (item: RustShopItem) => {
      setTogglingId(item.id)
      try {
        await updateRustShopItem(item.id, { enabled: !item.enabled })
        await load()
      } catch (err) {
        showToast('error', formatApiError(err, '更新失败'))
      } finally {
        setTogglingId(null)
      }
    },
    [load, showToast],
  )

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteRustShopItem(deleteTarget.id)
      showToast('success', '商品已删除')
      setDeleteTarget(null)
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '删除失败'))
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, load, showToast])

  return {
    items,
    loading,
    error,
    retryLoad,
    showForm,
    editingId,
    form,
    setForm,
    saving,
    togglingId,
    deleteTarget,
    setDeleteTarget,
    deleting,
    openCreate,
    openEdit,
    resetForm,
    handleSubmit,
    handleToggleEnabled,
    handleDelete,
  }
}
