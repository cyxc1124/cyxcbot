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
  dynamic_template_push: string
  dynamic_template_pinned: string
  dynamic_template_query_latest: string
  dynamic_template_query_pinned: string
  live_monitor_interval: number
  live_monitor_include_info: boolean
  live_monitor_use_websocket: boolean
  live_template_start: string
  live_template_end: string
  link_template_video: string
  link_template_live: string
  bilibili_cookie: CookieStatus
  audit_log_retention_days: number
  event_retention_days: number
  status_check_allowed_qq: string[]
  nonebot_superusers: string[]
  bilibili_link_parser_enabled: boolean
  bilibili_link_parser_private_enabled: boolean
  bilibili_link_parser_video_enabled: boolean
  bilibili_link_parser_live_enabled: boolean
}

export type SettingsUpdate = Partial<Omit<Settings, 'bilibili_cookie'>>

export interface CookieTestResult {
  success: boolean
  message: string
  status?: BilibiliConnectionStatusKind | ''
  username?: string | null
  uid?: string | null
}

export interface BilibiliQrcodeStart {
  url: string
  qrcode: Record<string, unknown>
}

export interface BilibiliQrcodeLoginResult {
  success: boolean
  username: string | null
  uid: string | null
  message: string
}

export interface BilibiliLogoutResult {
  success: boolean
  message: string
}

// Targets / Mappings
export interface DynamicTarget {
  id: number
  uid: string
  name: string | null
  enabled: boolean
  at_all: boolean
  group_ids: string[]
  user_ids: string[]
  created_at: string
}

export interface LiveTarget {
  id: number
  room_id: string
  name: string | null
  enabled: boolean
  at_all: boolean
  group_ids: string[]
  user_ids: string[]
  created_at: string
}

export interface DynamicTargetCreate {
  uid: string
  name?: string
  enabled?: boolean
  at_all?: boolean
  group_ids: string[]
  user_ids?: string[]
}

export interface LiveTargetCreate {
  room_id: string
  name?: string
  enabled?: boolean
  at_all?: boolean
  group_ids: string[]
  user_ids?: string[]
}

export type DynamicTargetUpdate = Partial<
  Omit<DynamicTarget, 'id' | 'created_at'>
>
export type LiveTargetUpdate = Partial<Omit<LiveTarget, 'id' | 'created_at'>>

// Groups
export interface Group {
  group_id: string
  group_name: string | null
  member_count?: number | null
}

export interface GroupMessagePolicy {
  restrict: boolean
  enabled_group_ids: string[]
  groups: Group[]
}

export interface Friend {
  user_id: string
  nickname: string | null
}

export interface PrivateMessagePolicy {
  restrict: boolean
  enabled_user_ids: string[]
  users: Friend[]
}

export interface LinkParserGlobalPolicy {
  enabled: boolean
  video_enabled: boolean
  live_enabled: boolean
}

export interface LinkParserGroupPolicyItem {
  group_id: string
  group_name: string | null
  member_count: number | null
  customized: boolean
  enabled: boolean
  video_enabled: boolean
  live_enabled: boolean
}

export interface LinkParserGroupPolicyList {
  global_policy: LinkParserGlobalPolicy
  groups: LinkParserGroupPolicyItem[]
}

export interface LinkParserGroupPolicyMutation {
  global_policy: LinkParserGlobalPolicy
  item: LinkParserGroupPolicyItem
}

export interface LinkParserUserPolicyItem {
  user_id: string
  nickname: string | null
  name: string | null
  customized: boolean
  enabled: boolean
  video_enabled: boolean
  live_enabled: boolean
}

export interface LinkParserUserPolicyList {
  global_policy: LinkParserGlobalPolicy
  users: LinkParserUserPolicyItem[]
}

export interface LinkParserUserPolicyMutation {
  global_policy: LinkParserGlobalPolicy
  item: LinkParserUserPolicyItem
}

export interface LinkParserUserPolicyInput {
  user_id: string
  name?: string
  enabled: boolean
  video_enabled: boolean
  live_enabled: boolean
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

export type BilibiliConnectionStatusKind =
  | 'logged_in'
  | 'not_configured'
  | 'session_expired'
  | 'verify_failed'

export interface BilibiliConnectionStatus {
  status: BilibiliConnectionStatusKind
  configured: boolean
  logged_in: boolean
  username: string | null
  uid: string | null
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

export interface AboutInfo {
  app_name: string
  web_frontend: string
  backend_framework: string
  build_version: string
  python_version: string
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
