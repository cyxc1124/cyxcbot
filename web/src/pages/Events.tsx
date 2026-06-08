import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { getEvents } from '../api/client'
import type { SystemEvent } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { Pagination } from '../components/Pagination'
import { LevelBadge } from '../components/StatusBadge'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/format'

const PAGE_SIZE = 20
const LEVELS = ['', 'debug', 'info', 'warning', 'error']

export function EventsPage() {
  const [events, setEvents] = useState<SystemEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [level, setLevel] = useState('')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getEvents({
        page,
        page_size: PAGE_SIZE,
        level: level || undefined,
        category: category || undefined,
      })
      setEvents(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, level, category])

  useEffect(() => {
    void load()
  }, [load])

  const handleFilter = (e: FormEvent) => {
    e.preventDefault()
    setPage(1)
    void load()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">系统事件</h2>
        <p className="mt-1 text-sm text-slate-500">机器人运行事件时间线</p>
      </div>

      <form onSubmit={handleFilter} className="card flex flex-wrap items-end gap-4">
        <div className="min-w-[140px] flex-1">
          <label className="label" htmlFor="level">
            级别
          </label>
          <select
            id="level"
            className="input"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            <option value="">全部</option>
            {LEVELS.filter(Boolean).map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[160px] flex-1">
          <label className="label" htmlFor="category">
            分类
          </label>
          <input
            id="category"
            className="input"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="如 monitor, auth"
          />
        </div>
        <button type="submit" className="btn-primary">
          筛选
        </button>
      </form>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="card">
        {loading ? (
          <PageLoading />
        ) : error ? (
          <p className="py-8 text-center text-sm text-slate-500">数据暂时无法加载</p>
        ) : events.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">暂无事件记录</p>
        ) : (
          <ul className="space-y-0">
            {events.map((ev, i) => (
              <li
                key={ev.id}
                className={`flex gap-4 py-4 ${
                  i < events.length - 1
                    ? 'border-b border-slate-100 dark:border-slate-800'
                    : ''
                }`}
              >
                <div className="w-36 shrink-0 text-xs text-slate-500">
                  {formatDateTime(ev.created_at)}
                </div>
                <div className="w-20 shrink-0">
                  <LevelBadge level={ev.level} />
                </div>
                <div className="w-24 shrink-0 text-xs text-slate-500">{ev.category}</div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-800 dark:text-slate-200">{ev.message}</p>
                  {ev.details && (
                    <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                      {JSON.stringify(ev.details, null, 2)}
                    </pre>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        {!loading && (
          <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-800">
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  )
}
