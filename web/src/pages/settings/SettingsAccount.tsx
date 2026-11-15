import { useCallback, useState } from 'react'
import { getBilibiliAccounts, removeBilibiliAccount, testBilibiliAccount } from '../../api/client'
import type { BilibiliAccount, BilibiliConnectionStatus } from '../../api/types'
import { BilibiliAccountInfo } from '../../components/BilibiliAccountInfo'
import { BilibiliQrLogin } from '../../components/BilibiliQrLogin'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LoadErrorBanner } from '../../components/LoadErrorBanner'
import { useToast } from '../../contexts/ToastContext'
import { useMountAsync } from '../../hooks/useMountAsync'
import { useSettingsForm } from './SettingsContext'

export function SettingsAccountPage() {
  const { showToast } = useToast()
  const { settings, formDisabled, load, loggingOut, setShowLogoutConfirm } = useSettingsForm()
  const [accounts, setAccounts] = useState<BilibiliAccount[] | null>(null)
  const [error, setError] = useState('')
  const [busyUid, setBusyUid] = useState<string | null>(null)
  const [pendingRemove, setPendingRemove] = useState<BilibiliAccount | null>(null)
  const [statuses, setStatuses] = useState<Record<string, BilibiliConnectionStatus>>({})

  const loadAccounts = useCallback(async () => {
    try {
      setAccounts(await getBilibiliAccounts())
      setStatuses({})
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载账号失败')
    }
  }, [])

  useMountAsync(useCallback(() => {
    if (settings) return loadAccounts()
  }, [settings, loadAccounts]))

  const verify = async (uid: string) => {
    setBusyUid(uid)
    try {
      const status = await testBilibiliAccount(uid)
      setStatuses((current) => ({ ...current, [uid]: status }))
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '验证失败')
    } finally {
      setBusyUid(null)
    }
  }

  const remove = async () => {
    if (!pendingRemove) return
    setBusyUid(pendingRemove.uid)
    try {
      const result = await removeBilibiliAccount(pendingRemove.uid)
      setPendingRemove(null)
      showToast('success', result.message)
      await load()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '移除失败')
    } finally {
      setBusyUid(null)
    }
  }

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-foreground">B 站账号</h3>
      <p className="text-sm text-muted-foreground">
        可扫码添加多个账号，HTTP 查询请求按账号轮换。同一 UID 重新登录会更新凭据，其他账号保留。
        截图与弹幕连接使用列表首账号。轮换不能保证避免风控，请保持合理的监控间隔。
      </p>

      {error && <LoadErrorBanner message={error} onRetry={() => void loadAccounts()} />}
      {accounts === null ? (
        <p className="text-sm text-muted-foreground" role="status">正在加载账号…</p>
      ) : accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">尚未添加 B 站账号</p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">已保存 {accounts.length} 个账号，均参与请求轮换</p>
          {accounts.map((account, index) => (
            <div key={account.uid} className="space-y-3 rounded-lg border border-border p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="break-words font-medium">{account.username || 'B 站账号'}</h4>
                  <p className="break-all text-sm text-muted-foreground">UID {account.uid}</p>
                  {index === 0 && <span className="badge">截图 / 弹幕账号</span>}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-secondary" disabled={busyUid !== null || loggingOut}
                    aria-label={`验证账号 ${account.uid}`} onClick={() => void verify(account.uid)}>
                    {busyUid === account.uid ? '处理中…' : '验证登录'}
                  </button>
                  <button type="button" className="btn-danger" disabled={busyUid !== null || loggingOut}
                    aria-label={`移除账号 ${account.uid}`} onClick={() => setPendingRemove(account)}>
                    移除
                  </button>
                </div>
              </div>
              {statuses[account.uid] && <BilibiliAccountInfo account={statuses[account.uid]} />}
            </div>
          ))}
        </div>
      )}

      {!formDisabled && (
        <BilibiliQrLogin
          onSuccess={() => {
            showToast('success', 'B 站账号已保存')
            void load()
          }}
          onError={(msg) => showToast('error', msg)}
        />
      )}

      {settings?.bilibili_cookie?.configured && (
        <button type="button" className="btn-danger" disabled={loggingOut || busyUid !== null}
          onClick={() => setShowLogoutConfirm(true)}>
          移除全部账号
        </button>
      )}
      <ConfirmDialog open={pendingRemove !== null} title="移除 B 站账号"
        message={`确定移除 ${pendingRemove?.username || pendingRemove?.uid}？其余账号继续参与请求轮换。`}
        confirmLabel="移除账号" loading={busyUid !== null}
        onCancel={() => { if (busyUid === null) setPendingRemove(null) }}
        onConfirm={() => void remove()} />
    </div>
  )
}
