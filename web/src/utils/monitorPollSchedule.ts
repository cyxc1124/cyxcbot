export const DYNAMIC_MIN_TICK_INTERVAL_SECONDS = 3
export const LIVE_BATCH_REQUEST_GAP_SECONDS = 0.3
export const LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS = 300

export interface MonitorPollSchedule {
  strategy: string
  target_count: number
  configured_interval_seconds: number
  min_tick_interval_seconds?: number | null
  poll_interval_seconds?: number | null
  batch_gap_seconds?: number | null
  use_websocket?: boolean | null
  tick_interval_seconds: number
  per_target_cycle_seconds: number
  requests_per_second_avg: number
  requests_per_second_peak: number
  meets_configured_interval: boolean
  warning?: string | null
}

function round(value: number, digits = 2): number {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

export function computeDynamicPollSchedule(
  targetCount: number,
  configuredIntervalSeconds: number,
  minTickIntervalSeconds = DYNAMIC_MIN_TICK_INTERVAL_SECONDS,
): MonitorPollSchedule {
  if (targetCount <= 0) {
    return {
      strategy: 'stagger',
      target_count: 0,
      configured_interval_seconds: configuredIntervalSeconds,
      min_tick_interval_seconds: minTickIntervalSeconds,
      tick_interval_seconds: 0,
      per_target_cycle_seconds: 0,
      requests_per_second_avg: 0,
      requests_per_second_peak: 0,
      meets_configured_interval: true,
      warning: null,
    }
  }

  const idealTick = configuredIntervalSeconds / targetCount
  const tickInterval = Math.max(minTickIntervalSeconds, idealTick)
  const perTargetCycle = tickInterval * targetCount
  const meetsConfigured = perTargetCycle <= configuredIntervalSeconds + 0.01
  const peakRps = 1 / tickInterval
  const avgRps = targetCount / perTargetCycle

  let warning: string | null = null
  if (!meetsConfigured) {
    warning =
      `当前 ${targetCount} 个 UP 主较多，每人实际约 ${Math.round(perTargetCycle)} 秒检查一次` +
      `（设置 ${configuredIntervalSeconds} 秒）。建议增大检查间隔或减少订阅数量。`
  }

  return {
    strategy: 'stagger',
    target_count: targetCount,
    configured_interval_seconds: configuredIntervalSeconds,
    min_tick_interval_seconds: minTickIntervalSeconds,
    tick_interval_seconds: round(tickInterval),
    per_target_cycle_seconds: round(perTargetCycle),
    requests_per_second_avg: round(avgRps),
    requests_per_second_peak: round(peakRps),
    meets_configured_interval: meetsConfigured,
    warning,
  }
}

export function computeLivePollSchedule(
  targetCount: number,
  configuredIntervalSeconds: number,
  useWebsocket: boolean,
  batchGapSeconds = LIVE_BATCH_REQUEST_GAP_SECONDS,
): MonitorPollSchedule {
  const pollInterval = useWebsocket
    ? Math.max(LIVE_WEBSOCKET_BACKUP_MIN_INTERVAL_SECONDS, configuredIntervalSeconds * 5)
    : configuredIntervalSeconds
  const strategy = useWebsocket ? 'websocket_primary' : 'batch'

  if (targetCount <= 0) {
    return {
      strategy,
      target_count: 0,
      configured_interval_seconds: configuredIntervalSeconds,
      poll_interval_seconds: pollInterval,
      batch_gap_seconds: batchGapSeconds,
      use_websocket: useWebsocket,
      tick_interval_seconds: 0,
      per_target_cycle_seconds: 0,
      requests_per_second_avg: 0,
      requests_per_second_peak: 0,
      meets_configured_interval: true,
      warning: null,
    }
  }

  const burstDuration = batchGapSeconds * Math.max(0, targetCount - 1)
  const peakRps = 1 / batchGapSeconds
  const avgRps = targetCount / pollInterval

  let warning: string | null = null
  if (!useWebsocket && peakRps >= 2) {
    warning =
      `未启用 WebSocket 时，每 ${pollInterval} 秒会集中轮询 ${targetCount} 个房间，` +
      `峰值约 ${peakRps.toFixed(1)} 次/秒。建议启用 WebSocket 或增大检查间隔。`
  } else if (useWebsocket && peakRps >= 2) {
    warning =
      `API 备用轮询每 ${pollInterval} 秒执行一次，峰值约 ${peakRps.toFixed(1)} 次/秒` +
      `（持续约 ${burstDuration.toFixed(1)} 秒）。`
  }

  return {
    strategy,
    target_count: targetCount,
    configured_interval_seconds: configuredIntervalSeconds,
    poll_interval_seconds: pollInterval,
    batch_gap_seconds: batchGapSeconds,
    use_websocket: useWebsocket,
    tick_interval_seconds: round(batchGapSeconds),
    per_target_cycle_seconds: round(pollInterval),
    requests_per_second_avg: round(avgRps),
    requests_per_second_peak: round(peakRps),
    meets_configured_interval: true,
    warning,
  }
}

export function formatRequestsPerSecond(value: number): string {
  if (value <= 0) return '0 次/秒'
  if (value < 0.01) return '< 0.01 次/秒'
  return `${value.toFixed(2)} 次/秒`
}

export function strategyLabel(strategy: string): string {
  switch (strategy) {
    case 'stagger':
      return '分散检查'
    case 'batch':
      return '批量轮询'
    case 'websocket_primary':
      return 'WebSocket 为主'
    default:
      return strategy
  }
}
