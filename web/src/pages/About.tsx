import { useCallback, useEffect, useState } from 'react'
import { getAbout } from '../api/client'
import type { AboutInfo } from '../api/types'
import { LoadErrorBanner } from '../components/LoadErrorBanner'
import { PageLoading } from '../components/LoadingSpinner'
import { formatApiError } from '../utils/apiError'

const WEB_BUILD_VERSION = import.meta.env.VITE_BUILD_VERSION || 'dev'

interface InfoRowProps {
  label: string
  value: string
  hint?: string
}

function InfoRow({ label, value, hint }: InfoRowProps) {
  return (
    <div className="border-b border-border py-4 last:border-0 border-border">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-base font-medium text-foreground">{value}</dd>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function AboutPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [about, setAbout] = useState<AboutInfo | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setAbout(await getAbout())
    } catch (err) {
      setError(formatApiError(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (loading && !about && !error) return <PageLoading />

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">关于</h2>
        <p className="mt-1 text-sm text-muted-foreground">机器草 Web 管理面板</p>
      </div>

      {error && <LoadErrorBanner message={error} onRetry={load} />}

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
            hint={`前端构建版本 ${WEB_BUILD_VERSION}`}
          />
          <InfoRow
            label="后端框架"
            value={about?.backend_framework ?? '—'}
            hint={about ? `Python ${about.python_version}` : undefined}
          />
          <InfoRow
            label="构建版本"
            value={about?.build_version ?? '—'}
            hint="由 GIT_TAG / GIT_COMMIT / BUILD_VERSION 环境变量注入"
          />
        </dl>
      </div>
    </div>
  )
}
