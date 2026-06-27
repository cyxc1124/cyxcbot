import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getAbout } from '../api/client'
import type { AboutInfo } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { formatApiError } from '../utils/apiError'

const WEB_BUILD_TIME = import.meta.env.VITE_BUILD_TIME

type BadgeColor = 'amber' | 'emerald' | 'slate'

const BADGE_COLORS: Record<BadgeColor, string> = {
  amber: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  emerald: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  slate: 'bg-slate-500/15 text-slate-600 dark:text-slate-400',
}

interface InfoRowProps {
  label: string
  value: string
  hint?: string
  badge?: { label: string; color: BadgeColor }
}

function InfoRow({ label, value, hint, badge }: InfoRowProps) {
  return (
    <div className="border-b border-border py-4 last:border-0 border-border">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex flex-wrap items-center gap-2">
        <span className="text-base font-medium text-foreground">{value}</span>
        {badge && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${BADGE_COLORS[badge.color]}`}>
            {badge.label}
          </span>
        )}
      </dd>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function formatBuildTime(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })
}

function getVersionBadge(about: AboutInfo | null): { label: string; color: BadgeColor } | undefined {
  if (!about) return undefined
  if (about.git_branch === 'develop') return { label: '开发版', color: 'amber' }
  if (about.git_tag) return { label: '正式版', color: 'emerald' }
  if (about.build_version === 'dev') return { label: '本地开发', color: 'slate' }
  return undefined
}

export function AboutPage() {
  const [loading, setLoading] = useLoadingOnKeyChange('about')
  const [error, setError] = useState('')
  const [about, setAbout] = useState<AboutInfo | null>(null)

  const load = useCallback(async () => {
    try {
      setAbout(await getAbout())
      setError('')
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading])

  const retryLoad = useMemo(() => createRetryHandler(load, setLoading), [load, setLoading])

  const backendBuildTime = useMemo(
    () => formatBuildTime(about?.build_time),
    [about?.build_time],
  )
  const webBuildTime = useMemo(() => formatBuildTime(WEB_BUILD_TIME), [])

  useMountAsync(load)

  // ponytail: refetch once after 3s to pick up async update check result
  useEffect(() => {
    const timer = setTimeout(() => {
      getAbout().then(setAbout).catch(() => {})
    }, 3000)
    return () => clearTimeout(timer)
  }, [])

  if (loading && !about && !error) return <PageLoading />

  const frontendLabel = (() => {
    const parts: string[] = []
    if (about?.react_version) parts.push(`React ${about.react_version}`)
    else parts.push('React')
    if (about?.tailwindcss_version) parts.push(`Tailwind CSS ${about.tailwindcss_version}`)
    else parts.push('Tailwind CSS')
    return parts.join(' + ')
  })()

  const versionHint = (() => {
    const parts: string[] = []
    if (about?.git_commit) parts.push(`提交 ${about.git_commit}`)
    if (about?.build_number) parts.push(`构建号 #${about.build_number}`)
    const bt = backendBuildTime
    if (bt) parts.push(`构建时间 ${bt}`)
    return parts.join(' · ') || undefined
  })()

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">关于</h2>
        <p className="mt-1 text-sm text-muted-foreground">机器草 Web 管理面板</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={retryLoad} />}

      <div className="card">
        <div className="mb-6 flex items-center gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary text-xl font-bold text-white">
            C
          </span>
          <div>
            <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground">
              <span>{about?.app_name ?? '机器草'}</span>
              {about?.update_available && about?.update_url && (
                <a
                  href={about.update_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-600 hover:underline dark:text-amber-400"
                >
                  有新版本
                </a>
              )}
            </h3>
            <p className="text-sm text-muted-foreground">Bilibili 监控机器人管理界面</p>
          </div>
        </div>

        <dl>
          <InfoRow
            label="前端"
            value={frontendLabel}
            hint={webBuildTime ? `构建时间 ${webBuildTime}` : undefined}
          />
          <InfoRow
            label="后端"
            value={about?.backend_framework ?? '—'}
            hint={about ? `Python ${about.python_version}` : undefined}
          />
          <InfoRow
            label="版本信息"
            value={about?.build_version ?? '—'}
            badge={getVersionBadge(about)}
            hint={versionHint}
          />
        </dl>
      </div>
    </div>
  )
}
