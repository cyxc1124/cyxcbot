import type { MonitorPollSchedule } from '../utils/monitorPollSchedule'
import { formatRequestsPerSecond, strategyLabel } from '../utils/monitorPollSchedule'

interface MonitorPollScheduleCardProps {
  title: string
  schedule: MonitorPollSchedule
  emptyHint?: string
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  )
}

export function MonitorPollScheduleCard({
  title,
  schedule,
  emptyHint = '暂无订阅目标，不会产生 API 请求。',
}: MonitorPollScheduleCardProps) {
  if (schedule.target_count <= 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
        <div className="font-medium text-foreground">{title}</div>
        <p className="mt-1">{emptyHint}</p>
      </div>
    )
  }

  const modeDetail =
    schedule.strategy === 'stagger'
      ? `每 ${schedule.tick_interval_seconds} 秒检查 1 个 UP 主`
      : schedule.strategy === 'websocket_primary'
        ? `WebSocket 实时检测；API 备用每 ${schedule.poll_interval_seconds ?? schedule.per_target_cycle_seconds} 秒轮询一轮`
        : `每 ${schedule.poll_interval_seconds ?? schedule.configured_interval_seconds} 秒批量检查一轮`

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/20 px-4 py-3">
      <div>
        <div className="text-sm font-medium text-foreground">{title}</div>
        <p className="mt-1 text-xs text-muted-foreground">
          {strategyLabel(schedule.strategy)} · {schedule.target_count} 个目标 · {modeDetail}
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="平均请求频率"
          value={formatRequestsPerSecond(schedule.requests_per_second_avg)}
        />
        <Metric
          label="峰值请求频率"
          value={formatRequestsPerSecond(schedule.requests_per_second_peak)}
        />
        <Metric
          label="每人检查周期"
          value={`约 ${Math.round(schedule.per_target_cycle_seconds)} 秒`}
        />
        <Metric
          label="设置周期"
          value={
            schedule.meets_configured_interval
              ? `${schedule.configured_interval_seconds} 秒（可达）`
              : `${schedule.configured_interval_seconds} 秒（已放宽）`
          }
        />
      </div>

      {schedule.warning ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">{schedule.warning}</p>
      ) : (
        <p className="text-xs text-muted-foreground">
          峰值频率表示最密集时的 API 请求速度；平均频率按完整轮询周期估算。
        </p>
      )}
    </div>
  )
}
