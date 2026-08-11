import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { createRetryHandler } from '../utils/retryLoad'
import { Link } from 'react-router-dom'
import {
  getConnectionsStatus,
  getDynamicMonitorStatus,
  getLiveMonitorStatus,
  getMonitorStatus,
  getSystemMonitorStatus,
  getXMonitorStatus,
} from '../api/client'
import type {
  BilibiliConnectionStatus,
  ConnectionsStatus,
  DynamicMonitorStatus,
  LiveMonitorStatus,
  QqConnectionStatus,
  SystemMonitorStatus,
  XMonitorStatus,
} from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { ResourceUsageCard } from '../components/ResourceUsageCard'
import { StatCard } from '../components/StatCard'
import { useLiveUptime } from '../hooks/useLiveUptime'
import { useMountAsync } from '../hooks/useMountAsync'
import { formatApiError } from '../utils/apiError'
import { formatDateTime, formatMemoryMb, formatMemoryUsage, formatStorageSize, formatUptime } from '../utils/format'

function formatCount(value: number | undefined | null): string {
  if (value == null) return '—'
  return value.toLocaleString('zh-CN')
}

function monitorRunningLabel(enabled: boolean | undefined): string {
  if (enabled == null) return '—'
  return enabled ? '运行中' : '已停止'
}

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
  const [loading, setLoading] = useLoadingOnKeyChange('dashboard')
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const [uptime, setUptime] = useState(0)
  const [system, setSystem] = useState<SystemMonitorStatus | null>(null)
  const [connections, setConnections] = useState<ConnectionsStatus | null>(null)
  const [dynamicMonitor, setDynamicMonitor] = useState<DynamicMonitorStatus | null>(null)
  const [liveMonitor, setLiveMonitor] = useState<LiveMonitorStatus | null>(null)
  const [xMonitor, setXMonitor] = useState<XMonitorStatus | null>(null)

  const load = useCallback(async () => {
    try {
      const [status, sys, conn, dynamic, live, x] = await Promise.all([
        getMonitorStatus(),
        getSystemMonitorStatus(),
        getConnectionsStatus(),
        getDynamicMonitorStatus(),
        getLiveMonitorStatus(),
        getXMonitorStatus(),
      ])
      setRunning(status.running)
      setUptime(status.uptime_seconds)
      setSystem(sys)
      setConnections(conn)
      setDynamicMonitor(dynamic)
      setLiveMonitor(live)
      setXMonitor(x)
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  useMountAsync(load)

  useEffect(() => {
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

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          title="机器草状态"
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
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">监控统计</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            自本次启动累计 · 每 30 秒自动刷新
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatCard
            title="动态监控"
            value={monitorRunningLabel(dynamicMonitor?.enabled)}
            subtitle={[
              dynamicMonitor ? `${dynamicMonitor.target_count} 个 UP 主` : undefined,
              dynamicMonitor?.last_check_at
                ? `最近检查 ${formatDateTime(dynamicMonitor.last_check_at)}`
                : undefined,
              <>
                管理订阅见
                <Link to="/dynamic" className="font-medium text-primary hover:opacity-80 hover:underline">
                  动态监控
                </Link>
              </>,
            ].filter(Boolean)}
          />
          <StatCard
            title="动态检查次数"
            value={formatCount(dynamicMonitor?.checks_total)}
            subtitle="每个 UP 主每次轮询计 1 次"
          />
          <StatCard
            title="新动态发现"
            value={formatCount(dynamicMonitor?.new_dynamics_total)}
            subtitle="不含首次基准初始化"
          />
          <StatCard
            title="直播监控"
            value={monitorRunningLabel(liveMonitor?.enabled)}
            subtitle={[
              liveMonitor ? `${liveMonitor.target_count} 个直播间` : undefined,
              liveMonitor?.last_check_at
                ? `最近检查 ${formatDateTime(liveMonitor.last_check_at)}`
                : undefined,
              <>
                管理订阅见
                <Link to="/live" className="font-medium text-primary hover:opacity-80 hover:underline">
                  直播监控
                </Link>
              </>,
            ].filter(Boolean)}
          />
          <StatCard
            title="直播检查次数"
            value={formatCount(liveMonitor?.checks_total)}
            subtitle="每个直播间每次轮询计 1 次"
          />
          <StatCard
            title="当前开播"
            value={formatCount(liveMonitor?.live_rooms)}
            subtitle="正在直播的房间数"
          />
          <StatCard
            title="X 监控"
            value={monitorRunningLabel(xMonitor?.enabled)}
            subtitle={[
              xMonitor ? `${xMonitor.target_count} 个博主` : undefined,
              xMonitor?.last_check_at
                ? `最近检查 ${formatDateTime(xMonitor.last_check_at)}`
                : undefined,
              <>
                管理订阅见
                <Link to="/x" className="font-medium text-primary hover:opacity-80 hover:underline">
                  推文订阅
                </Link>
              </>,
            ].filter(Boolean)}
          />
          <StatCard
            title="X 检查次数"
            value={formatCount(xMonitor?.checks_total)}
            subtitle="每个博主每次轮询计 1 次"
          />
          <StatCard
            title="新推文发现"
            value={formatCount(xMonitor?.new_tweets_total)}
            subtitle="不含首次基准初始化"
          />
        </div>
      </section>

      <section>
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">进程资源</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">本进程实际消耗 · 每 30 秒自动刷新</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <ResourceUsageCard
            label="进程 CPU"
            percent={
              system && system.cpu_count > 0
                ? system.process_cpu_percent / system.cpu_count
                : null
            }
            displayValue={
              system ? `${system.process_cpu_percent.toFixed(1)}%` : undefined
            }
            detail={
              system ? `${system.cpu_count} 核` : undefined
            }
          />
          <ResourceUsageCard
            label="进程内存 (RSS)"
            percent={
              system && (system.memory_limit_mb || system.memory_total_mb) > 0
                ? (system.process_memory_mb / (system.memory_limit_mb || system.memory_total_mb)) * 100
                : null
            }
            detail={
              system
                ? `常驻集 ${formatMemoryMb(system.process_memory_mb)}`
                : undefined
            }
          />
          <ResourceUsageCard
            label="数据库"
            percent={null}
            detail={system ? formatStorageSize(system.db_size_mb) : undefined}
          />
          <ResourceUsageCard
            label="日志"
            percent={null}
            detail={system ? formatStorageSize(system.log_size_mb) : undefined}
          />
        </div>
      </section>

      <section>
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">系统资源</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">整机参考指标</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <ResourceUsageCard label="系统 CPU" percent={system?.cpu_percent} detail="整机处理器占用" />
          <ResourceUsageCard
            label="系统内存"
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
    </div>
  )
}
