import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelDouyinQrcodeLogin,
  getDouyinQrcode,
  pollDouyinQrcodeLogin,
  refreshDouyinQrcode,
} from '../api/client'

type DouyinQrLoginProps = {
  onSuccess: () => void
  onError?: (message: string) => void
}

type Phase = 'idle' | 'loading' | 'waiting' | 'success' | 'error'

export function DouyinQrLogin({ onSuccess, onError }: DouyinQrLoginProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [imageBase64, setImageBase64] = useState('')
  const [message, setMessage] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const sessionRef = useRef<string | null>(null)

  const abortPoll = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const stopPolling = useCallback(() => {
    abortPoll()
    const sessionId = sessionRef.current
    sessionRef.current = null
    if (sessionId) {
      void cancelDouyinQrcodeLogin(sessionId).catch(() => {
        // best-effort cleanup of Playwright session
      })
    }
  }, [abortPoll])

  const cancelLogin = useCallback(() => {
    stopPolling()
    setPhase('idle')
    setMessage('')
    setImageBase64('')
    setRefreshing(false)
  }, [stopPolling])

  const runPoll = useCallback(
    async (sessionId: string, controller: AbortController) => {
      const result = await pollDouyinQrcodeLogin(sessionId, controller.signal)
      if (controller.signal.aborted) return

      sessionRef.current = null
      setImageBase64('')
      setRefreshing(false)
      if (result.success) {
        setPhase('success')
        setMessage(result.message || '登录成功')
        onSuccess()
      } else {
        setPhase('error')
        setMessage(result.message || '登录失败')
        onError?.(result.message)
      }
    },
    [onError, onSuccess],
  )

  const startLogin = useCallback(async () => {
    stopPolling()
    setPhase('loading')
    setRefreshing(false)
    setMessage('')
    setImageBase64('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const qr = await getDouyinQrcode()
      // 取消发生在 qrcode 请求返回前时 sessionRef 仍为空，stopPolling 无法 cancel；
      // 若此处直接 return，服务端 Playwright Chromium 会一直挂到下次扫码或进程退出。
      if (controller.signal.aborted) {
        void cancelDouyinQrcodeLogin(qr.session_id).catch(() => {
          // best-effort cleanup of Playwright session
        })
        return
      }

      sessionRef.current = qr.session_id
      setImageBase64(qr.image_base64)
      setPhase('waiting')
      setMessage('请使用抖音 App 扫描二维码，并在手机上确认登录')
      await runPoll(qr.session_id, controller)
    } catch (err) {
      if (controller.signal.aborted) return
      sessionRef.current = null
      setImageBase64('')
      setRefreshing(false)
      const text = err instanceof Error ? err.message : '扫码登录失败'
      setPhase('error')
      setMessage(text)
      onError?.(text)
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
    }
  }, [onError, runPoll, stopPolling])

  const refreshLogin = useCallback(async () => {
    const sessionId = sessionRef.current
    if (!sessionId) {
      await startLogin()
      return
    }

    // 只中断 poll，不 cancel Playwright；由 refresh API 在同会话换新码
    abortPoll()
    setPhase('loading')
    setRefreshing(true)
    setMessage('正在刷新二维码…')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const qr = await refreshDouyinQrcode(sessionId)
      if (controller.signal.aborted) return

      sessionRef.current = qr.session_id
      setImageBase64(qr.image_base64)
      setRefreshing(false)
      setPhase('waiting')
      setMessage('请使用抖音 App 扫描二维码，并在手机上确认登录')
      await runPoll(qr.session_id, controller)
    } catch (err) {
      if (controller.signal.aborted) return
      setRefreshing(false)
      setImageBase64('')
      sessionRef.current = null
      const text = err instanceof Error ? err.message : '刷新二维码失败'
      setPhase('error')
      setMessage(text)
      onError?.(text)
      void cancelDouyinQrcodeLogin(sessionId).catch(() => {
        // session may already be gone
      })
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
    }
  }, [abortPoll, onError, runPoll, startLogin])

  useEffect(() => () => stopPolling(), [stopPolling])

  const primaryLabel =
    phase === 'loading'
      ? refreshing
        ? '刷新中…'
        : '获取中…'
      : phase === 'waiting'
        ? '刷新二维码'
        : '获取二维码'

  return (
    <div className="space-y-4 rounded-lg border border-border bg-muted p-4 border-border bg-card/40">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-foreground">扫码登录</p>
          <p className="text-sm text-muted-foreground">
            使用抖音 App 扫描官网登录二维码（服务端 Playwright 截取），无需手动复制 Cookie
          </p>
        </div>
        <div className="flex gap-2">
          {(phase === 'waiting' || phase === 'loading') && (
            <button type="button" className="btn-secondary" onClick={cancelLogin}>
              取消
            </button>
          )}
          <button
            type="button"
            className="btn-primary"
            disabled={phase === 'loading'}
            onClick={() => void (phase === 'waiting' ? refreshLogin() : startLogin())}
          >
            {primaryLabel}
          </button>
        </div>
      </div>

      {message && (
        <p
          className={`text-sm ${
            phase === 'error'
              ? 'text-red-600'
              : phase === 'success'
                ? 'text-emerald-600'
                : 'text-muted-foreground'
          }`}
        >
          {message}
        </p>
      )}

      {imageBase64 && (phase === 'waiting' || phase === 'loading') && (
        <div className="flex justify-center py-2">
          <div
            className={`rounded-lg bg-white p-4 shadow-xs ${
              phase === 'loading' ? 'opacity-60' : ''
            }`}
          >
            <img
              src={`data:image/png;base64,${imageBase64}`}
              alt="抖音登录二维码"
              width={200}
              height={200}
              className="h-[200px] w-[200px] object-contain"
            />
          </div>
        </div>
      )}
    </div>
  )
}
