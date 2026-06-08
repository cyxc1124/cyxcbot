import type { BilibiliConnectionStatus } from '../api/types'

const STATUS_META: Record<
  BilibiliConnectionStatus['status'],
  { label: string; badge: string; title: string; hint?: string }
> = {
  logged_in: { label: '已登录', badge: 'badge-success', title: '' },
  not_configured: {
    label: '未登录',
    badge: 'badge-warning',
    title: '尚未登录 B 站账号',
    hint: '使用下方扫码完成 B 站账号绑定',
  },
  session_expired: {
    label: '已失效',
    badge: 'badge-danger',
    title: '登录已失效',
    hint: '请重新扫码登录',
  },
  verify_failed: {
    label: '验证失败',
    badge: 'badge-danger',
    title: '无法验证登录状态',
    hint: '请检查网络或重新登录',
  },
}

type BilibiliAccountInfoProps = {
  account: BilibiliConnectionStatus
}

export function BilibiliAccountInfo({ account }: BilibiliAccountInfoProps) {
  const meta = STATUS_META[account.status]

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/40">
      {account.logged_in ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-lg font-semibold text-slate-900 dark:text-white">
              {account.username || '未知用户'}
            </p>
            <span className={`badge shrink-0 ${meta.badge}`}>{meta.label}</span>
          </div>
          {account.uid && (
            <p className="mt-1 text-sm text-slate-500">
              UID{' '}
              <span className="font-mono text-slate-700 dark:text-slate-300">{account.uid}</span>
            </p>
          )}
        </>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-slate-900 dark:text-white">{meta.title}</p>
            <span className={`badge shrink-0 ${meta.badge}`}>{meta.label}</span>
          </div>
          {meta.hint && <p className="mt-1 text-sm text-slate-500">{meta.hint}</p>}
        </>
      )}
    </div>
  )
}
