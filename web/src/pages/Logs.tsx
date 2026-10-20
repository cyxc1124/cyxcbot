import { useVirtualizer } from '@tanstack/react-virtual'
import { useCallback, useEffect, useMemo, useRef, useState, startTransition } from 'react'
import {
  AdjustmentsHorizontalIcon, ArrowDownIcon, ArrowDownTrayIcon, ArrowPathIcon,
  ArrowUturnLeftIcon, FunnelIcon, MagnifyingGlassIcon, PauseIcon, PlayIcon, TrashIcon,
} from '@heroicons/react/24/outline'
import { ApiClientError, getRecentLogs, streamLogs } from '../api/client'
import type { RuntimeLogEntry } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { LogLevelSettings } from '../components/LogLevelSettings'
import { formatApiError } from '../utils/apiError'
import {
  DISPLAY_MAX,
  LOG_FLUSH_MS,
  LOG_LEVEL_CLASS,
  LOG_VIEW_PRESETS,
  WEB_LOG_LEVELS,
  appendToLogBuffer,
  filterLogs,
  isNearBottom,
  logViewPreset,
  mergeLogs,
  minLogLevel,
  serializeLogs,
  trimLogs,
  type LogViewOptions,
} from './logsDisplay'

type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'failed'

const LOG_LINE_ESTIMATE_PX = 34
const LOG_TABLE_HEADER_PX = 32

function LogLine({ entry }: { entry: RuntimeLogEntry }) {
  const levelClass = LOG_LEVEL_CLASS[entry.level.toUpperCase()] ?? LOG_LEVEL_CLASS.INFO
  return (
    <div className="log-table-row">
      <span className="text-muted-foreground" title={entry.ts}>{entry.ts.split(/[ T]/).at(-1)?.slice(0, 8)}</span>
      <span className={`flex items-center gap-1.5 font-semibold ${levelClass}`}><span className="size-1 shrink-0 rounded-full bg-current" aria-hidden="true" />{entry.level}</span>
      <span className="truncate text-muted-foreground" title={entry.logger}>{entry.logger}</span>
      <span className="log-message text-foreground">{entry.message}</span>
    </div>
  )
}

export function LogsPage() {
  const [logs, setLogs] = useState<RuntimeLogEntry[]>([])
  const [buffered, setBuffered] = useState(0)
  const [view, setView] = useState<LogViewOptions>(LOG_VIEW_PRESETS.运维)
  const [query, setQuery] = useState('')
  const [showOptions, setShowOptions] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [autoScroll, setAutoScroll] = useState(true)
  const [paused, setPaused] = useState(false)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [error, setError] = useState('')

  const minLevel = minLogLevel(view.levels)
  const preset = logViewPreset(view)
  const visibleLogs = useMemo(() => filterLogs(logs, view, query), [logs, view, query])

  const containerRef = useRef<HTMLDivElement>(null)
  const pausedBufferRef = useRef<RuntimeLogEntry[]>([])
  const pendingLogsRef = useRef<RuntimeLogEntry[]>([])
  const flushTimerRef = useRef<number | undefined>(undefined)
  const flushGenerationRef = useRef(0)
  const pausedRef = useRef(paused)

  pausedRef.current = paused

  const clearFlushTimer = useCallback(() => {
    if (flushTimerRef.current !== undefined) {
      window.clearTimeout(flushTimerRef.current)
      flushTimerRef.current = undefined
    }
  }, [])

  const invalidatePendingFlush = useCallback(() => {
    flushGenerationRef.current += 1
    pendingLogsRef.current = []
    clearFlushTimer()
  }, [clearFlushTimer])

  const flushPendingLogs = useCallback(() => {
    flushTimerRef.current = undefined
    const pending = pendingLogsRef.current
    if (!pending.length) return
    pendingLogsRef.current = []
    const generation = flushGenerationRef.current
    startTransition(() => {
      if (generation !== flushGenerationRef.current) return
      setLogs((prev) => mergeLogs(prev, pending))
    })
  }, [])

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current !== undefined) return
    flushTimerRef.current = window.setTimeout(flushPendingLogs, LOG_FLUSH_MS)
  }, [flushPendingLogs])

  const appendLogs = useCallback(
    (incoming: RuntimeLogEntry[]) => {
      if (!incoming.length) return
      if (pausedRef.current) {
        pausedBufferRef.current = appendToLogBuffer(pausedBufferRef.current, incoming)
        return
      }
      pendingLogsRef.current.push(...incoming)
      scheduleFlush()
    },
    [scheduleFlush],
  )

  // TanStack Virtual returns non-memoizable helpers; React Compiler skips this call site.
  // eslint-disable-next-line react-hooks/incompatible-library -- known TanStack Virtual limitation
  const rowVirtualizer = useVirtualizer({
    count: visibleLogs.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => LOG_LINE_ESTIMATE_PX,
    scrollMargin: LOG_TABLE_HEADER_PX,
    overscan: 15,
    getItemKey: (index) => {
      const entry = visibleLogs[index]
      return `${entry.session_id}:${entry.entry_id}-${index}`
    },
  })
  // scrollToIndex is stable; the virtualizer object identity is not.
  const scrollToIndex = rowVirtualizer.scrollToIndex
  const measureRows = rowVirtualizer.measure

  useEffect(() => { measureRows() }, [view.wrap, measureRows])

  const scrollToLatest = useCallback(() => {
    if (visibleLogs.length === 0) return
    scrollToIndex(visibleLogs.length - 1, { align: 'end' })
  }, [visibleLogs.length, scrollToIndex])

  useEffect(() => {
    if (!autoScroll || paused || visibleLogs.length === 0) return
    scrollToLatest()
  }, [visibleLogs, view.wrap, showOptions, autoScroll, paused, scrollToLatest])

  // Virtual row measurements also scroll; only manual input should stop following.
  const stopFollowing = () => setAutoScroll(false)

  const handleFollowChecked = useCallback(
    (checked: boolean) => {
      if (checked) {
        setAutoScroll(true)
        requestAnimationFrame(() => scrollToLatest())
      } else {
        setAutoScroll(false)
      }
    },
    [scrollToLatest],
  )

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    let reconnectTimer: number | undefined

    const connect = async () => {
      if (signal.aborted) return
      setConnection('connecting')
      setError('')

      try {
        await streamLogs(minLevel, {
          signal,
          onOpen: () => { if (!signal.aborted) setConnection('connected') },
          onLog: (entry) => { if (!signal.aborted) appendLogs([entry]) },
        })
      } catch (err) {
        if (signal.aborted) return
        setError(formatApiError(err, '无法建立日志连接'))
        if (err instanceof ApiClientError && (err.status === 401 || err.status === 403)) {
          setConnection('failed')
          return
        }
      }
      if (signal.aborted) return
      setConnection('disconnected')
      reconnectTimer = window.setTimeout(() => void connect(), 3000)
    }

    const start = async () => {
      try {
        const data = await getRecentLogs({ limit: DISPLAY_MAX, min_level: minLevel }, signal)
        if (signal.aborted) return
        setLogs(trimLogs(data.items))
        setBuffered(data.total_buffered)
      } catch (err) {
        if (signal.aborted) return
        setError(formatApiError(err, '加载历史日志失败'))
        if (err instanceof ApiClientError && (err.status === 401 || err.status === 403)) {
          setConnection('failed')
          return
        }
      }
      await connect()
    }
    void start()

    return () => {
      controller.abort()
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      pausedBufferRef.current = []
      invalidatePendingFlush()
    }
  }, [minLevel, reloadKey, invalidatePendingFlush, appendLogs])

  useEffect(() => () => clearFlushTimer(), [clearFlushTimer])

  const handleTogglePause = () => {
    setPaused((prev) => {
      if (prev) {
        const pending = pausedBufferRef.current
        pausedBufferRef.current = []
        if (pending.length) {
          clearFlushTimer()
          flushGenerationRef.current += 1
          setLogs((current) => mergeLogs(current, pending))
        }
      } else {
        clearFlushTimer()
        const pending = pendingLogsRef.current
        pendingLogsRef.current = []
        flushGenerationRef.current += 1
        if (pending.length) {
          pausedBufferRef.current = appendToLogBuffer(pausedBufferRef.current, pending)
        }
      }
      return !prev
    })
  }

  const handleClear = () => {
    pausedBufferRef.current = []
    invalidatePendingFlush()
    setLogs([])
  }

  const handleExport = () => {
    const url = URL.createObjectURL(new Blob([serializeLogs(visibleLogs)], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `cyxcbot-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.log`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const connectionLabel =
    paused ? '已暂停显示' : connection === 'connected' ? '实时'
      : connection === 'connecting' ? '连接中…'
        : connection === 'failed' ? '连接失败' : '已断开，重试中'

  const connectionClass =
    paused ? 'badge-neutral' : connection === 'connected'
      ? 'badge-success'
      : connection === 'connecting'
        ? 'badge-warning'
        : 'badge-danger'

  return (
    <section aria-label="运行日志" className="card flex min-h-[calc(100dvh-9rem)] flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-foreground">运行日志</h2>
            <span className={`badge ${connectionClass}`}>{connectionLabel}</span>
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground" title={`服务端缓冲约 ${buffered} 条`}>
            {visibleLogs.length} / {logs.length} 条 · SSE 实时推送 · 最多 {view.limit.toLocaleString()} 行
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto">
          <div className="relative w-full sm:w-56">
            <MagnifyingGlassIcon className="pointer-events-none absolute top-2 left-2.5 size-4 text-muted-foreground" aria-hidden="true" />
            <input type="search" aria-label="搜索日志" placeholder="搜索消息 / 模块 / 级别" className="input min-h-8 rounded-full py-1 pl-8 text-xs" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <div className="flex flex-wrap items-center gap-0.5">
            <button type="button" className="log-tool-button" aria-label="跟随最新" aria-pressed={autoScroll} onClick={() => handleFollowChecked(!autoScroll)}><ArrowDownIcon aria-hidden="true" /></button>
            <button type="button" className="log-tool-button" aria-label={paused ? '继续显示' : '暂停显示'} aria-pressed={paused} onClick={handleTogglePause}>{paused ? <PlayIcon aria-hidden="true" /> : <PauseIcon aria-hidden="true" />}</button>
            <button type="button" className="log-tool-button" aria-label="自动换行" aria-pressed={view.wrap} onClick={() => setView((current) => ({ ...current, wrap: !current.wrap }))}><ArrowUturnLeftIcon aria-hidden="true" /></button>
            <button type="button" className="log-tool-button" aria-label="显示选项" aria-expanded={showOptions} aria-controls="logs-options" aria-pressed={showOptions} onClick={() => setShowOptions((current) => !current)}><AdjustmentsHorizontalIcon aria-hidden="true" /></button>
            <button type="button" className="log-tool-button" aria-label="刷新日志" onClick={() => setReloadKey((current) => current + 1)}><ArrowPathIcon aria-hidden="true" /></button>
            <button type="button" className="log-tool-button" aria-label="导出当前视图" disabled={!visibleLogs.length} onClick={handleExport}><ArrowDownTrayIcon aria-hidden="true" /></button>
            <button type="button" className="log-tool-button" aria-label="清空视图" onClick={handleClear}><TrashIcon aria-hidden="true" /></button>
          </div>
        </div>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={() => setReloadKey((current) => current + 1)} />}

      <fieldset className="grid min-w-0 grid-cols-[1rem_minmax(0,1fr)] items-center gap-2 sm:flex sm:flex-wrap">
        <legend className="sr-only">Web 显示级别</legend>
        <FunnelIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="log-level-group">
          {WEB_LOG_LEVELS.map((level) => (
            <label key={level} className={`log-level-chip ${LOG_LEVEL_CLASS[level]}`}>
              <input type="checkbox" checked={view.levels.includes(level)} onChange={() => setView((current) => ({ ...current, levels: WEB_LOG_LEVELS.filter((item) => item === level ? !current.levels.includes(item) : current.levels.includes(item)) }))} className="peer sr-only" />
              <span className="log-level-choice"><span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />{level}</span>
            </label>
          ))}
        </div>
        <span className="col-start-2 text-xs text-muted-foreground">仅筛选 Web 显示</span>
      </fieldset>

      <div id="logs-options" hidden={!showOptions} className="shrink-0 rounded-2xl border border-border bg-secondary/20 p-4">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <fieldset>
            <legend className="mb-2 text-xs font-medium text-foreground">视图预设</legend>
            <div className="log-level-group">
              {Object.entries(LOG_VIEW_PRESETS).map(([name, options]) => (
                <label key={name} className="log-level-chip text-foreground" title={`${options.limit} 行 · ${options.wrap ? '自动换行' : '不换行'}`}>
                  <input type="radio" name="log-view-preset" value={name} checked={preset === name} onChange={() => setView(options)} className="peer sr-only" />
                  <span className="log-level-choice">{name}</span>
                </label>
              ))}
              {preset === '自定义' && <span className="px-2 py-1.5 text-xs text-muted-foreground">自定义</span>}
            </div>
          </fieldset>
          <div>
            <label htmlFor="log-view-limit" className="mb-1.5 block text-xs text-muted-foreground">显示行数</label>
            <select id="log-view-limit" className="input min-h-8 w-auto py-1 text-xs" value={view.limit} onChange={(event) => setView((current) => ({ ...current, limit: Number(event.target.value) }))}>
              {[500, 1000, 2000].map((limit) => <option key={limit} value={limit}>{limit.toLocaleString()} 行</option>)}
            </select>
          </div>
        </div>
        <LogLevelSettings />
      </div>

      <div
        ref={containerRef}
        className="log-panel h-80 flex-none focus-visible:outline-2 focus-visible:outline-ring lg:h-0 lg:min-h-40 lg:flex-1 lg:basis-0"
        data-wrap={view.wrap}
        role="region"
        aria-label="日志内容"
        tabIndex={0}
        onWheel={(event) => { if (event.deltaY < 0 || !isNearBottom(event.currentTarget)) setAutoScroll(false) }}
        onTouchMove={stopFollowing}
        onKeyDown={(event) => { if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) setAutoScroll(false) }}
        onPointerDown={stopFollowing}
      >
        <div className="log-table-head" aria-hidden="true"><span>时间</span><span>级别</span><span>模块</span><span className="log-message">消息</span></div>
        {visibleLogs.length === 0 ? (
          <p className="p-4 text-xs text-muted-foreground">{logs.length ? '没有匹配的日志，请调整筛选条件。' : '暂无日志，等待输出…'}</p>
        ) : (
          <div
            className="relative w-full"
            style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={rowVirtualizer.measureElement}
                className="absolute top-0 left-0 w-full"
                style={{ transform: `translateY(${virtualRow.start - LOG_TABLE_HEADER_PX}px)` }}
              >
                <LogLine entry={visibleLogs[virtualRow.index]!} />
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
