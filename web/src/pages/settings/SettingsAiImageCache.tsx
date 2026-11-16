import { useCallback, useState } from 'react'
import { clearAiImageCache, getAiImageCache } from '../../api/client'
import type { AiImageCacheEntry, AiImageCachePage } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { PageLoading } from '../../components/LoadingSpinner'
import { Pagination } from '../../components/Pagination'
import { useToast } from '../../contexts/ToastContext'
import { useMountAsync } from '../../hooks/useMountAsync'
import { formatApiError } from '../../utils/apiError'
import { AiImageCacheCard } from './AiImageCacheCard'
import { AiImageCacheSettingsCard } from './AiImageCacheSettingsCard'

const PAGE_SIZE = 20

export function SettingsAiImageCachePage() {
  const { showToast } = useToast()
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AiImageCachePage | null>(null)
  const [error, setError] = useState('')
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)

  const load = useCallback(async () => {
    try {
      const result = await getAiImageCache(page, PAGE_SIZE)
      // 删除最后一页的最后一条后回到上一页。
      if (result.items.length === 0 && page > 1) {
        setPage(page - 1)
        return
      }
      setData(result)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    }
  }, [page])

  useMountAsync(load)

  const replace = (entry: AiImageCacheEntry) => {
    setData((current) => current && { ...current, items: current.items.map((item) => (item.id === entry.id ? entry : item)) })
  }

  const clear = async () => {
    setClearing(true)
    try {
      const { deleted } = await clearAiImageCache()
      setConfirmClear(false)
      showToast('success', `已清空 ${deleted} 条记录`)
      if (page === 1) await load()
      else setPage(1)
    } catch (err) {
      showToast('error', formatApiError(err, '清空失败'))
    } finally {
      setClearing(false)
    }
  }

  if (!data && !error) return <PageLoading />

  const total = data?.total ?? 0

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-sm text-muted-foreground">
        <p>
          同一张图片（按原始文件的 SHA-256 判断）再次被询问时，机器人直接回复这里保存的结果并注明来自此前的检测，不再调用 OpenAI
          或视觉模型，避免重复计费。只有所有检测都完成时才保存；有来源或模型失败、超时时，下次仍会重新检测。
        </p>
        <p>
          修改检测来源、OpenAI 密钥或视觉模型后，未修改的结果会在下次询问时重新检测（列表中标为「配置已变更」）。你修改过的回复始终沿用，
          并注明为管理员复核后的结果；删除一条记录后，下次询问会重新检测。
        </p>
        <p>
          每条记录只保存一张最长边 512 像素的预览图，不保存原图。未修改的记录超过下方设置的上限时，删除最久没有被询问的；修改过的记录不会被自动删除。
        </p>
      </div>

      <AiImageCacheSettingsCard onSaved={() => void load()} />

      {error && <LoadErrorBanner message={error} onRetry={() => void load()} />}

      {data && data.items.length === 0 ? (
        <div className="card text-sm text-muted-foreground">还没有缓存的检测结果。有人引用图片发送触发词并完成检测后，结果会出现在这里。</div>
      ) : (
        <div className="space-y-3">
          {data?.items.map((entry) => (
            <AiImageCacheCard key={entry.id} entry={entry} onSaved={replace} onDeleted={() => void load()} />
          ))}
        </div>
      )}

      {total > 0 && (
        <>
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          <div>
            <button type="button" className="btn-danger" disabled={clearing} onClick={() => setConfirmClear(true)}>
              清空全部缓存
            </button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmClear}
        title="清空检测缓存"
        message={`确定删除全部 ${total} 条记录？包括修改过的回复和所有预览图，删除后无法恢复；之后询问这些图片都会重新检测。`}
        confirmLabel="全部删除"
        loading={clearing}
        onCancel={() => { if (!clearing) setConfirmClear(false) }}
        onConfirm={() => void clear()}
      />
    </div>
  )
}
