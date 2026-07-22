import { useCallback, useMemo, useState, type FormEvent } from 'react'
import {
  createRustRconBinding,
  deleteRustRconBinding,
  getRustRconBindings,
  updateRustRconBinding,
} from '../api/client'
import type { RustRconBinding } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { createRetryHandler } from '../utils/retryLoad'
import { useMountAsync } from './useMountAsync'

const DEFAULT_PORT = 28016

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

export interface RustRconFormState {
  alias: string
  name: string
  host: string
  port: string
  password: string
  allowedQqText: string
  enabled: boolean
}

export function emptyRustRconForm(): RustRconFormState {
  return {
    alias: '',
    name: '',
    host: '',
    port: String(DEFAULT_PORT),
    password: '',
    allowedQqText: '',
    enabled: true,
  }
}

function formFromBinding(binding: RustRconBinding): RustRconFormState {
  return {
    alias: binding.alias,
    name: binding.name ?? '',
    host: binding.host,
    port: String(binding.port),
    password: '',
    allowedQqText: formatQqInput(binding.allowed_qq_ids),
    enabled: binding.enabled,
  }
}

export function useRustRconBindings() {
  const { showToast } = useToast()
  const [bindings, setBindings] = useState<RustRconBinding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<RustRconFormState>(emptyRustRconForm)
  const [saving, setSaving] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<RustRconBinding | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      const items = await getRustRconBindings()
      setBindings(items)
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
    setShowForm(false)
    setEditingId(null)
    setForm(emptyRustRconForm())
  }, [])

  const openCreate = useCallback(() => {
    setEditingId(null)
    setForm(emptyRustRconForm())
    setShowForm(true)
  }, [])

  const openEdit = useCallback((binding: RustRconBinding) => {
    setEditingId(binding.id)
    setForm(formFromBinding(binding))
    setShowForm(true)
  }, [])

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()
      const alias = form.alias.trim()
      const host = form.host.trim()
      const port = Number.parseInt(form.port, 10)
      const name = form.name.trim()

      if (!alias) {
        showToast('error', '请填写触发词')
        return
      }
      if (!host) {
        showToast('error', '请填写服务器地址')
        return
      }
      if (!Number.isFinite(port) || port < 1 || port > 65535) {
        showToast('error', '端口必须在 1–65535 之间')
        return
      }
      if (!editingId && !form.password.trim()) {
        showToast('error', '请填写 RCON 密码')
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
        if (editingId) {
          const payload = {
            alias,
            host,
            port,
            enabled: form.enabled,
            name: name || null,
            allowed_qq_ids: allowedQqIds,
            ...(form.password.trim() ? { password: form.password } : {}),
          }
          await updateRustRconBinding(editingId, payload)
          showToast('success', 'RCON 绑定已更新')
        } else {
          await createRustRconBinding({
            alias,
            host,
            port,
            password: form.password,
            enabled: form.enabled,
            name: name || null,
            allowed_qq_ids: allowedQqIds,
          })
          showToast('success', 'RCON 绑定已创建')
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
    async (binding: RustRconBinding) => {
      setTogglingId(binding.id)
      try {
        await updateRustRconBinding(binding.id, { enabled: !binding.enabled })
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
      await deleteRustRconBinding(deleteTarget.id)
      showToast('success', 'RCON 绑定已删除')
      setDeleteTarget(null)
      if (editingId === deleteTarget.id) {
        resetForm()
      }
      await load()
    } catch (err) {
      showToast('error', formatApiError(err, '删除失败'))
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, editingId, load, resetForm, showToast])

  return {
    bindings,
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
