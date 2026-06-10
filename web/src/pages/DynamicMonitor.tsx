import { useCallback, useState } from 'react'
import { getDynamicMonitorStatus, triggerDynamicCheck } from '../api/client'
import type { MonitorPollSchedule } from '../api/types'
import { MonitorPollScheduleCard } from '../components/MonitorPollScheduleCard'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'
import { useMountAsync } from '../hooks/useMountAsync'

export function DynamicMonitorPage() {
  const { showToast } = useToast()
  const [checking, setChecking] = useState(false)
  const [pollSchedule, setPollSchedule] = useState<MonitorPollSchedule | null>(null)

  const loadStatus = useCallback(async () => {
    const status = await getDynamicMonitorStatus()
    setPollSchedule(status.poll_schedule)
  }, [])

  useMountAsync(loadStatus)

  const handleCheck = async () => {
    setChecking(true)
    try {
      const result = await triggerDynamicCheck()
      showToast(result.success ? 'success' : 'error', result.message)
      await loadStatus()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '操作失败')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start gap-4">
        <div className="shrink-0 basis-full md:basis-auto md:max-w-[14rem]">
          <h2 className="text-2xl font-bold text-foreground">动态订阅管理</h2>
          <p className="mt-1 text-sm text-muted-foreground">管理 UP 主动态推送到 QQ 群的订阅</p>
        </div>

        {pollSchedule ? (
          <div className="w-fit max-w-full shrink-0 self-start basis-full md:basis-auto">
            <MonitorPollScheduleCard title="当前 API 请求频率（动态）" schedule={pollSchedule} />
          </div>
        ) : null}

        <button
          type="button"
          className="btn-secondary shrink-0 self-start basis-full sm:basis-auto sm:w-auto md:ml-auto md:self-center"
          disabled={checking}
          onClick={() => void handleCheck()}
        >
          {checking ? '检查中…' : '立即检查'}
        </button>
      </div>

      <TargetMappingSection type="dynamic" onTargetsChanged={loadStatus} />
    </div>
  )
}
