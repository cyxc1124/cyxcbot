import { useCallback, useState } from 'react'
import { getXMonitorStatus, triggerXCheck } from '../api/client'
import type { MonitorPollSchedule } from '../api/types'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'
import { useMountAsync } from '../hooks/useMountAsync'

export function XMonitorPage() {
  const { showToast } = useToast()
  const [checking, setChecking] = useState(false)
  const [pollSchedule, setPollSchedule] = useState<MonitorPollSchedule | null>(null)

  const loadStatus = useCallback(async () => {
    const status = await getXMonitorStatus()
    setPollSchedule(status.poll_schedule)
  }, [])

  useMountAsync(loadStatus)

  const handleCheck = async () => {
    setChecking(true)
    try {
      const result = await triggerXCheck()
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
      type="x"
      title="X 推文订阅"
      description="管理 X 博主推文推送到 QQ 群与好友的订阅"
      pollSchedule={pollSchedule}
      checking={checking}
      onCheck={() => void handleCheck()}
      onTargetsChanged={loadStatus}
    />
  )
}
