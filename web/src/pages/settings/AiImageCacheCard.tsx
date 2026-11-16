import { useEffect, useState } from 'react'
import { deleteAiImageCacheEntry, getAiImageCachePreview, updateAiImageCacheEntry } from '../../api/client'
import type { AiImageCacheEntry } from '../../api/types'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Icon } from '../../components/Icon'
import { useToast } from '../../contexts/ToastContext'
import { formatApiError } from '../../utils/apiError'
import { formatDateTime, formatStorageSize } from '../../utils/format'

/** 需与 admin/api/v1/ai_image_cache.py 的 MAX_RESULT_LENGTH 保持一致 */
const MAX_RESULT_LENGTH = 4000

const BADGE = 'rounded bg-amber-500/15 px-1.5 py-px text-[10px] font-medium text-amber-600 dark:text-amber-400'

/** 收起时用回复中的「结论：」一行作为标题。 */
function conclusionOf(result: string): string {
  const lines = result.split('\n').map((line) => line.trim()).filter(Boolean)
  return lines.find((line) => line.startsWith('结论：')) ?? lines[0] ?? ''
}

function usePreview(entry: AiImageCacheEntry): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!entry.has_preview) return
    const controller = new AbortController()
    let objectUrl: string | null = null
    getAiImageCachePreview(entry.id, controller.signal)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {})
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [entry.id, entry.has_preview])
  return url
}

export function AiImageCacheCard({ entry, onSaved, onDeleted }: {
  entry: AiImageCacheEntry
  onSaved: (entry: AiImageCacheEntry) => void
  onDeleted: () => void
}) {
  const { showToast } = useToast()
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState(entry.result)
  const [busy, setBusy] = useState<'save' | 'delete' | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const preview = usePreview(entry)
  const id = (field: string) => `ai-cache-${entry.id}-${field}`
  const dirty = draft.trim() !== entry.result

  const save = async () => {
    const result = draft.trim()
    if (!result) {
      showToast('error', '回复内容不能为空')
      return
    }
    setBusy('save')
    try {
      const saved = await updateAiImageCacheEntry(entry.id, result)
      setDraft(saved.result)
      onSaved(saved)
      showToast('success', '已保存，之后询问这张图片会回复修改后的内容')
    } catch (err) {
      showToast('error', formatApiError(err, '保存失败'))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    setBusy('delete')
    try {
      await deleteAiImageCacheEntry(entry.id)
      setConfirmDelete(false)
      showToast('success', '已删除，之后询问这张图片会重新检测')
      onDeleted()
    } catch (err) {
      showToast('error', formatApiError(err, '删除失败'))
    } finally {
      setBusy(null)
    }
  }

  const image = (className: string) => preview
    ? <img src={preview} alt="检测过的图片" className={`${className} rounded-md border border-border bg-muted object-contain`} />
    : (
      <span className={`${className} flex items-center justify-center rounded-md border border-dashed border-border text-[10px] text-muted-foreground`}>
        {entry.has_preview ? '加载中' : '无预览'}
      </span>
    )

  return (
    <div className="card">
      <button type="button" className="flex w-full min-w-0 items-center gap-3 rounded-lg text-left"
        aria-expanded={expanded} aria-controls={id('body')} onClick={() => setExpanded(!expanded)}>
        <Icon name="chevron-down" className={`size-4 shrink-0 text-muted-foreground transition-transform ${expanded ? '' : '-rotate-90'}`} />
        {image('size-12 shrink-0')}
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="truncate font-medium text-foreground">{conclusionOf(entry.result)}</span>
            {entry.edited && <span className={BADGE}>已修改</span>}
            {entry.stale && <span className={BADGE}>配置已变更</span>}
            {dirty && <span className={BADGE}>有未保存修改</span>}
          </span>
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {entry.sha256.slice(0, 12)} · {formatDateTime(entry.created_at)} 检测 · 复用 {entry.hit_count} 次
          </span>
        </span>
      </button>

      {expanded && (
        <div id={id('body')} className="mt-4 grid gap-4 border-t border-border pt-4 md:grid-cols-[minmax(0,320px)_1fr]">
          <div className="space-y-3">
            {image('max-h-80 min-h-32 w-full')}
            <dl className="space-y-1 text-xs text-muted-foreground">
              <div><dt className="inline">SHA-256：</dt><dd className="inline break-all font-mono">{entry.sha256}</dd></div>
              <div><dt className="inline">原图：</dt><dd className="inline">{entry.media_type} · {formatStorageSize(entry.size_bytes / 1024 / 1024)}</dd></div>
              <div><dt className="inline">检测时间：</dt><dd className="inline">{formatDateTime(entry.created_at)}</dd></div>
              <div><dt className="inline">最近询问：</dt><dd className="inline">{formatDateTime(entry.used_at)}（复用 {entry.hit_count} 次）</dd></div>
              {entry.edited_at && <div><dt className="inline">修改时间：</dt><dd className="inline">{formatDateTime(entry.edited_at)}</dd></div>}
            </dl>
            {entry.stale && (
              <p className="text-xs text-amber-600 dark:text-amber-400">检测配置已变更，下次有人询问这张图片时会重新检测并覆盖此结果。</p>
            )}
          </div>
          <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); void save() }}>
            <label className="label" htmlFor={id('result')}>回复内容</label>
            <textarea id={id('result')} className="input min-h-64 text-sm" value={draft} maxLength={MAX_RESULT_LENGTH}
              disabled={busy !== null} onChange={(event) => setDraft(event.target.value)} />
            <p className="text-xs text-muted-foreground">
              保存后，再次询问这张图片会回复这里的内容，并注明为管理员复核后的结果；修改过的结果不会因检测配置变化而重新检测，也不会被自动清理。
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button type="submit" className="btn-primary" disabled={busy !== null || !dirty}>
                {busy === 'save' ? '保存中…' : '保存修改'}
              </button>
              <button type="button" className="btn-secondary" disabled={busy !== null || !dirty} onClick={() => setDraft(entry.result)}>
                放弃修改
              </button>
              <button type="button" className="btn-danger ml-auto" disabled={busy !== null} onClick={() => setConfirmDelete(true)}>
                删除
              </button>
            </div>
          </form>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title="删除检测记录"
        message="确定删除这条记录？保存的预览图和回复内容会一并删除；之后有人询问这张图片时会重新检测。"
        confirmLabel="删除"
        loading={busy === 'delete'}
        onCancel={() => { if (busy !== 'delete') setConfirmDelete(false) }}
        onConfirm={() => void remove()}
      />
    </div>
  )
}
