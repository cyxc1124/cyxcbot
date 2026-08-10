import type {
  AboutInfo,
  BilibiliLogoutResult,
  BilibiliQrcodeLoginResult,
  BilibiliQrcodeStart,
  CookieTestResult,
  DynamicMonitorStatus,
  DynamicTarget,
  DynamicTargetCreate,
  DynamicTargetUpdate,
  Friend,
  Group,
  GroupMessagePolicy,
  DouyinCookieStatus,
  DouyinLogoutResult,
  DouyinQrcodeLoginResult,
  DouyinQrcodeStart,
  DouyinLinkParserGroupPolicyList,
  DouyinLinkParserGroupPolicyMutation,
  DouyinLinkParserUserPolicyList,
  DouyinLinkParserUserPolicyMutation,
  LinkParserGroupPolicyList,
  LinkParserGroupPolicyMutation,
  LinkParserUserPolicyInput,
  LinkParserUserPolicyList,
  LinkParserUserPolicyMutation,
  PrivateMessagePolicy,
  PrivateStatusPolicy,
  GroupStatusPolicy,
  GroupSpecialTitlePolicy,
  StatusCheckDisplayOptions,
  LiveMonitorStatus,
  LiveTarget,
  LiveTargetCreate,
  LiveTargetUpdate,
  LoginRequest,
  LoginResponse,
  MonitorActionResult,
  MonitorStatus,
  RecentLogsResponse,
  XBearerStatus,
  XBearerTestResult,
  XMonitorStatus,
  XTarget,
  XTargetCreate,
  XTargetUpdate,
  RustRconBinding,
  RustRconBindingCreate,
  RustRconBindingUpdate,
  RustRconGroupPolicyList,
  RustRconGroupPolicyMutation,
  RustRconUserPolicyList,
  RustRconUserPolicyMutation,
  RustPlayerOverviewItem,
  RustCheckInConfig,
  RustPlayerPointsUpdate,
  RustShopItem,
  RustShopItemCreate,
  RustShopItemListResponse,
  RustShopItemUpdate,
  RustRconCustomCommand,
  RustRconCustomCommandCreate,
  RustRconCustomCommandListResponse,
  RustRconCustomCommandUpdate,
  Settings,
  SettingsUpdate,
  SetupRequest,
  SetupStatus,
  SystemMonitorStatus,
  ConnectionsStatus,
  User,
} from './types'

const TOKEN_KEY = 'cyxcbot_access_token'
const API_BASE = '/api/v1'

export class ApiClientError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

/** 合并开发模式下 StrictMode 触发的并发相同 GET 请求 */
const inflightGetRequests = new Map<string, Promise<unknown>>()

function getInflightKey(method: string, path: string, auth: boolean): string | null {
  if (method !== 'GET') return null
  const token = auth ? getToken() ?? '' : ''
  return `${path}:${token}`
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const inflightKey = getInflightKey(method, path, auth)

  if (inflightKey) {
    const existing = inflightGetRequests.get(inflightKey)
    if (existing) {
      return existing as Promise<T>
    }
  }

  const execute = async (): Promise<T> => {
    const headers = new Headers(options.headers)
    if (!headers.has('Content-Type') && options.body) {
      headers.set('Content-Type', 'application/json')
    }

    if (auth) {
      const token = getToken()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
    }

    let response: Response
    try {
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      })
    } catch {
      throw new ApiClientError('后端服务暂不可用，数据暂时无法加载', 0)
    }

    if (response.status === 401 && auth) {
      clearToken()
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/setup')) {
        window.location.href = '/login'
      }
      throw new ApiClientError('未授权，请重新登录', 401)
    }

    if (!response.ok) {
      let message = `请求失败 (${response.status})`
      if (response.status === 502 || response.status === 503 || response.status === 504) {
        message = '后端服务暂不可用，数据暂时无法加载'
      } else {
        try {
          const data = await response.json()
          if (typeof data.detail === 'string') {
            message = data.detail
          } else if (Array.isArray(data.detail)) {
            message = data.detail.map((d: { msg?: string }) => d.msg ?? '').join('; ')
          }
        } catch {
          // ignore parse errors
        }
      }
      throw new ApiClientError(message, response.status)
    }

    if (response.status === 204) {
      return undefined as T
    }

    return response.json() as Promise<T>
  }

  if (!inflightKey) {
    return execute()
  }

  const promise = execute()
  inflightGetRequests.set(inflightKey, promise)
  try {
    return await promise
  } finally {
    inflightGetRequests.delete(inflightKey)
  }
}

// Auth & Setup
export const getSetupStatus = () =>
  request<SetupStatus>('/setup/status', {}, false)

export const postSetup = (data: SetupRequest) =>
  request<LoginResponse>('/setup', { method: 'POST', body: JSON.stringify(data) }, false)

export const postLogin = (data: LoginRequest) =>
  request<LoginResponse>('/auth/login', { method: 'POST', body: JSON.stringify(data) }, false)

export const getMe = () => request<User>('/auth/me')

// Settings
export const getSettings = () => request<Settings>('/settings')

export const patchSettings = (data: SettingsUpdate) =>
  request<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(data) })

export const testCookie = () =>
  request<CookieTestResult>('/settings/test-cookie', { method: 'POST' })

// Bilibili login
export const getBilibiliQrcode = () =>
  request<BilibiliQrcodeStart>('/bilibili/login/qrcode')

export async function pollBilibiliQrcodeLogin(
  qrcode: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<BilibiliQrcodeLoginResult> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}/bilibili/login/qrcode/poll`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ qrcode }),
    signal,
  }).catch(() => {
    throw new ApiClientError('后端服务暂不可用，数据暂时无法加载', 0)
  })

  if (response.status === 401) {
    clearToken()
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/setup')) {
      window.location.href = '/login'
    }
    throw new ApiClientError('未授权，请重新登录', 401)
  }

  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      message = '后端服务暂不可用，数据暂时无法加载'
    } else {
      try {
        const data = await response.json()
        if (typeof data.detail === 'string') {
          message = data.detail
        }
      } catch {
        // ignore parse errors
      }
    }
    throw new ApiClientError(message, response.status)
  }

  return response.json() as Promise<BilibiliQrcodeLoginResult>
}

export const logoutBilibili = () =>
  request<BilibiliLogoutResult>('/bilibili/logout', { method: 'POST' })

// Dynamic Targets
export const getDynamicTargets = () =>
  request<DynamicTarget[]>('/dynamic-targets')

export const createDynamicTarget = (data: DynamicTargetCreate) =>
  request<DynamicTarget>('/dynamic-targets', { method: 'POST', body: JSON.stringify(data) })

export const updateDynamicTarget = (id: number, data: DynamicTargetUpdate) =>
  request<DynamicTarget>(`/dynamic-targets/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const deleteDynamicTarget = (id: number) =>
  request<void>(`/dynamic-targets/${id}`, { method: 'DELETE' })

// Live Targets
export const getLiveTargets = () => request<LiveTarget[]>('/live-targets')

export const createLiveTarget = (data: LiveTargetCreate) =>
  request<LiveTarget>('/live-targets', { method: 'POST', body: JSON.stringify(data) })

export const updateLiveTarget = (id: number, data: LiveTargetUpdate) =>
  request<LiveTarget>(`/live-targets/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const deleteLiveTarget = (id: number) =>
  request<void>(`/live-targets/${id}`, { method: 'DELETE' })

// X Targets
export const getXTargets = () => request<XTarget[]>('/x-targets')

export const createXTarget = (data: XTargetCreate) =>
  request<XTarget>('/x-targets', { method: 'POST', body: JSON.stringify(data) })

export const updateXTarget = (id: number, data: XTargetUpdate) =>
  request<XTarget>(`/x-targets/${id}`, { method: 'PATCH', body: JSON.stringify(data) })

export const deleteXTarget = (id: number) =>
  request<void>(`/x-targets/${id}`, { method: 'DELETE' })

// Rust RCON bindings
export const getRustRconBindings = () =>
  request<RustRconBinding[]>('/rust-rcon/bindings')

export const createRustRconBinding = (data: RustRconBindingCreate) =>
  request<RustRconBinding>('/rust-rcon/bindings', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateRustRconBinding = (id: number, data: RustRconBindingUpdate) =>
  request<RustRconBinding>(`/rust-rcon/bindings/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteRustRconBinding = (id: number) =>
  request<void>(`/rust-rcon/bindings/${id}`, { method: 'DELETE' })

export const getRustRconGroupPolicies = () =>
  request<RustRconGroupPolicyList>('/rust-rcon/policies/groups')

export const updateRustRconGroupPolicy = (groupId: string, enabled: boolean) =>
  request<RustRconGroupPolicyMutation>(
    `/rust-rcon/policies/groups/${encodeURIComponent(groupId)}`,
    { method: 'PUT', body: JSON.stringify({ enabled }) },
  )

export const resetRustRconGroupPolicy = (groupId: string) =>
  request<RustRconGroupPolicyMutation>(
    `/rust-rcon/policies/groups/${encodeURIComponent(groupId)}`,
    { method: 'DELETE' },
  )

export const getRustRconUserPolicies = () =>
  request<RustRconUserPolicyList>('/rust-rcon/policies/users')

export const updateRustRconUserPolicy = (
  userId: string,
  payload: { enabled: boolean; name?: string | null },
) =>
  request<RustRconUserPolicyMutation>(
    `/rust-rcon/policies/users/${encodeURIComponent(userId)}`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )

export const resetRustRconUserPolicy = (userId: string) =>
  request<RustRconUserPolicyMutation>(
    `/rust-rcon/policies/users/${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  )

// Rust player points / Steam bindings
export const getRustPlayerOverview = () =>
  request<{ items: RustPlayerOverviewItem[] }>('/rust-players/overview')

export const updateRustPlayerPoints = (data: RustPlayerPointsUpdate) =>
  request<RustPlayerPointsUpdate>('/rust-players/points', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteRustSteamBinding = (userId: string) =>
  request<void>(`/rust-players/steam-bindings/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  })

export const getRustCheckInConfig = () =>
  request<RustCheckInConfig>('/rust-players/checkin-config')

export const updateRustCheckInConfig = (data: RustCheckInConfig) =>
  request<RustCheckInConfig>('/rust-players/checkin-config', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

// Rust shop items
export const getRustShopItems = () =>
  request<RustShopItemListResponse>('/rust-shop/items')

export const createRustShopItem = (data: RustShopItemCreate) =>
  request<RustShopItem>('/rust-shop/items', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateRustShopItem = (id: number, data: RustShopItemUpdate) =>
  request<RustShopItem>(`/rust-shop/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteRustShopItem = (id: number) =>
  request<void>(`/rust-shop/items/${id}`, { method: 'DELETE' })

// Rust RCON custom commands
export const getRustRconCustomCommands = () =>
  request<RustRconCustomCommandListResponse>('/rust-rcon/custom-commands')

export const createRustRconCustomCommand = (data: RustRconCustomCommandCreate) =>
  request<RustRconCustomCommand>('/rust-rcon/custom-commands', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateRustRconCustomCommand = (
  id: number,
  data: RustRconCustomCommandUpdate,
) =>
  request<RustRconCustomCommand>(`/rust-rcon/custom-commands/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

export const deleteRustRconCustomCommand = (id: number) =>
  request<void>(`/rust-rcon/custom-commands/${id}`, { method: 'DELETE' })

// Groups
export const getGroups = async (): Promise<Group[]> => {
  const data = await request<{ groups: Group[] }>('/groups')
  return data.groups ?? []
}

export const getMessagePolicy = () => request<GroupMessagePolicy>('/groups/message-policy')

export const updateMessagePolicy = (payload: {
  restrict: boolean
  enabled_group_ids: string[]
}) =>
  request<GroupMessagePolicy>('/groups/message-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getGroupStatusPolicy = () => request<GroupStatusPolicy>('/groups/status-policy')

export const updateGroupStatusPolicy = (payload: {
  restrict: boolean
  enabled_group_ids: string[]
  display?: StatusCheckDisplayOptions
}) =>
  request<GroupStatusPolicy>('/groups/status-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getGroupSpecialTitlePolicy = () =>
  request<GroupSpecialTitlePolicy>('/groups/special-title-policy')

export const updateGroupSpecialTitlePolicy = (payload: {
  restrict: boolean
  enabled_group_ids: string[]
  daily_limit?: number
}) =>
  request<GroupSpecialTitlePolicy>('/groups/special-title-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getPrivateMessagePolicy = () =>
  request<PrivateMessagePolicy>('/private/message-policy')

export const getFriends = () =>
  request<{ friends: Friend[] }>('/private/friends').then((data) => data.friends ?? [])

export const updatePrivateMessagePolicy = (payload: {
  restrict: boolean
  enabled_user_ids: string[]
}) =>
  request<PrivateMessagePolicy>('/private/message-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getPrivateStatusPolicy = () => request<PrivateStatusPolicy>('/private/status-policy')

export const updatePrivateStatusPolicy = (payload: {
  restrict: boolean
  enabled_user_ids: string[]
  display?: StatusCheckDisplayOptions
}) =>
  request<PrivateStatusPolicy>('/private/status-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getLinkParserGroupPolicies = () =>
  request<LinkParserGroupPolicyList>('/link-parser/policies/groups')

export const updateLinkParserGroupPolicy = (
  groupId: string,
  payload: {
    video_enabled: boolean
    live_enabled: boolean
    dynamic_enabled: boolean
    send_video_enabled: boolean
  },
) =>
  request<LinkParserGroupPolicyMutation>(`/link-parser/policies/groups/${encodeURIComponent(groupId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const resetLinkParserGroupPolicy = (groupId: string) =>
  request<LinkParserGroupPolicyMutation>(
    `/link-parser/policies/groups/${encodeURIComponent(groupId)}`,
    { method: 'DELETE' },
  )

export const getLinkParserUserPolicies = () =>
  request<LinkParserUserPolicyList>('/link-parser/policies/users')

export const createLinkParserUserPolicy = (payload: LinkParserUserPolicyInput) =>
  request<LinkParserUserPolicyMutation>('/link-parser/policies/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const updateLinkParserUserPolicy = (
  userId: string,
  payload: Omit<LinkParserUserPolicyInput, 'user_id'>,
) =>
  request<LinkParserUserPolicyMutation>(
    `/link-parser/policies/users/${encodeURIComponent(userId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )

export const resetLinkParserUserPolicy = (userId: string) =>
  request<LinkParserUserPolicyMutation>(
    `/link-parser/policies/users/${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  )

export const getDouyinLinkParserGroupPolicies = () =>
  request<DouyinLinkParserGroupPolicyList>('/douyin-link-parser/policies/groups')

export const updateDouyinLinkParserGroupPolicy = (
  groupId: string,
  payload: { enabled: boolean },
) =>
  request<DouyinLinkParserGroupPolicyMutation>(
    `/douyin-link-parser/policies/groups/${encodeURIComponent(groupId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )

export const resetDouyinLinkParserGroupPolicy = (groupId: string) =>
  request<DouyinLinkParserGroupPolicyMutation>(
    `/douyin-link-parser/policies/groups/${encodeURIComponent(groupId)}`,
    { method: 'DELETE' },
  )

export const getDouyinLinkParserUserPolicies = () =>
  request<DouyinLinkParserUserPolicyList>('/douyin-link-parser/policies/users')

export const updateDouyinLinkParserUserPolicy = (
  userId: string,
  payload: { enabled: boolean; name?: string | null },
) =>
  request<DouyinLinkParserUserPolicyMutation>(
    `/douyin-link-parser/policies/users/${encodeURIComponent(userId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )

export const resetDouyinLinkParserUserPolicy = (userId: string) =>
  request<DouyinLinkParserUserPolicyMutation>(
    `/douyin-link-parser/policies/users/${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  )

export const saveDouyinCookie = (cookie: string) =>
  request<DouyinCookieStatus>('/douyin-link-parser/cookie', {
    method: 'PUT',
    body: JSON.stringify({ cookie }),
  })

export const clearDouyinCookie = () =>
  request<{ success: boolean; message: string }>('/douyin-link-parser/cookie', {
    method: 'DELETE',
  })

export const getDouyinQrcode = () =>
  request<DouyinQrcodeStart>('/douyin/login/qrcode')

export const refreshDouyinQrcode = (sessionId: string) =>
  request<DouyinQrcodeStart>('/douyin/login/qrcode/refresh', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })

export async function pollDouyinQrcodeLogin(
  sessionId: string,
  signal?: AbortSignal,
): Promise<DouyinQrcodeLoginResult> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE}/douyin/login/qrcode/poll`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId }),
    signal,
  }).catch(() => {
    throw new ApiClientError('后端服务暂不可用，数据暂时无法加载', 0)
  })

  if (response.status === 401) {
    clearToken()
    if (
      !window.location.pathname.startsWith('/login') &&
      !window.location.pathname.startsWith('/setup')
    ) {
      window.location.href = '/login'
    }
    throw new ApiClientError('未授权，请重新登录', 401)
  }

  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    if (response.status === 502 || response.status === 503 || response.status === 504) {
      message = '后端服务暂不可用，数据暂时无法加载'
    } else {
      try {
        const data = await response.json()
        if (typeof data.detail === 'string') {
          message = data.detail
        }
      } catch {
        // ignore parse errors
      }
    }
    throw new ApiClientError(message, response.status)
  }

  return response.json() as Promise<DouyinQrcodeLoginResult>
}

export const cancelDouyinQrcodeLogin = (sessionId: string) =>
  request<{ success: boolean; message: string }>('/douyin/login/qrcode/cancel', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })

export const logoutDouyin = () =>
  request<DouyinLogoutResult>('/douyin/logout', { method: 'POST' })

// X account
export const getXBearerStatus = () => request<XBearerStatus>('/x/bearer')

export const saveXBearer = (bearer: string) =>
  request<XBearerStatus>('/x/bearer', {
    method: 'PUT',
    body: JSON.stringify({ bearer }),
  })

export const clearXBearer = () =>
  request<XBearerStatus>('/x/bearer', { method: 'DELETE' })

export const testXBearer = (username = 'X') =>
  request<XBearerTestResult>('/x/bearer/test', {
    method: 'POST',
    body: JSON.stringify({ username }),
  })

// Monitors
export const getMonitorStatus = () => request<MonitorStatus>('/monitors/status')

export const getDynamicMonitorStatus = () =>
  request<DynamicMonitorStatus>('/monitors/dynamic')

export const getLiveMonitorStatus = () => request<LiveMonitorStatus>('/monitors/live')

export const getXMonitorStatus = () => request<XMonitorStatus>('/monitors/x')

export const getSystemMonitorStatus = () =>
  request<SystemMonitorStatus>('/monitors/system')

export const getConnectionsStatus = () =>
  request<ConnectionsStatus>('/connections/status')

export const getAbout = () => request<AboutInfo>('/about')

export const triggerDynamicCheck = () =>
  request<MonitorActionResult>('/monitors/dynamic/check', { method: 'POST' })

export const triggerLiveCheck = () =>
  request<MonitorActionResult>('/monitors/live/check', { method: 'POST' })

export const triggerXCheck = () =>
  request<MonitorActionResult>('/monitors/x/check', { method: 'POST' })

export const getRecentLogs = (params: { limit?: number; min_level?: string } = {}) =>
  request<RecentLogsResponse>(
    `/logs/recent${buildQuery(params as Record<string, string | number | undefined>)}`,
  )

const LOGS_WS_AUTH_PROTOCOL = 'access_token'

export function buildLogsWebSocketUrl(minLevel = 'INFO'): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const params = new URLSearchParams({ min_level: minLevel })
  return `${protocol}//${window.location.host}/api/v1/ws/logs?${params}`
}

export function createLogsWebSocket(minLevel = 'INFO'): WebSocket {
  const token = getToken()
  if (!token) {
    throw new Error('Not authenticated')
  }
  return new WebSocket(buildLogsWebSocketUrl(minLevel), [LOGS_WS_AUTH_PROTOCOL, token])
}
