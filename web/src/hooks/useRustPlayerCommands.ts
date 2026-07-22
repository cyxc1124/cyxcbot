import { useCallback, useMemo, useState, type FormEvent } from 'react'
import { getSettings, patchSettings } from '../api/client'
import type { Settings } from '../api/types'
import {
  RUST_PLAYER_COMMAND_FIELDS,
  type RustPlayerCommandId,
} from '../constants/commandAliases'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { createRetryHandler } from '../utils/retryLoad'
import {
  buildForm,
  parseLines,
  type CommandForm,
  type CommandFormValue,
} from '../pages/settings/commandsForm'
import { useMountAsync } from './useMountAsync'

export function useRustPlayerCommands() {
  const { showToast } = useToast()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<CommandForm>(() =>
    buildForm(null, RUST_PLAYER_COMMAND_FIELDS),
  )

  const load = useCallback(async () => {
    try {
      const settings = await getSettings()
      setForm(buildForm(settings, RUST_PLAYER_COMMAND_FIELDS))
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load])

  useMountAsync(load)

  const updateField = (id: RustPlayerCommandId, patch: Partial<CommandFormValue>) => {
    setForm((current) => ({
      ...current,
      [id]: { ...current[id]!, ...patch },
    }))
  }

  const handleReset = (id: RustPlayerCommandId) => {
    const field = RUST_PLAYER_COMMAND_FIELDS.find((item) => item.id === id)
    if (!field) return
    updateField(id, { enabled: true, text: field.defaultTriggers.join('\n') })
  }

  const handleSubmit = useCallback(
    async (event: FormEvent) => {
      event.preventDefault()

      const payload: Settings['command_aliases'] = {}
      for (const field of RUST_PLAYER_COMMAND_FIELDS) {
        const value = form[field.id]
        if (!value) continue
        const triggers = parseLines(value.text)
        if (value.enabled && triggers.length === 0) {
          showToast('error', `「${field.label}」已启用但未填写触发词`)
          return
        }
        payload[field.id] = { enabled: value.enabled, triggers }
      }

      setSaving(true)
      try {
        const updated = await patchSettings({ command_aliases: payload })
        setForm(buildForm(updated, RUST_PLAYER_COMMAND_FIELDS))
        showToast('success', '群管命令已保存')
      } catch (err) {
        showToast('error', formatApiError(err, '保存失败'))
      } finally {
        setSaving(false)
      }
    },
    [form, showToast],
  )

  return {
    form,
    loading,
    error,
    saving,
    retryLoad,
    updateField,
    handleReset,
    handleSubmit,
  }
}
