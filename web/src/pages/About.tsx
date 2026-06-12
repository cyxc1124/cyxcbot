import { useCallback, useMemo, useState } from 'react'
import { useLoadingOnKeyChange } from '../hooks/useLoadingOnKeyChange'
import { useMountAsync } from '../hooks/useMountAsync'
import { createRetryHandler } from '../utils/retryLoad'
import { getAbout } from '../api/client'
import type { AboutInfo } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { formatApiError } from '../utils/apiError'

const WEB_BUILD_VERSION = import.meta.env.VITE_BUILD_VERSION || 'dev'
const WEB_GIT_BRANCH = import.meta.env.VITE_GIT_BRANCH
const WEB_BUILD_TIME = import.meta.env.VITE_BUILD_TIME

interface InfoRowProps {
  label: string
  value: string
  hint?: string
  badge?: string
}

function InfoRow({ label, value, hint, badge }: InfoRowProps) {
  return (
    <div className="border-b border-border py-4 last:border-0 border-border">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex flex-wrap items-center gap-2">
        <span className="text-base font-medium text-foreground">{value}</span>
        {badge && (
          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
            {badge}
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

function branchLabel(branch: string | null | undefined): string {
  if (!branch) return '—'
  return branch
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

  if (loading && !about && !error) return <PageLoading />

  const isDevelop = about?.git_branch === 'develop'

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
            <h3 className="text-lg font-semibold text-foreground">
              {about?.app_name ?? '机器草'}
            </h3>
            <p className="text-sm text-muted-foreground">Bilibili 监控机器人管理界面</p>
          </div>
        </div>

        <dl>
          <InfoRow
            label="Web UI"
            value={`Powered by ${about?.web_frontend ?? 'React + Tailwind CSS'}`}
            hint={[
              `前端构建版本 ${WEB_BUILD_VERSION}`,
              WEB_GIT_BRANCH ? `分支 ${WEB_GIT_BRANCH}` : null,
              webBuildTime ? `构建时间 ${webBuildTime}` : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          />
          <InfoRow
            label="后端框架"
            value={about?.backend_framework ?? '—'}
            hint={about ? `Python ${about.python_version}` : undefined}
          />
          <InfoRow
            label="Git 分支"
            value={branchLabel(about?.git_branch ?? about?.git_tag)}
            badge={isDevelop ? '开发版' : undefined}
            hint={
              about?.git_tag
                ? `标签 ${about.git_tag}${about.git_commit ? ` · 提交 ${about.git_commit}` : ''}`
                : about?.git_commit
                  ? `提交 ${about.git_commit}`
                  : '由 GIT_BRANCH / GIT_TAG 环境变量注入'
            }
          />
          <InfoRow
            label="构建版本"
            value={about?.build_version ?? '—'}
            hint={
              [
                about?.build_number ? `构建号 #${about.build_number}` : null,
                backendBuildTime ? `构建时间 ${backendBuildTime}` : null,
              ]
                .filter(Boolean)
                .join(' · ') || '由 GIT_TAG / GIT_COMMIT / BUILD_VERSION 环境变量注入'
            }
          />
        </dl>
      </div>
    </div>
  )
}
