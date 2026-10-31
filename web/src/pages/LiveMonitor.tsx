import { useCallback, useState } from 'react'
import { getLiveMonitorStatus, triggerLiveCheck } from '../api/client'
import type { MonitorPollSchedule } from '../api/types'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'
import { useMountAsync } from '../hooks/useMountAsync'

export function LiveMonitorPage() {
  const { showToast } = useToast()
  const [checking, setChecking] = useState(false)
  const [pollSchedule, setPollSchedule] = useState<MonitorPollSchedule | null>(null)

  const loadStatus = useCallback(async () => {
    const status = await getLiveMonitorStatus()
    setPollSchedule(status.poll_schedule)
  }, [])

  useMountAsync(loadStatus)

  const handleCheck = async () => {
    setChecking(true)
    try {
      const result = await triggerLiveCheck()
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
      type="live"
      title="B 站直播订阅"
      description="管理 B 站直播间开播通知推送到 QQ 群与好友的订阅"
      pollSchedule={pollSchedule}
      checking={checking}
      onCheck={() => void handleCheck()}
      onTargetsChanged={loadStatus}
    />
  )
}
