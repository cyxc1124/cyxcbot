import { useCallback, useEffect, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { getBilibiliQrcode, pollBilibiliQrcodeLogin } from '../api/client'

type BilibiliQrLoginProps = {
  onSuccess: () => void
  onError?: (message: string) => void
}

type Phase = 'idle' | 'loading' | 'waiting' | 'success' | 'error'

export function BilibiliQrLogin({ onSuccess, onError }: BilibiliQrLoginProps) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [url, setUrl] = useState('')
  const [message, setMessage] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const stopPolling = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  const startLogin = useCallback(async () => {
    stopPolling()
    setPhase('loading')
    setMessage('')
    setUrl('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const qrcodeData = await getBilibiliQrcode()
      if (controller.signal.aborted) return

      setUrl(qrcodeData.url)
      setPhase('waiting')
      setMessage('请使用 B 站 App 扫描二维码')

      const result = await pollBilibiliQrcodeLogin(qrcodeData.qrcode, controller.signal)
      if (controller.signal.aborted) return

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
    <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-medium text-slate-900 dark:text-white">扫码登录</p>
          <p className="text-sm text-slate-500">使用 B 站 App 扫描 TV 登录二维码，无需手动复制 Cookie</p>
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
            {phase === 'idle' || phase === 'error' || phase === 'success' ? '获取二维码' : '等待扫码…'}
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
                : 'text-slate-500'
          }`}
        >
          {message}
        </p>
      )}

      {url && phase === 'waiting' && (
        <div className="flex justify-center py-2">
          <div className="rounded-lg bg-white p-4 shadow-sm">
            <QRCodeSVG value={url} size={200} />
          </div>
        </div>
      )}
    </div>
  )
}
