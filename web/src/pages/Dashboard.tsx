import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getConnectionsStatus,
  getEvents,
  getMonitorStatus,
  getSystemMonitorStatus,
} from '../api/client'
import type {
  BilibiliConnectionStatus,
  ConnectionsStatus,
  QqConnectionStatus,
  SystemEvent,
  SystemMonitorStatus,
} from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { ResourceUsageCard } from '../components/ResourceUsageCard'
import { StatCard } from '../components/StatCard'
import { LevelBadge } from '../components/StatusBadge'
import { useLiveUptime } from '../hooks/useLiveUptime'
import { formatApiError } from '../utils/apiError'
import { formatDateTime, formatMemoryUsage, formatUptime } from '../utils/format'

function bilibiliCardValue(b: BilibiliConnectionStatus | undefined): string {
  if (!b) return '—'
  if (b.logged_in) return b.username || '已登录'
  return '未登录'
}

function bilibiliSettingsLink(action = '登录') {
  return (
    <>
      前往
      <Link to="/settings/account" className="font-medium text-primary hover:opacity-80 hover:underline">
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
  const [system, setSystem] = useState<SystemMonitorStatus | null>(null)
  const [connections, setConnections] = useState<ConnectionsStatus | null>(null)
  const [events, setEvents] = useState<SystemEvent[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [status, sys, conn, ev] = await Promise.all([
        getMonitorStatus(),
        getSystemMonitorStatus(),
        getConnectionsStatus(),
        getEvents({ page: 1, page_size: 8 }),
      ])
      setRunning(status.running)
      setUptime(status.uptime_seconds)
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

  if (loading && !connections && !error) return <PageLoading />

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground">仪表盘</h2>
        <p className="mt-1 text-sm text-muted-foreground">系统运行状态总览</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

      <div className="grid gap-4 sm:grid-cols-3">
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
      </div>

      <section>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="font-semibold text-foreground">资源使用</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">每 30 秒自动刷新</p>
          </div>
          {system && (
            <p className="text-xs text-muted-foreground">
              {system.bot_version} · Python {system.python_version}
            </p>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <ResourceUsageCard label="CPU" percent={system?.cpu_percent} detail="处理器占用" />
          <ResourceUsageCard
            label="内存"
            percent={system?.memory_percent}
            detail={
              system
                ? formatMemoryUsage(system.memory_used_mb, system.memory_total_mb)
                : undefined
            }
          />
          <ResourceUsageCard label="磁盘" percent={system?.disk_percent} detail="根分区占用" />
        </div>
      </section>

      <div className="card">
        <h3 className="mb-4 font-semibold text-foreground">最近事件</h3>
        {error ? (
          <p className="text-sm text-muted-foreground">数据暂时无法加载</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无事件记录</p>
        ) : (
          <ul className="space-y-3">
            {events.map((ev) => (
              <li
                key={ev.id}
                className="flex items-start gap-3 border-b border-border pb-3 last:border-0 border-border"
              >
                <LevelBadge level={ev.level} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-foreground text-foreground">
                    {ev.message}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {ev.category} · {formatDateTime(ev.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
