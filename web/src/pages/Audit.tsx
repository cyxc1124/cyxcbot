import { useCallback, useMemo, useState, type FormEvent } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getAuditLogs } from '../api/client'
import type { AuditLog } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { Pagination } from '../components/Pagination'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/format'

const PAGE_SIZE = 20

export function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const loadKey = `${page}|${action}|${from}|${to}`
  const [loading, setLoading] = useLoadingOnKeyChange(loadKey)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await getAuditLogs({
        page,
        page_size: PAGE_SIZE,
        action: action || undefined,
        from: from || undefined,
        to: to || undefined,
      })
      setLogs(data.items)
      setTotal(data.total)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, action, from, to, setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  const handleFilter = (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">审计日志</h2>
        <p className="mt-1 text-sm text-muted-foreground">管理员操作记录</p>
      </div>

      <form onSubmit={handleFilter} className="card flex flex-wrap items-end gap-4">
        <div className="min-w-[160px] flex-1">
          <label className="label" htmlFor="action">
            操作类型
          </label>
          <input
            id="action"
            className="input"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="如 login, settings.update"
          />
        </div>
        <div className="min-w-[160px] flex-1">
          <label className="label" htmlFor="from">
            开始时间
          </label>
          <input
            id="from"
            type="datetime-local"
            className="input"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className="min-w-[160px] flex-1">
          <label className="label" htmlFor="to">
            结束时间
          </label>
          <input
            id="to"
            type="datetime-local"
            className="input"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary">
          筛选
        </button>
      </form>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="card overflow-x-auto">
        {loading ? (
          <PageLoading />
        ) : (
          <>
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-muted-foreground border-border">
                  <th className="pb-3 pr-4 font-medium">时间</th>
                  <th className="pb-3 pr-4 font-medium">操作</th>
                  <th className="pb-3 pr-4 font-medium">操作者</th>
                  <th className="pb-3 pr-4 font-medium">资源</th>
                  <th className="pb-3 pr-4 font-medium">IP</th>
                  <th className="pb-3 font-medium">详情</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="border-b border-border"
                  >
                    <td className="py-3 pr-4 whitespace-nowrap text-muted-foreground">
                      {formatDateTime(log.created_at)}
                    </td>
                    <td className="py-3 pr-4 font-medium">{log.action}</td>
                    <td className="py-3 pr-4">{log.actor}</td>
                    <td className="py-3 pr-4 text-xs text-muted-foreground">
                      {log.resource_type
                        ? `${log.resource_type}${log.resource_id ? `#${log.resource_id}` : ''}`
                        : '—'}
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs">{log.ip_address ?? '—'}</td>
                    <td className="py-3 max-w-xs truncate text-xs text-muted-foreground">
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logs.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {error ? '数据暂时无法加载' : '暂无审计记录'}
              </p>
            )}
            <div className="mt-4">
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={total}
                onPageChange={setPage}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
