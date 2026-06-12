import type { MonitorMode } from './monitorMode'

interface MonitorModeBadgeProps {
  mode: MonitorMode
}

const MODE_LABEL: Record<MonitorMode, string> = {
  'api-polling': 'API 轮询',
  websocket: 'WebSocket',
}

const MODE_CLASS: Record<MonitorMode, string> = {
  'api-polling': 'badge-info',
  websocket: 'badge-success',
}

export function MonitorModeBadge({ mode }: MonitorModeBadgeProps) {
  return <span className={MODE_CLASS[mode]}>{MODE_LABEL[mode]}</span>
}
