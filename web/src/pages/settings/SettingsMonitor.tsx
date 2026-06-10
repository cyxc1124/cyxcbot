import { useCallback, useMemo, useState } from 'react'
import { MonitorPollScheduleCard } from '../../components/MonitorPollScheduleCard'
import { ToggleSwitch } from '../../components/ToggleSwitch'
import { useMountAsync } from '../../hooks/useMountAsync'
import { getDynamicMonitorStatus, getLiveMonitorStatus } from '../../api/client'
import {
  computeDynamicPollSchedule,
  computeLivePollSchedule,
} from '../../utils/monitorPollSchedule'
import { useSettingsForm } from './SettingsContext'

function SettingToggleRow({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center gap-4 py-2">
      <span className="min-w-0 flex-1 text-sm text-foreground">{label}</span>
      <div className="flex w-[5.75rem] shrink-0 items-center justify-end gap-2">
        <span
          className={`w-10 shrink-0 text-right text-xs ${
            checked ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'
          }`}
        >
          {checked ? '已启用' : '已关闭'}
        </span>
        <ToggleSwitch checked={checked} disabled={disabled} onChange={onChange} />
      </div>
    </div>
  )
}

export function SettingsMonitorPage() {
  const { settings, setSettings, formDisabled, saving, handleSubmit } = useSettingsForm()
  const [dynamicTargetCount, setDynamicTargetCount] = useState(0)
  const [liveTargetCount, setLiveTargetCount] = useState(0)

  const loadTargetCounts = useCallback(async () => {
    const [dynamicStatus, liveStatus] = await Promise.all([
      getDynamicMonitorStatus(),
      getLiveMonitorStatus(),
    ])
    setDynamicTargetCount(dynamicStatus.target_count)
    setLiveTargetCount(liveStatus.target_count)
  }, [])

  useMountAsync(loadTargetCounts)

  const dynamicSchedule = useMemo(() => {
    const interval = settings?.dynamic_monitor_interval
    if (!interval || interval < 10) return null
    return computeDynamicPollSchedule(
      dynamicTargetCount,
      interval,
      settings?.dynamic_monitor_use_stagger ?? true,
    )
  }, [
    dynamicTargetCount,
    settings?.dynamic_monitor_interval,
    settings?.dynamic_monitor_use_stagger,
  ])

  const liveSchedule = useMemo(() => {
    const interval = settings?.live_monitor_interval
    if (!interval || interval < 30) return null
    return computeLivePollSchedule(
      liveTargetCount,
      interval,
      settings?.live_monitor_use_websocket ?? true,
    )
  }, [
    liveTargetCount,
    settings?.live_monitor_interval,
    settings?.live_monitor_use_websocket,
  ])

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">动态监控</h3>
        <div className="max-w-xs">
          <label className="label" htmlFor="dynamic_interval">
            检查间隔（秒）
          </label>
          <input
            id="dynamic_interval"
            type="number"
            min={30}
            max={3600}
            className="input"
            value={settings?.dynamic_monitor_interval ?? ''}
            disabled={formDisabled}
            onChange={(e) =>
              setSettings((s) =>
                s ? { ...s, dynamic_monitor_interval: Number(e.target.value) } : s,
              )
            }
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {settings?.dynamic_monitor_use_stagger ?? true
              ? '期望每个 UP 主约每 N 秒检查一次；目标较多时会自动分散请求，且单次间隔不低于 3 秒。'
              : '每 N 秒依次检查全部 UP 主；订阅较多时可能短时集中请求 API。'}
          </p>
        </div>
        {dynamicSchedule ? (
          <MonitorPollScheduleCard
            title="API 请求频率预估（动态）"
            schedule={dynamicSchedule}
          />
        ) : null}
        <div className="divide-y divide-border border-t border-border pt-1">
          <SettingToggleRow
            label="启用分散检查（推荐）"
            checked={settings?.dynamic_monitor_use_stagger ?? true}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) =>
                s ? { ...s, dynamic_monitor_use_stagger: checked } : s,
              )
            }
          />
          <SettingToggleRow
            label="启用动态截图（Playwright）"
            checked={settings?.dynamic_enable_screenshot ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, dynamic_enable_screenshot: checked } : s))
            }
          />
        </div>
      </div>

      <div className="card space-y-4">
        <h3 className="font-semibold text-foreground">直播监控</h3>
        <div className="max-w-xs">
          <label className="label" htmlFor="live_interval">
            检查间隔（秒）
          </label>
          <input
            id="live_interval"
            type="number"
            min={30}
            max={3600}
            className="input"
            value={settings?.live_monitor_interval ?? ''}
            disabled={formDisabled}
            onChange={(e) =>
              setSettings((s) =>
                s ? { ...s, live_monitor_interval: Number(e.target.value) } : s,
              )
            }
          />
          <p className="mt-1 text-xs text-muted-foreground">
            启用 WebSocket 时此间隔主要影响 API 备用轮询；未启用时即为批量轮询周期。
          </p>
        </div>
        {liveSchedule ? (
          <MonitorPollScheduleCard title="API 请求频率预估（直播）" schedule={liveSchedule} />
        ) : null}
        <div className="divide-y divide-border border-t border-border pt-1">
          <SettingToggleRow
            label="通知包含详细房间信息"
            checked={settings?.live_monitor_include_info ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, live_monitor_include_info: checked } : s))
            }
          />
          <SettingToggleRow
            label="启用 WebSocket 实时监控"
            checked={settings?.live_monitor_use_websocket ?? false}
            disabled={formDisabled || saving}
            onChange={(checked) =>
              setSettings((s) => (s ? { ...s, live_monitor_use_websocket: checked } : s))
            }
          />
        </div>
      </div>

      <button type="submit" className="btn-primary" disabled={saving || formDisabled}>
        {saving ? '保存中…' : '保存设置'}
      </button>
    </form>
  )
}
