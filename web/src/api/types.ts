// Auth & Setup
export interface SetupStatus {
  initialized: boolean
}

export interface SetupRequest {
  username: string
  password: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface User {
  id: number
  username: string
  is_admin: boolean
}

// Settings
export interface CookieStatus {
  configured: boolean
  preview: string | null
}

export interface Settings {
  dynamic_monitor_interval: number
  dynamic_enable_screenshot: boolean
  live_monitor_interval: number
  live_monitor_include_info: boolean
  live_monitor_use_websocket: boolean
  bilibili_cookie: CookieStatus
  audit_log_retention_days: number
  event_retention_days: number
}

export type SettingsUpdate = Partial<
  Omit<Settings, 'bilibili_cookie'> & { bilibili_cookie?: string }
>

export interface CookieTestResult {
  success: boolean
  message: string
}

// Targets / Mappings
export interface DynamicTarget {
  id: number
  uid: string
  name: string | null
  enabled: boolean
  group_ids: string[]
  created_at: string
}

export interface LiveTarget {
  id: number
  room_id: string
  name: string | null
  enabled: boolean
  group_ids: string[]
  created_at: string
}

export interface DynamicTargetCreate {
  uid: string
  name?: string
  enabled?: boolean
  group_ids: string[]
}

export interface LiveTargetCreate {
  room_id: string
  name?: string
  enabled?: boolean
  group_ids: string[]
}

export type DynamicTargetUpdate = Partial<
  Omit<DynamicTarget, 'id' | 'created_at'>
>
export type LiveTargetUpdate = Partial<Omit<LiveTarget, 'id' | 'created_at'>>

// Groups
export interface Group {
  group_id: string
  group_name: string | null
}

// Monitors
export interface MonitorStatus {
  running: boolean
  uptime_seconds: number
  last_check_at: string | null
}

export interface DynamicMonitorStatus {
  enabled: boolean
  interval_seconds: number
  target_count: number
  last_check_at: string | null
  last_fetch_at: string | null
  last_error: string | null
  checks_total: number
  new_dynamics_total: number
}

export interface LiveMonitorStatus {
  enabled: boolean
  interval_seconds: number
  use_websocket: boolean
  target_count: number
  last_check_at: string | null
  last_error: string | null
  live_rooms: number
  checks_total: number
}

export interface SystemMonitorStatus {
  cpu_percent: number
  memory_percent: number
  memory_used_mb: number
  memory_total_mb: number
  disk_percent: number
  python_version: string
  bot_version: string
}

export interface BilibiliConnectionStatus {
  configured: boolean
  logged_in: boolean
  username: string | null
  uid: string | null
  message: string
}

export interface QqBotInfo {
  qq: string
  nickname: string | null
}

export interface QqConnectionStatus {
  connected: boolean
  bot_count: number
  bots: QqBotInfo[]
  message: string
}

export interface ConnectionsStatus {
  bilibili: BilibiliConnectionStatus
  qq: QqConnectionStatus
}

export interface MonitorActionResult {
  success: boolean
  message: string
}

// Audit & Events
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AuditLog {
  id: number
  action: string
  actor: string
  resource_type: string | null
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

export interface SystemEvent {
  id: number
  level: 'debug' | 'info' | 'warning' | 'error'
  category: string
  message: string
  details: Record<string, unknown> | null
  created_at: string
}

export interface AuditLogQuery {
  page?: number
  page_size?: number
  action?: string
  from?: string
  to?: string
}

export interface EventQuery {
  page?: number
  page_size?: number
  level?: string
  category?: string
}

export interface ApiError {
  detail: string
}
