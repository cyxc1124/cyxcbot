import { useCallback, useEffect, useState } from 'react'
import { getLiveMonitorStatus, triggerLiveCheck } from '../api/client'
import type { LiveMonitorStatus } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { PageLoading } from '../components/LoadingSpinner'
import {
  getLiveMonitorMode,
  getLiveMonitorModeLabel,
  MonitorModeBadge,
} from '../components/MonitorModeBadge'
import { StatusBadge } from '../components/StatusBadge'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'
import { formatDateTime } from '../utils/format'

export function LiveMonitorPage() {
  const { showToast } = useToast()
  const [status, setStatus] = useState<LiveMonitorStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getLiveMonitorStatus()
      setStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [load])

  const handleCheck = async () => {
    setChecking(true)
    try {
      const result = await triggerLiveCheck()
      showToast(result.success ? 'success' : 'error', result.message)
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '操作失败')
    } finally {
      setChecking(false)
    }
  }

  if (loading && !status) return <PageLoading />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">直播监控</h2>
          <p className="mt-1 text-sm text-slate-500">B 站直播间状态检测、开播通知与映射管理</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          disabled={checking}
          onClick={handleCheck}
        >
          {checking ? '检查中…' : '立即检查'}
        </button>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      <div className="card">
        <div className="mb-6 flex items-center gap-3">
          <h3 className="text-lg font-semibold">运行状态</h3>
          <StatusBadge active={status?.enabled ?? false} />
          {status && (
            <MonitorModeBadge mode={getLiveMonitorMode(status.use_websocket)} />
          )}
        </div>

        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-sm text-slate-500">监控房间数</dt>
            <dd className="mt-1 text-xl font-semibold">{status?.target_count ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">正在直播</dt>
            <dd className="mt-1 text-xl font-semibold text-emerald-600">
              {status?.live_rooms ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">检查间隔</dt>
            <dd className="mt-1 text-xl font-semibold">{status?.interval_seconds ?? '—'} 秒</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">累计检查</dt>
            <dd className="mt-1 text-xl font-semibold">{status?.checks_total ?? 0}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">上次检查</dt>
            <dd className="mt-1 text-sm">{formatDateTime(status?.last_check_at)}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">监控模式</dt>
            <dd className="mt-1 text-sm">
              {status ? getLiveMonitorModeLabel(status.use_websocket) : '—'}
            </dd>
          </div>
        </dl>

        {status?.last_error && (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <strong>最近错误：</strong> {status.last_error}
          </div>
        )}
      </div>

      <div className="card">
        <TargetMappingSection type="live" />
      </div>
    </div>
  )
}
