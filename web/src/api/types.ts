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

export interface CommandAliasEntry {
  enabled: boolean
  triggers: string[]
}

export interface XProxySettings {
  enabled: boolean
  scheme: string
  host: string
  port: number
  username: string
  password_configured: boolean
}

export interface Settings {
  dynamic_monitor_interval: number
  dynamic_monitor_use_stagger: boolean
  dynamic_enable_screenshot: boolean
  dynamic_template_push: string
  dynamic_template_pinned: string
  dynamic_template_query_latest: string
  dynamic_template_query_pinned: string
  dynamic_template_extract: string
  dynamic_template_extract_empty: string
  dynamic_template_extract_failed: string
  dynamic_template_extract_image_label: string
  live_monitor_interval: number
  live_monitor_include_info: boolean
  live_monitor_use_websocket: boolean
  live_template_start: string
  live_template_end: string
  link_template_video: string
  link_template_live: string
  link_template_douyin: string
  x_monitor_interval: number
  x_monitor_use_stagger: boolean
  x_template_push: string
  bilibili_cookie: CookieStatus
  douyin_cookie: CookieStatus
  x_api_bearer: CookieStatus
  x_proxy: XProxySettings
  status_check_allowed_qq: string[]
  nonebot_superusers: string[]
  command_aliases: Record<string, CommandAliasEntry>
  /** 习惯性前缀（如 !、。），与 COMMAND_START 无关，可编辑，保存后立即生效 */
  command_extra_prefixes: string[]
  /** 只读：当前生效的完整前缀集合 = COMMAND_START ∪ command_extra_prefixes */
  command_prefixes: string[]
  /** B 站发视频共享目录；空则使用平台默认 */
  link_parser_shared_media_dir: string
  /** 只读：当前平台默认目录 */
  link_parser_shared_media_dir_default: string
  /** 只读：解析后的实际目录 */
  link_parser_shared_media_dir_resolved: string
}

export type SettingsUpdate = Partial<
  Omit<
    Settings,
    | 'bilibili_cookie'
    | 'douyin_cookie'
    | 'x_api_bearer'
    | 'x_proxy'
    | 'command_prefixes'
    | 'link_parser_shared_media_dir_default'
    | 'link_parser_shared_media_dir_resolved'
  >
> & {
  x_api_bearer?: string
  x_proxy_enabled?: boolean
  x_proxy_scheme?: string
  x_proxy_host?: string
  x_proxy_port?: number
  x_proxy_username?: string
  /** 明文；undefined=不改；""=清除 */
  x_proxy_password?: string
}

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

export interface XTarget {
  id: number
  username: string
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

export interface XTargetCreate {
  username: string
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
export type XTargetUpdate = Partial<Omit<XTarget, 'id' | 'created_at'>>

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
  group_list_available: boolean
}

export interface Friend {
  user_id: string
  nickname: string | null
}

export interface PrivateMessagePolicy {
  restrict: boolean
  enabled_user_ids: string[]
  users: Friend[]
  friend_list_available: boolean
}

export interface StatusCheckDisplayOptions {
  show_detailed: boolean
  show_uptime: boolean
  show_memory: boolean
}

export interface GroupStatusPolicy {
  restrict: boolean
  enabled_group_ids: string[]
  groups: Group[]
  display: StatusCheckDisplayOptions
  group_list_available: boolean
}

export interface GroupSpecialTitlePolicy {
  restrict: boolean
  enabled_group_ids: string[]
  groups: Group[]
  daily_limit: number
  group_list_available: boolean
}

export interface PrivateStatusPolicy {
  restrict: boolean
  enabled_user_ids: string[]
  users: Friend[]
  display: StatusCheckDisplayOptions
  friend_list_available: boolean
}

export interface LinkParserGroupPolicyItem {
  group_id: string
  group_name: string | null
  member_count: number | null
  customized: boolean
  video_enabled: boolean
  live_enabled: boolean
  dynamic_enabled: boolean
  send_video_enabled: boolean
}

export interface LinkParserGroupPolicyList {
  groups: LinkParserGroupPolicyItem[]
  group_list_available: boolean
}

export interface LinkParserGroupPolicyMutation {
  item: LinkParserGroupPolicyItem
}

export interface LinkParserUserPolicyItem {
  user_id: string
  nickname: string | null
  name: string | null
  customized: boolean
  video_enabled: boolean
  live_enabled: boolean
  dynamic_enabled: boolean
  send_video_enabled: boolean
}

export interface LinkParserUserPolicyList {
  users: LinkParserUserPolicyItem[]
  friend_list_available: boolean
}

export interface LinkParserUserPolicyMutation {
  item: LinkParserUserPolicyItem
}

export interface DouyinLinkParserGroupPolicyItem {
  group_id: string
  group_name?: string | null
  member_count?: number | null
  customized: boolean
  enabled: boolean
}

export interface DouyinLinkParserGroupPolicyList {
  groups: DouyinLinkParserGroupPolicyItem[]
  group_list_available: boolean
}

export interface DouyinLinkParserGroupPolicyMutation {
  item: DouyinLinkParserGroupPolicyItem
}

export interface DouyinLinkParserUserPolicyItem {
  user_id: string
  nickname?: string | null
  name?: string | null
  customized: boolean
  enabled: boolean
}

export interface DouyinLinkParserUserPolicyList {
  users: DouyinLinkParserUserPolicyItem[]
  friend_list_available: boolean
}

export interface DouyinLinkParserUserPolicyMutation {
  item: DouyinLinkParserUserPolicyItem
}

export interface DouyinCookieStatus {
  configured: boolean
  preview?: string | null
  message?: string
}

export interface DouyinQrcodeStart {
  session_id: string
  image_base64: string
}

export interface DouyinQrcodeLoginResult {
  success: boolean
  message: string
  configured: boolean
  preview?: string | null
}

export interface DouyinLogoutResult {
  success: boolean
  message: string
}

export interface XBearerStatus {
  configured: boolean
  preview?: string | null
  message?: string
}

export interface XBearerTestResult {
  success: boolean
  message: string
  username?: string | null
  name?: string | null
  user_id?: string | null
}

export interface LinkParserUserPolicyInput {
  user_id: string
  name?: string
  video_enabled: boolean
  live_enabled: boolean
  dynamic_enabled: boolean
  send_video_enabled: boolean
}

// Monitors
export interface MonitorStatus {
  running: boolean
  uptime_seconds: number
  last_check_at: string | null
}

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

export interface DynamicMonitorStatus {
  enabled: boolean
  interval_seconds: number
  target_count: number
  poll_schedule: MonitorPollSchedule
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
  poll_schedule: MonitorPollSchedule
  last_check_at: string | null
  last_error: string | null
  live_rooms: number
  checks_total: number
}

export interface XMonitorStatus {
  enabled: boolean
  interval_seconds: number
  target_count: number
  poll_schedule: MonitorPollSchedule
  last_check_at: string | null
  last_error: string | null
  checks_total: number
  new_tweets_total: number
}

export interface SystemMonitorStatus {
  process_cpu_percent: number
  process_memory_mb: number
  db_size_mb: number
  log_size_mb: number
  cpu_percent: number
  cpu_count: number
  memory_percent: number
  memory_used_mb: number
  memory_total_mb: number
  memory_limit_mb: number | null
  disk_percent: number
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
  git_branch: string | null
  git_tag: string | null
  git_commit: string | null
  build_time: string | null
  build_number: string | null
  python_version: string
  fastapi_version: string | null
  react_version: string | null
  tailwindcss_version: string | null
  update_available: boolean | null
  update_url: string | null
}

export interface MonitorActionResult {
  success: boolean
  message: string
}

export interface RuntimeLogEntry {
  session_id: string
  entry_id: number
  ts: string
  level: string
  logger: string
  message: string
}

export interface RecentLogsResponse {
  items: RuntimeLogEntry[]
  total_buffered: number
  log_session_id: string
}

export interface ApiError {
  detail: string
}

// Rust RCON
export interface RustRconPasswordStatus {
  configured: boolean
  preview: string | null
}

export interface RustRconBinding {
  id: number
  alias: string
  host: string
  port: number
  password: RustRconPasswordStatus
  enabled: boolean
  name: string | null
  allowed_qq_ids: string[]
  created_at: string
  updated_at: string
}

export interface RustRconBindingCreate {
  alias: string
  host: string
  port: number
  password: string
  enabled?: boolean
  name?: string | null
  allowed_qq_ids: string[]
}

export interface RustRconBindingUpdate {
  alias?: string
  host?: string
  port?: number
  password?: string
  enabled?: boolean
  name?: string | null
  allowed_qq_ids?: string[]
}

export interface RustRconGroupPolicyItem {
  group_id: string
  group_name: string | null
  member_count: number | null
  customized: boolean
  enabled: boolean
}

export interface RustRconGroupPolicyList {
  groups: RustRconGroupPolicyItem[]
  group_list_available: boolean
}

export interface RustRconGroupPolicyMutation {
  item: RustRconGroupPolicyItem
}

export interface RustRconUserPolicyItem {
  user_id: string
  nickname: string | null
  name: string | null
  customized: boolean
  enabled: boolean
}

export interface RustRconUserPolicyList {
  users: RustRconUserPolicyItem[]
  friend_list_available: boolean
}

export interface RustRconUserPolicyMutation {
  item: RustRconUserPolicyItem
}

// Rust player points / Steam bindings
export interface RustPlayerOverviewItem {
  group_id: string | null
  user_id: string
  points: number
  steam_id: string | null
}

export interface RustPlayerOverviewResponse {
  items: RustPlayerOverviewItem[]
}

export interface RustPlayerPointsUpdate {
  group_id: string
  user_id: string
  points: number
}

export interface RustCheckInConfig {
  min_points: number
  max_points: number
  online_bonus_points: number
  steam_bind_bonus_points: number
  rcon_binding_id: number
}

export interface RustShopItem {
  id: number
  name: string
  item_id: string
  points_cost: number
  enabled: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface RustShopItemListResponse {
  items: RustShopItem[]
}

export interface RustShopItemCreate {
  name: string
  item_id: string
  points_cost: number
  enabled?: boolean
  sort_order?: number
}

export interface RustShopItemUpdate {
  name?: string
  item_id?: string
  points_cost?: number
  enabled?: boolean
  sort_order?: number
}

export interface RustRconCustomCommand {
  id: number
  name: string
  template: string
  binding_id: number
  enabled: boolean
  allowed_qq_ids: string[]
  created_at: string
  updated_at: string
}

export interface RustRconCustomCommandListResponse {
  items: RustRconCustomCommand[]
}

export interface RustRconCustomCommandCreate {
  name: string
  template: string
  binding_id: number
  allowed_qq_ids: string[]
  enabled?: boolean
}

export interface RustRconCustomCommandUpdate {
  name?: string
  template?: string
  binding_id?: number
  allowed_qq_ids?: string[]
  enabled?: boolean
}
