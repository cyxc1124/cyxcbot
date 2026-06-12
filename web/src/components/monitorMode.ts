export type MonitorMode = 'api-polling' | 'websocket'

export function getLiveMonitorMode(useWebsocket: boolean): MonitorMode {
  return useWebsocket ? 'websocket' : 'api-polling'
}

export function getLiveMonitorModeLabel(useWebsocket: boolean): string {
  return useWebsocket ? 'WebSocket 实时 + API 备用' : 'API 轮询'
}
