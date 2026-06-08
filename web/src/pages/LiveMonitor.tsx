import { useState } from 'react'
import { triggerLiveCheck } from '../api/client'
import { TargetMappingSection } from '../components/TargetMappingSection'
import { useToast } from '../contexts/ToastContext'

export function LiveMonitorPage() {
  const { showToast } = useToast()
  const [checking, setChecking] = useState(false)

  const handleCheck = async () => {
    setChecking(true)
    try {
      const result = await triggerLiveCheck()
      showToast(result.success ? 'success' : 'error', result.message)
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '操作失败')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">直播订阅管理</h2>
          <p className="mt-1 text-sm text-slate-500">管理 B 站直播间开播通知推送到 QQ 群的订阅</p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          disabled={checking}
          onClick={() => void handleCheck()}
        >
          {checking ? '检查中…' : '立即检查'}
        </button>
      </div>

      <div className="card">
        <TargetMappingSection type="live" />
      </div>
    </div>
  )
}
