import { useCallback, useState } from 'react'
import { getDynamicMonitorStatus, triggerDynamicCheck } from '../api/client'
import type { MonitorPollSchedule } from '../api/types'
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
    <TargetMappingSection
      type="dynamic"
      title="B 站动态订阅"
      description="管理 UP 主动态推送到 QQ 群与好友的订阅"
      pollSchedule={pollSchedule}
      checking={checking}
      onCheck={() => void handleCheck()}
      onTargetsChanged={loadStatus}
    />
  )
}
