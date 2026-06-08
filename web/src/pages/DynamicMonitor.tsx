import { useCallback, useEffect, useState } from 'react'
import {
  getDynamicMonitorStatus,
  triggerDynamicCheck,
  triggerDynamicFetch,
} from '../api/client'
import type { DynamicMonitorStatus } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { MonitorModeBadge } from '../components/MonitorModeBadge'
import { StatusBadge } from '../components/StatusBadge'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'
import { formatApiError } from '../utils/apiError'
import { formatDateTime } from '../utils/format'

export function DynamicMonitorPage() {
  const { showToast } = useToast()
  const [status, setStatus] = useState<DynamicMonitorStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getDynamicMonitorStatus()
      setStatus(data)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [load])

  const runAction = async (action: 'check' | 'fetch') => {
    setActionLoading(action)
    try {
      const fn = action === 'check' ? triggerDynamicCheck : triggerDynamicFetch
      const result = await fn()
      showToast(result.success ? 'success' : 'error', result.message)
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '操作失败')
    } finally {
      setActionLoading('')
    }
  }

  if (loading && !status && !error) return <PageLoading />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">动态监控</h2>
          <p className="mt-1 text-sm text-slate-500">UP 主动态检测、推送与映射管理</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={!!actionLoading}
            onClick={() => runAction('check')}
          >
            {actionLoading === 'check' ? '检查中…' : '立即检查'}
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!!actionLoading}
            onClick={() => runAction('fetch')}
          >
            {actionLoading === 'fetch' ? '拉取中…' : '强制拉取'}
          </button>
        </div>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="card">
        <div className="mb-6 flex items-center gap-3">
          <h3 className="text-lg font-semibold">运行状态</h3>
          <StatusBadge active={status?.enabled ?? false} />
          <MonitorModeBadge mode="api-polling" />
        </div>

        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-sm text-slate-500">监控目标数</dt>
            <dd className="mt-1 text-xl font-semibold">{status?.target_count ?? '—'}</dd>
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
            <dt className="text-sm text-slate-500">新动态推送</dt>
            <dd className="mt-1 text-xl font-semibold">{status?.new_dynamics_total ?? 0}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">上次检查</dt>
            <dd className="mt-1 text-sm">{formatDateTime(status?.last_check_at)}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">上次拉取</dt>
            <dd className="mt-1 text-sm">{formatDateTime(status?.last_fetch_at)}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">监控模式</dt>
            <dd className="mt-1 text-sm">API 轮询</dd>
          </div>
        </dl>

        {status?.last_error && (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <strong>最近错误：</strong> {status.last_error}
          </div>
        )}
      </div>

      <div className="card">
        <TargetMappingSection type="dynamic" />
      </div>
    </div>
  )
}
