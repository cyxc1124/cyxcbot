import { useCallback, useEffect, useRef, useState } from 'react'
import { createLogsWebSocket, getRecentLogs } from '../api/client'
import type { RuntimeLogEntry } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { formatApiError } from '../utils/apiError'

const DISPLAY_MAX = 1500
const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const
type LogLevel = (typeof LEVELS)[number]

const LEVEL_CLASS: Record<string, string> = {
  TRACE: 'text-muted-foreground',
  DEBUG: 'text-muted-foreground',
  INFO: 'text-primary',
  SUCCESS: 'text-emerald-600 dark:text-emerald-400',
  WARNING: 'text-amber-600 dark:text-amber-400',
  ERROR: 'text-red-600 dark:text-red-400',
  CRITICAL: 'text-red-700 dark:text-red-300 font-semibold',
}

type ConnectionState = 'connecting' | 'connected' | 'disconnected'

function trimLogs(items: RuntimeLogEntry[]): RuntimeLogEntry[] {
  if (items.length <= DISPLAY_MAX) return items
  return items.slice(items.length - DISPLAY_MAX)
}

function LogLine({ entry }: { entry: RuntimeLogEntry }) {
  const levelClass = LEVEL_CLASS[entry.level.toUpperCase()] ?? LEVEL_CLASS.INFO
  return (
    <div className="whitespace-pre-wrap break-all font-mono text-xs leading-5">
      <span className="log-line-ts">{entry.ts}</span>
      {' '}
      <span className={levelClass}>{entry.level.padEnd(7)}</span>
      <span className="log-line-logger"> {entry.logger} | </span>
      <span className="log-line-msg">{entry.message}</span>
    </div>
  )
}

export function LogsPage() {
  const [logs, setLogs] = useState<RuntimeLogEntry[]>([])
  const [buffered, setBuffered] = useState(0)
  const [minLevel, setMinLevel] = useState<LogLevel>('INFO')
  const [autoScroll, setAutoScroll] = useState(true)
  const [paused, setPaused] = useState(false)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [error, setError] = useState('')

  const containerRef = useRef<HTMLDivElement>(null)
  const pausedBufferRef = useRef<RuntimeLogEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const appendLogs = useCallback((incoming: RuntimeLogEntry[]) => {
    if (!incoming.length) return
    if (paused) {
      pausedBufferRef.current.push(...incoming)
      return
    }
    setLogs((prev) => trimLogs([...prev, ...incoming]))
  }, [paused])

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [])

  useEffect(() => {
    if (autoScroll && !paused) {
      scrollToBottom()
    }
  }, [logs, autoScroll, paused, scrollToBottom])

  useEffect(() => {
    let cancelled = false
    let reconnectTimer: number | undefined

    const connect = () => {
      if (cancelled) return
      setConnection('connecting')
      setError('')

      try {
        const ws = createLogsWebSocket(minLevel)
        wsRef.current = ws

        ws.onopen = () => {
          if (cancelled) return
          setConnection('connected')
        }

        ws.onmessage = (event) => {
          if (cancelled) return
          try {
            const payload = JSON.parse(String(event.data)) as RuntimeLogEntry
            appendLogs([payload])
          } catch {
            // ignore malformed frames
          }
        }

        ws.onerror = () => {
          if (cancelled) return
          setConnection('disconnected')
        }

        ws.onclose = () => {
          if (cancelled) return
          setConnection('disconnected')
          reconnectTimer = window.setTimeout(connect, 3000)
        }
      } catch (err) {
        setConnection('disconnected')
        setError(formatApiError(err, '无法建立日志连接'))
      }
    }

    void getRecentLogs({ limit: 500, min_level: minLevel })
      .then((data) => {
        if (cancelled) return
        setLogs(trimLogs(data.items))
        setBuffered(data.total_buffered)
      })
      .catch((err) => {
        if (cancelled) return
        setError(formatApiError(err, '加载历史日志失败'))
      })
      .finally(() => {
        if (!cancelled) connect()
      })

    return () => {
      cancelled = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [minLevel, appendLogs])

  const handleTogglePause = () => {
    setPaused((prev) => {
      if (prev) {
        const pending = pausedBufferRef.current
        pausedBufferRef.current = []
        if (pending.length) {
          setLogs((current) => trimLogs([...current, ...pending]))
        }
      }
      return !prev
    })
  }

  const handleClear = () => {
    pausedBufferRef.current = []
    setLogs([])
  }

  const connectionLabel =
    connection === 'connected' ? '实时连接中' : connection === 'connecting' ? '连接中…' : '已断开，重试中'

  const connectionClass =
    connection === 'connected'
      ? 'badge-success'
      : connection === 'connecting'
        ? 'badge-warning'
        : 'badge-danger'

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">运行日志</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            实时查看 Bot 控制台输出，内存保留最近约 {DISPLAY_MAX.toLocaleString()} 条
          </p>
        </div>
        <span className={`badge ${connectionClass}`}>{connectionLabel}</span>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <div className="card flex flex-wrap items-end gap-3">
        <div className="min-w-[140px]">
          <label className="label" htmlFor="log-level">
            最低级别
          </label>
          <select
            id="log-level"
            className="input"
            value={minLevel}
            onChange={(e) => setMinLevel(e.target.value as LogLevel)}
          >
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 pb-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-input"
          />
          自动滚到底部
        </label>

        <button type="button" className="btn-secondary" onClick={handleTogglePause}>
          {paused ? '继续' : '暂停'}
        </button>
        <button type="button" className="btn-secondary" onClick={handleClear}>
          清空显示
        </button>

        <p className="ml-auto pb-2 text-xs text-muted-foreground">
          显示 {logs.length} 条{buffered > 0 ? ` · 服务端缓冲约 ${buffered} 条` : ''}
        </p>
      </div>

      <div ref={containerRef} className="log-panel">
        {logs.length === 0 ? (
          <p className="font-mono text-sm text-muted-foreground">暂无日志，等待输出…</p>
        ) : (
          <div className="space-y-0.5">
            {logs.map((entry, index) => (
              <LogLine key={`${entry.ts}-${index}-${entry.message.slice(0, 24)}`} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
