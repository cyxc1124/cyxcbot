import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getBotConnectionsStatus } from '../api/client'
import type { BotConnectionsStatus } from '../api/types'
import { Icon } from './Icon'

function StatusDot({ label }: { label: string }) {
  const color = label === '已连接'
    ? 'bg-green-600 dark:bg-green-400'
    : label === '未连接' || label === '等待连接' || label === '状态未知'
      ? 'bg-amber-500 dark:bg-amber-400'
      : 'bg-muted-foreground/60'
  return <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full sm:size-2 ${color}`} />
}

export function BotConnectionStatus() {
  const [status, setStatus] = useState<BotConnectionsStatus | null>(null)
  const [failed, setFailed] = useState(false)
  const detailsRef = useRef<HTMLDetailsElement>(null)
  const panelId = useId()

  useEffect(() => {
    let cancelled = false
    let pending = false
    const load = async () => {
      if (pending) return
      pending = true
      try {
        const data = await getBotConnectionsStatus()
        if (!cancelled) {
          setStatus(data)
          setFailed(false)
        }
      } catch {
        if (!cancelled) {
          setStatus(null)
          setFailed(true)
        }
      } finally {
        pending = false
      }
    }
    void load()
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') void load()
    }, 30000)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void load()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const details = detailsRef.current
      if (details?.open && !details.contains(event.target as Node)) details.open = false
    }
    const onKeyDown = (event: KeyboardEvent) => {
      const details = detailsRef.current
      if (event.key === 'Escape' && details?.open) {
        details.open = false
        details.querySelector('summary')?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [])

  const unknown = failed ? '状态未知' : '检查中'
  const onebot = status ? status.qq.connected ? '已连接' : '未连接' : unknown
  const official = status
    ? status.official_qq.connected ? '已连接' : status.official_qq.configured ? '等待连接' : '未配置'
    : unknown

  return (
    <details ref={detailsRef} className="group shrink-0 sm:relative">
      <summary
        aria-label={`Bot 连接：OneBot ${onebot}，官方 Bot ${official}`}
        aria-controls={panelId}
        className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-full border border-border bg-background px-2.5 text-[13px] text-foreground transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:gap-3 sm:px-4 [&::-webkit-details-marker]:hidden"
      >
        <span className="inline-flex items-center gap-1.5 sm:gap-2">
          <StatusDot label={onebot} />
          <span className="hidden whitespace-nowrap sm:inline">OneBot {onebot}</span>
        </span>
        <span aria-hidden="true" className="hidden h-4 w-px shrink-0 bg-[var(--border)] sm:block" />
        <span className="inline-flex items-center gap-1.5 sm:gap-2">
          <StatusDot label={official} />
          <span className="hidden whitespace-nowrap sm:inline">官方 Bot {official}</span>
        </span>
        <span className="sm:hidden">连接</span>
        <Icon name="chevron-down" className="hidden size-3.5 text-muted-foreground transition-transform group-open:rotate-180 sm:block" />
      </summary>
      <div id={panelId} role="region" aria-label="Bot 连接详情" className="absolute right-3 top-full mt-2 w-80 max-w-[calc(100vw-1.5rem)] rounded-2xl border border-border bg-popover p-4 text-popover-foreground shadow-lg sm:right-0">
        <h2 className="mb-4 text-sm font-semibold">Bot 连接</h2>
        {failed && <p role="alert" className="mb-4 text-xs text-amber-700 dark:text-amber-400">无法获取连接状态，稍后自动重试。</p>}
        <div className="space-y-4 text-sm">
          <div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">OneBot</span>
              <span className="inline-flex items-center gap-2 text-xs"><StatusDot label={onebot} />{onebot}</span>
            </div>
            <p className="mt-1.5 break-words text-xs text-muted-foreground">{status?.qq.message ?? '等待获取 OneBot 连接状态'}</p>
          </div>
          <div className="border-t border-border pt-4">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">官方 Bot</span>
              <span className="inline-flex items-center gap-2 text-xs"><StatusDot label={official} />{official}</span>
            </div>
            <p className="mt-1.5 break-words text-xs text-muted-foreground">{status?.official_qq.message ?? '等待获取官方 Bot 连接状态'}</p>
            {status?.official_qq.configured && !status.official_qq.use_websocket && (
              <p className="mt-1.5 text-xs text-muted-foreground">Webhook 按有效事件识别接入，不代表长连接在线检测。</p>
            )}
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-3 text-xs">
          <span className="text-muted-foreground">每 30 秒更新</span>
          <Link to="/settings/official-qq" onClick={() => { if (detailsRef.current) detailsRef.current.open = false }} className="inline-flex min-h-9 items-center gap-1 font-medium text-primary hover:underline">
            官方 Bot 设置 <Icon name="arrow-right" className="size-3.5" />
          </Link>
        </div>
      </div>
    </details>
  )
}
