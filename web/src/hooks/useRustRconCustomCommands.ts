import { useCallback, useMemo, useState, type FormEvent } from 'react'
import {
  createRustRconCustomCommand,
  deleteRustRconCustomCommand,
  getRustRconBindings,
  getRustRconCustomCommands,
  updateRustRconCustomCommand,
} from '../api/client'
import type { RustRconBinding, RustRconCustomCommand } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { createRetryHandler } from '../utils/retryLoad'
import { useMountAsync } from './useMountAsync'

function parseQqInput(raw: string): string[] {
  return [
    ...new Set(
      raw
        .split('\n')
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  ]
}

function formatQqInput(qqList: string[]): string {
  return qqList.join('\n')
}

function validateQqList(list: string[]): string | null {
  if (list.length === 0) return '请至少填写一个允许执行的 QQ 号'
  const invalid = list.filter((qq) => !/^\d+$/.test(qq))
  if (invalid.length > 0) return `QQ 号格式无效: ${invalid.join(', ')}`
  return null
}

export interface RustRconCustomCommandFormState {
  name: string
  template: string
  binding_id: string
  allowedQqText: string
  enabled: boolean
}

export function emptyRustRconCustomCommandForm(
  defaultBindingId = '',
): RustRconCustomCommandFormState {
  return {
    name: '',
    template: 'giveto {steamid} ',
    binding_id: defaultBindingId,
    allowedQqText: '',
    enabled: true,
  }
}

function formFromItem(item: RustRconCustomCommand): RustRconCustomCommandFormState {
  return {
    name: item.name,
    template: item.template,
    binding_id: String(item.binding_id),
    allowedQqText: formatQqInput(item.allowed_qq_ids),
    enabled: item.enabled,
  }
}

export function useRustRconCustomCommands() {
  const { showToast } = useToast()
  const [items, setItems] = useState<RustRconCustomCommand[]>([])
  const [bindings, setBindings] = useState<RustRconBinding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<RustRconCustomCommandFormState>(
    emptyRustRconCustomCommandForm(),
  )
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<RustRconCustomCommand | null>(null)
  const [deleting, setDeleting] = useState(false)

  const defaultBindingId = useMemo(() => {
    const enabled = bindings.filter((item) => item.enabled)
    const source = enabled.length > 0 ? enabled : bindings
    return source[0] ? String(source[0].id) : ''
  }, [bindings])

  const bindingLabel = useCallback(
    (bindingId: number) => {
      const binding = bindings.find((item) => item.id === bindingId)
      if (!binding) return `#${bindingId}`
      return binding.name ? `${binding.alias}（${binding.name}）` : binding.alias
    },
    [bindings],
  )

  const load = useCallback(async () => {
    try {
      const [commands, bindingRows] = await Promise.all([
        getRustRconCustomCommands(),
        getRustRconBindings(),
      ])
      setItems(commands.items)
      setBindings(bindingRows)
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
    setForm(emptyRustRconCustomCommandForm(defaultBindingId))
    setEditingId(null)
    setShowForm(false)
  }, [defaultBindingId])

  const openCreate = useCallback(() => {
    setForm(emptyRustRconCustomCommandForm(defaultBindingId))
    setEditingId(null)
    setShowForm(true)
  }, [defaultBindingId])

  const openEdit = useCallback((item: RustRconCustomCommand) => {
    setForm(formFromItem(item))
    setEditingId(item.id)
    setShowForm(true)
  }, [])

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const bindingId = Number(form.binding_id)
      if (!form.name.trim()) {
        showToast('error', '请填写指令名')
        return
      }
      if (!form.template.trim()) {
        showToast('error', '请填写命令模板')
        return
      }
      if (!Number.isInteger(bindingId) || bindingId <= 0) {
        showToast('error', '请选择 RCON 服务器绑定')
        return
      }
      const allowedQqIds = parseQqInput(form.allowedQqText)
      const qqError = validateQqList(allowedQqIds)
      if (qqError) {
        showToast('error', qqError)
        return
      }

      setSaving(true)
      try {
        if (editingId === null) {
          await createRustRconCustomCommand({
            name: form.name.trim(),
            template: form.template.trim(),
            binding_id: bindingId,
            allowed_qq_ids: allowedQqIds,
            enabled: form.enabled,
          })
          showToast('success', '自定义指令已添加')
        } else {
          await updateRustRconCustomCommand(editingId, {
            name: form.name.trim(),
            template: form.template.trim(),
            binding_id: bindingId,
            allowed_qq_ids: allowedQqIds,
            enabled: form.enabled,
          })
          showToast('success', '自定义指令已更新')
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
    async (item: RustRconCustomCommand) => {
      setTogglingId(item.id)
      try {
        await updateRustRconCustomCommand(item.id, { enabled: !item.enabled })
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
      await deleteRustRconCustomCommand(deleteTarget.id)
      showToast('success', '自定义指令已删除')
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
    bindings,
    bindingLabel,
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
