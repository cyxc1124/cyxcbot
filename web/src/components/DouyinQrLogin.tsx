import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelDouyinQrcodeLogin,
  getDouyinQrcode,
  pollDouyinQrcodeLogin,
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
  const abortRef = useRef<AbortController | null>(null)
  const sessionRef = useRef<string | null>(null)

  const stopPolling = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    const sessionId = sessionRef.current
    sessionRef.current = null
    if (sessionId) {
      void cancelDouyinQrcodeLogin(sessionId).catch(() => {
        // best-effort cleanup of Playwright session
      })
    }
  }, [])

  const startLogin = useCallback(async () => {
    stopPolling()
    setPhase('loading')
    setMessage('')
    setImageBase64('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const qr = await getDouyinQrcode()
      if (controller.signal.aborted) return

      sessionRef.current = qr.session_id
      setImageBase64(qr.image_base64)
      setPhase('waiting')
      setMessage('请使用抖音 App 扫描二维码，并在手机上确认登录')

      const result = await pollDouyinQrcodeLogin(qr.session_id, controller.signal)
      if (controller.signal.aborted) return

      sessionRef.current = null
      if (result.success) {
        setPhase('success')
        setMessage(result.message || '登录成功')
        onSuccess()
      } else {
        setPhase('error')
        setMessage(result.message || '登录失败')
        onError?.(result.message)
      }
    } catch (err) {
      if (controller.signal.aborted) return
      sessionRef.current = null
      const text = err instanceof Error ? err.message : '扫码登录失败'
      setPhase('error')
      setMessage(text)
      onError?.(text)
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
    }
  }, [onError, onSuccess, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

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
            <button type="button" className="btn-secondary" onClick={stopPolling}>
              取消
            </button>
          )}
          <button
            type="button"
            className="btn-primary"
            disabled={phase === 'loading' || phase === 'waiting'}
            onClick={() => void startLogin()}
          >
            {phase === 'idle' || phase === 'error' || phase === 'success'
              ? '获取二维码'
              : '等待扫码…'}
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

      {imageBase64 && phase === 'waiting' && (
        <div className="flex justify-center py-2">
          <div className="rounded-lg bg-white p-4 shadow-xs">
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
