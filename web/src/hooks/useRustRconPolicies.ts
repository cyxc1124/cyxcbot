import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from './useLoadingOnKeyChange'
import { useMountAsync } from './useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { formatApiError } from '../utils/apiError'
import { useToast } from '../contexts/ToastContext'

export interface RustRconPolicyRow {
  customized: boolean
  enabled: boolean
}

interface UseRustRconPoliciesOptions<T extends RustRconPolicyRow> {
  loadingKey: string
  loadItems: () => Promise<T[]>
  getItemId: (item: T) => string
  mergeItem: (existing: T, incoming: T) => T
  updateItem: (id: string, enabled: boolean, row: T) => Promise<{ item: T }>
  resetItem: (id: string) => Promise<{ item: T }>
  toggleAllSuccessMessage: (enabled: boolean) => string
}

export function useRustRconPolicies<T extends RustRconPolicyRow>({
  loadingKey,
  loadItems,
  getItemId,
  mergeItem,
  updateItem,
  resetItem,
  toggleAllSuccessMessage,
}: UseRustRconPoliciesOptions<T>) {
  const { showToast } = useToast()
  const [items, setItems] = useState<T[]>([])
  const [loading, setLoading] = useLoadingOnKeyChange(loadingKey)
  const [error, setError] = useState('')
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set())
  const [togglingAll, setTogglingAll] = useState(false)

  const markSaving = (id: string, saving: boolean) => {
    setSavingIds((current) => {
      const next = new Set(current)
      if (saving) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const applyItem = useCallback(
    (item: T) => {
      setItems((current) =>
        current.map((row) => (getItemId(row) === getItemId(item) ? mergeItem(row, item) : row)),
      )
    },
    [getItemId, mergeItem],
  )

  const load = useCallback(async () => {
    try {
      setItems(await loadItems())
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [loadItems, setLoading])

  useMountAsync(load)

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const patchItem = async (id: string, enabled: boolean) => {
    const normalizedId = String(id)
    const row = items.find((item) => getItemId(item) === normalizedId)
    if (!row) return

    const prevRow = row
    setItems((current) =>
      current.map((item) =>
        getItemId(item) === normalizedId
          ? { ...item, enabled, customized: enabled }
          : item,
      ),
    )

    markSaving(normalizedId, true)
    try {
      const data = enabled
        ? await updateItem(normalizedId, true, row)
        : await resetItem(normalizedId)
      applyItem(data.item)
    } catch (err) {
      setItems((current) =>
        current.map((item) => (getItemId(item) === normalizedId ? prevRow : item)),
      )
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      markSaving(normalizedId, false)
    }
  }

  const handleReset = async (id: string) => {
    markSaving(id, true)
    try {
      const data = await resetItem(id)
      applyItem(data.item)
      showToast('success', '已恢复为默认（关闭）')
    } catch (err) {
      showToast('error', formatApiError(err, '恢复失败'))
    } finally {
      markSaving(id, false)
    }
  }

  const handleToggleAll = async (enabled: boolean) => {
    if (items.length === 0) return

    const prevItems = items
    setTogglingAll(true)
    setItems((current) =>
      current.map((item) => ({
        ...item,
        enabled,
        customized: enabled,
      })),
    )

    try {
      await Promise.all(
        items.map((item) =>
          enabled ? updateItem(getItemId(item), true, item) : resetItem(getItemId(item)),
        ),
      )
      await load()
      showToast('success', toggleAllSuccessMessage(enabled))
    } catch (err) {
      setItems(prevItems)
      showToast('error', formatApiError(err, '批量保存失败'))
    } finally {
      setTogglingAll(false)
    }
  }

  const allEnabled = items.length > 0 && items.every((item) => item.enabled)
  const noneEnabled = items.length > 0 && items.every((item) => !item.enabled)
  const busy = togglingAll || savingIds.size > 0

  return {
    items,
    loading,
    error,
    retryLoad,
    savingIds,
    togglingAll,
    patchItem,
    handleReset,
    handleToggleAll,
    allEnabled,
    noneEnabled,
    busy,
  }
}
