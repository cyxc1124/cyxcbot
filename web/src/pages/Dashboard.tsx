import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getConnectionsStatus,
  getDynamicMonitorStatus,
  getEvents,
  getLiveMonitorStatus,
  getMonitorStatus,
  getSystemMonitorStatus,
} from '../api/client'
import type {
  BilibiliConnectionStatus,
  ConnectionsStatus,
  DynamicMonitorStatus,
  LiveMonitorStatus,
  QqConnectionStatus,
  SystemEvent,
  SystemMonitorStatus,
} from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { StatCard } from '../components/StatCard'
import { getLiveMonitorMode, MonitorModeBadge } from '../components/MonitorModeBadge'
import { LevelBadge, StatusBadge } from '../components/StatusBadge'
import { useLiveUptime } from '../hooks/useLiveUptime'
import { formatApiError } from '../utils/apiError'
import { formatDateTime, formatPercent, formatUptime } from '../utils/format'

function bilibiliCardValue(b: BilibiliConnectionStatus | undefined): string {
  if (!b) return '—'
  if (b.logged_in) return b.username || '已登录'
  return '未登录'
}

function bilibiliSettingsLink(action = '登录') {
  return (
    <>
      前往
      <Link to="/settings" className="font-medium text-brand-600 hover:text-brand-700 hover:underline dark:text-brand-400">
      系统设置
      </Link>
      {action}
    </>
  )
}

function bilibiliCardSubtitle(b: BilibiliConnectionStatus | undefined) {
  if (!b) return undefined

  if (b.status === 'logged_in') {
    return b.uid ? `UID ${b.uid}` : undefined
  }

  switch (b.status) {
    case 'not_configured':
      return bilibiliSettingsLink()
    case 'session_expired':
      return <>登录已失效 · {bilibiliSettingsLink('重新登录')}</>
    case 'verify_failed':
      return <>无法验证登录状态 · {bilibiliSettingsLink('重新登录')}</>
  }
}

function qqCardValue(q: QqConnectionStatus | undefined): string {
  if (!q) return '—'
  if (!q.connected) return '未连接'
  if (q.bot_count === 1 && q.bots[0]) {
    return q.bots[0].nickname || q.bots[0].qq
  }
  return `${q.bot_count} 个账号`
}

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [uptime, setUptime] = useState(0)
  const [dynamic, setDynamic] = useState<DynamicMonitorStatus | null>(null)
  const [live, setLive] = useState<LiveMonitorStatus | null>(null)
  const [system, setSystem] = useState<SystemMonitorStatus | null>(null)
  const [connections, setConnections] = useState<ConnectionsStatus | null>(null)
  const [events, setEvents] = useState<SystemEvent[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [status, dyn, liv, sys, conn, ev] = await Promise.all([
        getMonitorStatus(),
        getDynamicMonitorStatus(),
        getLiveMonitorStatus(),
        getSystemMonitorStatus(),
        getConnectionsStatus(),
        getEvents({ page: 1, page_size: 8 }),
      ])
      setRunning(status.running)
      setUptime(status.uptime_seconds)
      setDynamic(dyn)
      setLive(liv)
      setSystem(sys)
      setConnections(conn)
      setEvents(ev.items)
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [load])

  const liveUptime = useLiveUptime(uptime, running)

  if (loading && !dynamic && !error) return <PageLoading />

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">仪表盘</h2>
        <p className="mt-1 text-sm text-slate-500">系统运行状态总览</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          title="机器人状态"
          value={running ? '运行中' : '已停止'}
          subtitle={`已运行 ${formatUptime(liveUptime)}`}
        />
        <StatCard
          title="B 站账号"
          value={bilibiliCardValue(connections?.bilibili)}
          subtitle={bilibiliCardSubtitle(connections?.bilibili)}
        />
        <StatCard
          title="QQ 登录"
          value={qqCardValue(connections?.qq)}
          subtitle={connections?.qq.message}
        />
        <StatCard
          title="动态监控"
          value={dynamic?.target_count ?? '—'}
          subtitle={`间隔 ${dynamic?.interval_seconds ?? '—'} 秒 · 检查 ${dynamic?.checks_total ?? 0} 次`}
        />
        <StatCard
          title="直播监控"
          value={live?.live_rooms ?? 0}
          subtitle={`${live?.target_count ?? 0} 个房间 · 检查 ${live?.checks_total ?? 0} 次`}
        />
        <StatCard
          title="内存使用"
          value={system ? formatPercent(system.memory_percent) : '—'}
          subtitle={
            system
              ? `${system.memory_used_mb.toFixed(0)} / ${system.memory_total_mb.toFixed(0)} MB`
              : undefined
          }
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
                <MonitorModeBadge mode="api-polling" />
                <span className="text-slate-700 dark:text-slate-300">
                  上次检查 {formatDateTime(dynamic?.last_check_at)}
                </span>
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">直播监控</dt>
              <dd className="flex items-center gap-2">
                <StatusBadge active={live?.enabled ?? false} />
                {live && (
                  <MonitorModeBadge mode={getLiveMonitorMode(live.use_websocket)} />
                )}
                <span className="text-slate-700 dark:text-slate-300">
                  上次 {formatDateTime(live?.last_check_at)}
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
          {error ? (
            <p className="text-sm text-slate-500">数据暂时无法加载</p>
          ) : events.length === 0 ? (
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
