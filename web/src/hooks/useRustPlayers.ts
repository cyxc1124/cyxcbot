import { useCallback, useMemo, useState } from 'react'
import {
  deleteRustSteamBinding,
  getRustCheckInConfig,
  getRustPlayerOverview,
  updateRustCheckInConfig,
  updateRustPlayerPoints,
} from '../api/client'
import type { RustCheckInConfig, RustPlayerOverviewItem } from '../api/types'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { createRetryHandler } from '../utils/retryLoad'
import { useMountAsync } from './useMountAsync'

const MAX_RUST_PLAYER_POINTS = 1_000_000

function pointsValidationError(value: number): string | null {
  if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
    return '积分必须为非负整数'
  }
  if (value > MAX_RUST_PLAYER_POINTS) {
    return `积分不能超过 ${MAX_RUST_PLAYER_POINTS}`
  }
  return null
}

function rowKey(item: RustPlayerOverviewItem): string {
  return `${item.group_id ?? ''}:${item.user_id}`
}

export function useRustPlayers() {
  const { showToast } = useToast()
  const [items, setItems] = useState<RustPlayerOverviewItem[]>([])
  const [checkInConfig, setCheckInConfig] = useState<RustCheckInConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [configForm, setConfigForm] = useState({ min_points: '1', max_points: '10' })
  const [savingConfig, setSavingConfig] = useState(false)
  const [savingRowKeys, setSavingRowKeys] = useState<Set<string>>(new Set())
  const [unbindingUserIds, setUnbindingUserIds] = useState<Set<string>>(new Set())
  const [draftPoints, setDraftPoints] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    try {
      const [overview, config] = await Promise.all([
        getRustPlayerOverview(),
        getRustCheckInConfig(),
      ])
      setItems(overview.items)
      setCheckInConfig(config)
      setConfigForm({
        min_points: String(config.min_points),
        max_points: String(config.max_points),
      })
      setDraftPoints(
        Object.fromEntries(
          overview.items.map((item) => [rowKey(item), String(item.points)]),
        ),
      )
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load])

  useMountAsync(load)

  const handleSaveConfig = useCallback(async () => {
    const minPoints = Number.parseInt(configForm.min_points, 10)
    const maxPoints = Number.parseInt(configForm.max_points, 10)
    const minError = pointsValidationError(minPoints)
    if (minError) {
      showToast('error', minError)
      return
    }
    const maxError = pointsValidationError(maxPoints)
    if (maxError) {
      showToast('error', maxError)
      return
    }
    if (minPoints > maxPoints) {
      showToast('error', '最小积分不能大于最大积分')
      return
    }

    setSavingConfig(true)
    try {
      const config = await updateRustCheckInConfig({
        min_points: minPoints,
        max_points: maxPoints,
      })
      setCheckInConfig(config)
      showToast('success', '签到积分范围已保存')
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setSavingConfig(false)
    }
  }, [configForm, showToast])

  const handleSavePoints = useCallback(
    async (item: RustPlayerOverviewItem) => {
      if (!item.group_id) {
        showToast('error', '该用户尚无群积分记录，无法修改积分')
        return
      }
      const key = rowKey(item)
      const points = Number.parseInt(draftPoints[key] ?? String(item.points), 10)
      const pointsError = pointsValidationError(points)
      if (pointsError) {
        showToast('error', pointsError)
        return
      }

      setSavingRowKeys((prev) => new Set(prev).add(key))
      try {
        const updated = await updateRustPlayerPoints({
          group_id: item.group_id,
          user_id: item.user_id,
          points,
        })
        setItems((prev) =>
          prev.map((row) =>
            rowKey(row) === key ? { ...row, points: updated.points } : row,
          ),
        )
        showToast('success', '积分已更新')
      } catch (err) {
        showToast('error', formatApiError(err, '保存失败'))
      } finally {
        setSavingRowKeys((prev) => {
          const next = new Set(prev)
          next.delete(key)
          return next
        })
      }
    },
    [draftPoints, showToast],
  )

  const handleUnbind = useCallback(
    async (userId: string) => {
      setUnbindingUserIds((prev) => new Set(prev).add(userId))
      try {
        await deleteRustSteamBinding(userId)
        setItems((prev) =>
          prev.map((row) => (row.user_id === userId ? { ...row, steam_id: null } : row)),
        )
        showToast('success', 'SteamID 绑定已解除')
      } catch (err) {
        showToast('error', formatApiError(err, '解除绑定失败'))
      } finally {
        setUnbindingUserIds((prev) => {
          const next = new Set(prev)
          next.delete(userId)
          return next
        })
      }
    },
    [showToast],
  )

  return {
    items,
    checkInConfig,
    loading,
    error,
    retryLoad,
    configForm,
    setConfigForm,
    savingConfig,
    savingRowKeys,
    unbindingUserIds,
    draftPoints,
    setDraftPoints,
    rowKey,
    handleSaveConfig,
    handleSavePoints,
    handleUnbind,
  }
}
