export type MonitorMode = 'api-polling' | 'websocket'

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

export function getLiveMonitorMode(useWebsocket: boolean): MonitorMode {
  return useWebsocket ? 'websocket' : 'api-polling'
}

export function getLiveMonitorModeLabel(useWebsocket: boolean): string {
  return useWebsocket ? 'WebSocket 实时 + API 备用' : 'API 轮询'
}

export function MonitorModeBadge({ mode }: MonitorModeBadgeProps) {
  return <span className={MODE_CLASS[mode]}>{MODE_LABEL[mode]}</span>
}
