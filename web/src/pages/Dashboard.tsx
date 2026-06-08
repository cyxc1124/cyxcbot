import { useCallback, useEffect, useState } from 'react'
import {
  getDynamicMonitorStatus,
  getEvents,
  getLiveMonitorStatus,
  getMonitorStatus,
  getSystemMonitorStatus,
} from '../api/client'
import type { DynamicMonitorStatus, LiveMonitorStatus, SystemEvent, SystemMonitorStatus } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { PageLoading } from '../components/LoadingSpinner'
import { StatCard } from '../components/StatCard'
import { LevelBadge, StatusBadge } from '../components/StatusBadge'
import { formatDateTime, formatPercent, formatUptime } from '../utils/format'

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [uptime, setUptime] = useState(0)
  const [dynamic, setDynamic] = useState<DynamicMonitorStatus | null>(null)
  const [live, setLive] = useState<LiveMonitorStatus | null>(null)
  const [system, setSystem] = useState<SystemMonitorStatus | null>(null)
  const [events, setEvents] = useState<SystemEvent[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [status, dyn, liv, sys, ev] = await Promise.all([
        getMonitorStatus(),
        getDynamicMonitorStatus(),
        getLiveMonitorStatus(),
        getSystemMonitorStatus(),
        getEvents({ page: 1, page_size: 8 }),
      ])
      setRunning(status.running)
      setUptime(status.uptime_seconds)
      setDynamic(dyn)
      setLive(liv)
      setSystem(sys)
      setEvents(ev.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [load])

  if (loading && !dynamic) return <PageLoading />

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">仪表盘</h2>
        <p className="mt-1 text-sm text-slate-500">系统运行状态总览</p>
      </div>

      {error && <ErrorAlert message={error} onRetry={load} />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="机器人状态"
          value={running ? '运行中' : '已停止'}
          subtitle={`运行时长 ${formatUptime(uptime)}`}
          icon="🤖"
        />
        <StatCard
          title="动态监控"
          value={dynamic?.target_count ?? '—'}
          subtitle={`间隔 ${dynamic?.interval_seconds ?? '—'} 秒 · 检查 ${dynamic?.checks_total ?? 0} 次`}
          icon="📰"
        />
        <StatCard
          title="直播监控"
          value={live?.live_rooms ?? 0}
          subtitle={`${live?.target_count ?? 0} 个房间 · 检查 ${live?.checks_total ?? 0} 次`}
          icon="📺"
        />
        <StatCard
          title="内存使用"
          value={system ? formatPercent(system.memory_percent) : '—'}
          subtitle={
            system
              ? `${system.memory_used_mb.toFixed(0)} / ${system.memory_total_mb.toFixed(0)} MB`
              : undefined
          }
          icon="💾"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-4 font-semibold text-slate-900 dark:text-white">监控概览</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">动态监控</dt>
              <dd className="flex items-center gap-2">
                <StatusBadge active={dynamic?.enabled ?? false} />
                <span className="text-slate-700 dark:text-slate-300">
                  上次检查 {formatDateTime(dynamic?.last_check_at)}
                </span>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">直播监控</dt>
              <dd className="flex items-center gap-2">
                <StatusBadge active={live?.enabled ?? false} />
                <span className="text-slate-700 dark:text-slate-300">
                  {live?.use_websocket ? 'WebSocket' : '轮询'} · 上次 {formatDateTime(live?.last_check_at)}
                </span>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">CPU</dt>
              <dd>{system ? formatPercent(system.cpu_percent) : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">磁盘</dt>
              <dd>{system ? formatPercent(system.disk_percent) : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">版本</dt>
              <dd className="text-slate-700 dark:text-slate-300">
                {system?.bot_version ?? '—'} · Python {system?.python_version ?? '—'}
              </dd>
            </div>
          </dl>
        </div>

        <div className="card">
          <h3 className="mb-4 font-semibold text-slate-900 dark:text-white">最近事件</h3>
          {events.length === 0 ? (
            <p className="text-sm text-slate-500">暂无事件记录</p>
          ) : (
            <ul className="space-y-3">
              {events.map((ev) => (
                <li
                  key={ev.id}
                  className="flex items-start gap-3 border-b border-slate-100 pb-3 last:border-0 dark:border-slate-800"
                >
                  <LevelBadge level={ev.level} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-slate-800 dark:text-slate-200">
                      {ev.message}
                    </p>
                    <p className="text-xs text-slate-500">
                      {ev.category} · {formatDateTime(ev.created_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
