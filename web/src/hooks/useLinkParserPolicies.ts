import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from './useLoadingOnKeyChange'
import { useMountAsync } from './useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import {
  buildPolicyPayload,
  buildToggleAllPayload,
  buildToggleAllSendVideoPayload,
  isAllPoliciesEnabled,
  isAllSendVideoEnabled,
  isNoPoliciesEnabled,
  isNoSendVideoEnabled,
  type LinkParserPolicyFlags,
} from '../utils/linkParserPolicy'
import { formatApiError } from '../utils/apiError'
import { useToast } from '../contexts/ToastContext'

export interface LinkParserPolicyRow extends LinkParserPolicyFlags {
  customized: boolean
}

interface UseLinkParserPoliciesOptions<T extends LinkParserPolicyRow> {
  loadingKey: string
  loadItems: () => Promise<T[]>
  getItemId: (item: T) => string
  mergeItem: (existing: T, incoming: T) => T
  updateItem: (
    id: string,
    payload: LinkParserPolicyFlags,
    row: T,
  ) => Promise<{ item: T }>
  resetItem: (id: string) => Promise<{ item: T }>
  toggleAllSuccessMessage: (enabled: boolean) => string
  toggleAllSendVideoSuccessMessage: (enabled: boolean) => string
}

export function useLinkParserPolicies<T extends LinkParserPolicyRow>({
  loadingKey,
  loadItems,
  getItemId,
  mergeItem,
  updateItem,
  resetItem,
  toggleAllSuccessMessage,
  toggleAllSendVideoSuccessMessage,
}: UseLinkParserPoliciesOptions<T>) {
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

  const patchItem = async (id: string, patch: Partial<LinkParserPolicyFlags>) => {
    const normalizedId = String(id)
    const row = items.find((item) => getItemId(item) === normalizedId)
    if (!row) return

    const optimistic = buildPolicyPayload(row, patch)
    const prevRow = row

    setItems((current) =>
      current.map((item) =>
        getItemId(item) === normalizedId ? { ...item, ...optimistic } : item,
      ),
    )

    markSaving(normalizedId, true)
    try {
      const data = await updateItem(normalizedId, optimistic, row)
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
      showToast('success', '已恢复为默认（全部关闭）')
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
    // 全开：只开三项解析，保留各行已有的「发送视频」；全关走 reset
    setItems((current) =>
      current.map((item) => {
        if (!enabled) {
          return {
            ...item,
            ...buildToggleAllPayload(false),
            customized: false,
          }
        }
        const payload = {
          video_enabled: true,
          live_enabled: true,
          dynamic_enabled: true,
          send_video_enabled: item.send_video_enabled,
        }
        return {
          ...item,
          ...payload,
          customized: true,
        }
      }),
    )

    try {
      await Promise.all(
        items.map((item) =>
          enabled
            ? updateItem(
                getItemId(item),
                {
                  video_enabled: true,
                  live_enabled: true,
                  dynamic_enabled: true,
                  send_video_enabled: item.send_video_enabled,
                },
                item,
              )
            : resetItem(getItemId(item)),
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

  const handleToggleAllSendVideo = async (enabled: boolean) => {
    if (items.length === 0) return

    const prevItems = items
    setTogglingAll(true)
    setItems((current) =>
      current.map((item) => {
        const payload = buildToggleAllSendVideoPayload(item, enabled)
        return {
          ...item,
          ...payload,
          customized:
            payload.video_enabled ||
            payload.live_enabled ||
            payload.dynamic_enabled ||
            payload.send_video_enabled,
        }
      }),
    )

    try {
      await Promise.all(
        items.map((item) => {
          const payload = buildToggleAllSendVideoPayload(item, enabled)
          const nextCustomized =
            payload.video_enabled ||
            payload.live_enabled ||
            payload.dynamic_enabled ||
            payload.send_video_enabled
          // 全关发送视频后若三项解析也全关，走 reset 清掉记录
          if (!nextCustomized) {
            return resetItem(getItemId(item))
          }
          return updateItem(getItemId(item), payload, item)
        }),
      )
      await load()
      showToast('success', toggleAllSendVideoSuccessMessage(enabled))
    } catch (err) {
      setItems(prevItems)
      showToast('error', formatApiError(err, '批量保存失败'))
    } finally {
      setTogglingAll(false)
    }
  }

  const allEnabled = isAllPoliciesEnabled(items)
  const noneEnabled = isNoPoliciesEnabled(items)
  const allSendVideoEnabled = isAllSendVideoEnabled(items)
  const noneSendVideoEnabled = isNoSendVideoEnabled(items)
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
    handleToggleAllSendVideo,
    allEnabled,
    noneEnabled,
    allSendVideoEnabled,
    noneSendVideoEnabled,
    busy,
  }
}
