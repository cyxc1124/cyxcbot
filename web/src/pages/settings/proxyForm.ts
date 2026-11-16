import type {
  ProxyEntry,
  ProxyInput,
  ProxyScheme,
  ProxyTestRequest,
  ProxyTestResult,
  Settings,
} from '../../api/types'

export const PROXIES_PATH = '/system/proxies'

export const PROXY_SCHEME_LABELS: Record<ProxyScheme, string> = {
  http: 'HTTP',
  https: 'HTTPS',
  socks5: 'SOCKS5',
}

export type ProxyDraft = {
  /** React key；已保存的代理沿用服务端 id */
  key: string
  id?: string
  name: string
  scheme: ProxyScheme
  host: string
  port: number
  username: string
  password_configured: boolean
  /** 新填写的密码；留空表示保留 */
  password: string
  clear_password: boolean
}

let nextDraftKey = 0

export function proxyDraftFrom(proxy: ProxyEntry): ProxyDraft {
  return {
    key: proxy.id,
    id: proxy.id,
    name: proxy.name,
    scheme: proxy.scheme,
    host: proxy.host,
    port: proxy.port,
    username: proxy.username,
    password_configured: proxy.password_configured,
    password: '',
    clear_password: false,
  }
}

export function newProxyDraft(): ProxyDraft {
  nextDraftKey += 1
  return {
    key: `new-proxy-${nextDraftKey}`,
    name: '',
    scheme: 'http',
    host: '',
    port: 7890,
    username: '',
    password_configured: false,
    password: '',
    clear_password: false,
  }
}

/** 已存密码不会回传，主机变化后必须重新填写。 */
export function needsPasswordReentry(draft: ProxyDraft, proxy?: ProxyEntry): boolean {
  if (!proxy?.password_configured || draft.clear_password || draft.password) return false
  return draft.host.trim().toLowerCase() !== proxy.host.toLowerCase()
}

export function isProxyDirty(draft: ProxyDraft, proxy?: ProxyEntry): boolean {
  if (!proxy) return true
  return draft.name.trim() !== proxy.name
    || draft.scheme !== proxy.scheme
    || draft.host.trim() !== proxy.host
    || draft.port !== proxy.port
    || draft.username.trim() !== proxy.username
    || draft.clear_password
    || draft.password !== ''
}

export function validateProxyDraft(draft: ProxyDraft, proxy?: ProxyEntry): string | null {
  const name = draft.name.trim()
  if (!name) return '请填写代理名称'
  if (!draft.host.trim()) return `请填写「${name}」的主机`
  if (!Number.isInteger(draft.port) || draft.port < 1 || draft.port > 65535) return '代理端口须在 1–65535 之间'
  if (needsPasswordReentry(draft, proxy)) return `修改「${name}」的主机后，需要重新填写密码`
  return null
}

function passwordPatch(draft: ProxyDraft): { password?: string } {
  return draft.password ? { password: draft.password } : draft.clear_password ? { password: '' } : {}
}

export function proxyInput(draft: ProxyDraft): ProxyInput {
  return {
    name: draft.name.trim(),
    scheme: draft.scheme,
    host: draft.host.trim(),
    port: draft.port,
    username: draft.username.trim(),
    ...passwordPatch(draft),
  }
}

export function proxyTestPayload(draft: ProxyDraft): ProxyTestRequest {
  return {
    ...(draft.id ? { id: draft.id } : {}),
    scheme: draft.scheme,
    host: draft.host.trim(),
    port: draft.port,
    username: draft.username.trim(),
    ...passwordPatch(draft),
  }
}

export function proxyAddress(proxy: Pick<ProxyEntry, 'scheme' | 'host' | 'port'>): string {
  return `${PROXY_SCHEME_LABELS[proxy.scheme]} ${proxy.host}:${proxy.port}`
}

export function proxySummary(proxy: Pick<ProxyEntry, 'scheme' | 'host' | 'port' | 'username' | 'password_configured'>): string {
  const host = proxy.host.trim() || '未填写主机'
  const auth = proxy.username || proxy.password_configured ? '需要认证' : '无认证'
  return `${PROXY_SCHEME_LABELS[proxy.scheme]} · ${host}:${proxy.port} · ${auth}`
}

export type ProxyUsage = {
  label: string
  proxyId: string
  /** 修改该功能所用代理的页面 */
  to: string
}

/** 所有可以选用代理的功能，以及各自当前选择的代理 id。 */
export function proxyUsages(settings: Settings | null): ProxyUsage[] {
  if (!settings) return []
  return [
    { label: 'X（推文订阅、链接解析）', proxyId: settings.x_proxy_id ?? '', to: '/x/account' },
    { label: 'AI 图片检测 · OpenAI 来源检测', proxyId: settings.ai_image_openai_proxy_id ?? '', to: '/ai-image/sources' },
    ...(settings.ai_image_vision_providers ?? []).map((provider) => ({
      label: `AI 图片检测 · 视觉模型「${provider.name}」`,
      proxyId: provider.proxy_id,
      to: '/ai-image/vision',
    })),
  ]
}

export function describeProxyTest(result: ProxyTestResult): string[] {
  return [
    result.message,
    ...result.targets.map((target) => target.reachable
      ? `${target.name}：${target.message}，${target.latency_ms ?? '—'} ms`
      : `${target.name}：${target.message}`),
  ]
}
