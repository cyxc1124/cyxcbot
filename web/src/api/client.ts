import type {
  AboutInfo,
  AuditLog,
  AuditLogQuery,
  BilibiliLogoutResult,
  BilibiliQrcodeLoginResult,
  BilibiliQrcodeStart,
  CookieTestResult,
  DynamicMonitorStatus,
  DynamicTarget,
  DynamicTargetCreate,
  DynamicTargetUpdate,
  EventQuery,
  Group,
  GroupMessagePolicy,
  LinkParserGroupPolicyList,
  LinkParserGroupPolicyMutation,
  LinkParserUserPolicyInput,
  LinkParserUserPolicyList,
  LinkParserUserPolicyMutation,
  PrivateMessagePolicy,
  LiveMonitorStatus,
  LiveTarget,
  LiveTargetCreate,
  LiveTargetUpdate,
  LoginRequest,
  LoginResponse,
  MonitorActionResult,
  MonitorStatus,
  PaginatedResponse,
  Settings,
  SettingsUpdate,
  SetupRequest,
  SetupStatus,
  SystemEvent,
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

export const getPrivateMessagePolicy = () =>
  request<PrivateMessagePolicy>('/private/message-policy')

export const updatePrivateMessagePolicy = (payload: {
  restrict: boolean
  enabled_user_ids: string[]
}) =>
  request<PrivateMessagePolicy>('/private/message-policy', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const getLinkParserGroupPolicies = () =>
  request<LinkParserGroupPolicyList>('/link-parser/policies/groups')

export const updateLinkParserGroupPolicy = (
  groupId: string,
  payload: { enabled: boolean; video_enabled: boolean; live_enabled: boolean },
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
  request<LinkParserUserPolicyList>('/link-parser/policies/users', {
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

// Monitors
export const getMonitorStatus = () => request<MonitorStatus>('/monitors/status')

export const getDynamicMonitorStatus = () =>
  request<DynamicMonitorStatus>('/monitors/dynamic')

export const getLiveMonitorStatus = () => request<LiveMonitorStatus>('/monitors/live')

export const getSystemMonitorStatus = () =>
  request<SystemMonitorStatus>('/monitors/system')

export const getConnectionsStatus = () =>
  request<ConnectionsStatus>('/connections/status')

export const getAbout = () => request<AboutInfo>('/about')

export const triggerDynamicCheck = () =>
  request<MonitorActionResult>('/monitors/dynamic/check', { method: 'POST' })

export const triggerLiveCheck = () =>
  request<MonitorActionResult>('/monitors/live/check', { method: 'POST' })

// Audit & Events
export const getAuditLogs = (query: AuditLogQuery = {}) =>
  request<PaginatedResponse<AuditLog>>(
    `/audit-logs${buildQuery(query as Record<string, string | number | undefined>)}`,
  )

export const getEvents = (query: EventQuery = {}) =>
  request<PaginatedResponse<SystemEvent>>(
    `/events${buildQuery(query as Record<string, string | number | undefined>)}`,
  )
