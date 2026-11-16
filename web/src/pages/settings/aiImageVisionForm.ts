import type {
  AiImageVisionProvider,
  AiImageVisionProviderInput,
  VisionApiType,
  VisionBalanceResult,
  VisionModelInfo,
  VisionProbeRequest,
  VisionTestResult,
} from '../../api/types'

/** 需与 shared/config/ai_image.py 保持一致 */
export const DEFAULT_VISION_BASE_URLS: Record<VisionApiType, string> = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com',
}

export const API_TYPE_LABELS: Record<VisionApiType, string> = {
  openai: 'OpenAI 兼容',
  anthropic: 'Anthropic',
}

export type VisionProviderDraft = {
  /** React key；已保存的供应商沿用服务端 id */
  key: string
  id?: string
  name: string
  api_type: VisionApiType
  base_url: string
  model: string
  /** 仅新建时使用；已保存的供应商通过卡片标题栏的开关立即启停 */
  enabled: boolean
  /** 选用的代理 id，空字符串表示直接连接 */
  proxy_id: string
  api_key_configured: boolean
  /** 新填写的密钥；留空表示保留 */
  api_key: string
  clear_key: boolean
}

let nextDraftKey = 0

export function draftFromProvider(provider: AiImageVisionProvider): VisionProviderDraft {
  return {
    key: provider.id,
    id: provider.id,
    name: provider.name,
    api_type: provider.api_type,
    base_url: provider.base_url,
    model: provider.model,
    enabled: provider.enabled,
    proxy_id: provider.proxy_id,
    api_key_configured: provider.api_key_configured,
    api_key: '',
    clear_key: false,
  }
}

export function newDraft(apiType: VisionApiType = 'openai'): VisionProviderDraft {
  nextDraftKey += 1
  return {
    key: `new-${nextDraftKey}`,
    name: '',
    api_type: apiType,
    base_url: '',
    model: '',
    enabled: true,
    proxy_id: '',
    api_key_configured: false,
    api_key: '',
    clear_key: false,
  }
}

/** 切换接口类型时，若地址仍是旧类型的官方地址则改回留空，避免把请求发错地方。 */
export function switchApiType(draft: VisionProviderDraft, apiType: VisionApiType): VisionProviderDraft {
  const baseUrl = draft.base_url.trim().replace(/\/+$/, '') === DEFAULT_VISION_BASE_URLS[draft.api_type] ? '' : draft.base_url
  return { ...draft, api_type: apiType, base_url: baseUrl }
}

function endpoint(apiType: VisionApiType, baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '') || DEFAULT_VISION_BASE_URLS[apiType]
}

/** 已存密钥不会回传，接口类型或地址变化后必须重新填写。 */
export function needsKeyReentry(draft: VisionProviderDraft, provider?: AiImageVisionProvider): boolean {
  if (!provider?.api_key_configured || draft.clear_key || draft.api_key.trim()) return false
  return provider.api_type !== draft.api_type
    || endpoint(provider.api_type, provider.base_url) !== endpoint(draft.api_type, draft.base_url)
}

/** 与已保存的值比较；启停由标题栏开关立即保存，不算未保存修改。 */
export function isDirty(draft: VisionProviderDraft, provider?: AiImageVisionProvider): boolean {
  if (!provider) return true
  return draft.name.trim() !== provider.name
    || draft.api_type !== provider.api_type
    || draft.base_url.trim() !== provider.base_url
    || draft.model.trim() !== provider.model
    || draft.proxy_id !== provider.proxy_id
    || draft.clear_key
    || draft.api_key.trim() !== ''
}

export function validateDraft(draft: VisionProviderDraft, provider?: AiImageVisionProvider): string | null {
  const name = draft.name.trim()
  if (!name) return '请填写名称'
  if (!draft.model.trim()) return `请填写「${name}」的模型`
  if (needsKeyReentry(draft, provider)) return `修改「${name}」的接口类型或地址后，需要重新填写 API Key`
  return null
}

function keyPatch(draft: VisionProviderDraft): { api_key?: string } {
  const apiKey = draft.api_key.trim()
  return apiKey ? { api_key: apiKey } : draft.clear_key ? { api_key: '' } : {}
}

/** 编辑已保存的供应商：提交表单字段，不含启停状态。 */
export function providerChanges(draft: VisionProviderDraft): Partial<AiImageVisionProviderInput> {
  return {
    name: draft.name.trim(),
    api_type: draft.api_type,
    base_url: draft.base_url.trim(),
    model: draft.model.trim(),
    proxy_id: draft.proxy_id,
    ...keyPatch(draft),
  }
}

export function providerInput(draft: VisionProviderDraft): AiImageVisionProviderInput {
  return {
    name: draft.name.trim(),
    api_type: draft.api_type,
    base_url: draft.base_url.trim(),
    model: draft.model.trim(),
    enabled: draft.enabled,
    proxy_id: draft.proxy_id,
    ...keyPatch(draft),
  }
}

/** 收起时显示的一行摘要；proxyName 为空表示直接连接。 */
export function providerSummary(
  values: { api_type: VisionApiType; base_url: string; model: string },
  keyConfigured: boolean,
  proxyName = '',
): string {
  const address = endpoint(values.api_type, values.base_url)
  let host = '官方地址'
  if (address !== DEFAULT_VISION_BASE_URLS[values.api_type]) {
    try {
      host = new URL(address).host
    } catch {
      host = address
    }
  }
  return [
    API_TYPE_LABELS[values.api_type],
    values.model.trim() || '未填写模型',
    host,
    keyConfigured ? '已配置密钥' : '未配置密钥',
    proxyName ? `代理「${proxyName}」` : '直接连接',
  ].join(' · ')
}

/** 获取模型 / 测试 / 余额按当前表单值请求，不必先保存。 */
export function probePayload(draft: VisionProviderDraft): VisionProbeRequest {
  return {
    ...(draft.id ? { id: draft.id } : {}),
    api_type: draft.api_type,
    base_url: draft.base_url.trim(),
    model: draft.model.trim(),
    proxy_id: draft.proxy_id,
    ...keyPatch(draft),
  }
}

/** 需与 utils/vision_api/balance.py 的 _BALANCE_APIS 保持一致 */
const BALANCE_PROVIDERS: Record<string, string> = {
  'api.deepseek.com': 'DeepSeek',
  'api.moonshot.cn': 'Kimi',
  'api.moonshot.ai': 'Kimi',
}

export function balanceProviderName(draft: VisionProviderDraft): string | null {
  try {
    return BALANCE_PROVIDERS[new URL(endpoint(draft.api_type, draft.base_url)).hostname.toLowerCase()] ?? null
  } catch {
    return null
  }
}

/** 声明支持图片的模型排在前面，其次是未声明的，最后是声明不支持的。 */
export function sortModels(models: VisionModelInfo[]): VisionModelInfo[] {
  const rank = (model: VisionModelInfo) => (model.vision === true ? 0 : model.vision === null ? 1 : 2)
  return [...models].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id))
}

const VERDICT_LABELS = { ai: '倾向 AI 生成', not_ai: '倾向非 AI 生成', uncertain: '无法判断' } as const

function seconds(ms: number | null): string {
  return ms === null ? '' : `${(ms / 1000).toFixed(1)} 秒`
}

export function describeTest(result: VisionTestResult): string[] {
  if (!result.success) {
    return [`测试失败${result.latency_ms === null ? '' : `（用时 ${seconds(result.latency_ms)}）`}：${result.message}`]
  }
  const verdict = result.verdict ? VERDICT_LABELS[result.verdict] : '—'
  const confidence = result.confidence === null ? '' : `（置信度 ${result.confidence}%）`
  const lines = [`响应正常，用时 ${seconds(result.latency_ms)}；测试图判断：${verdict}${confidence}`]
  if (result.reason) lines.push(`理由：${result.reason}`)
  if (result.input_tokens !== null || result.output_tokens !== null) {
    lines.push(`本次用量：输入 ${result.input_tokens ?? '—'} tokens，输出 ${result.output_tokens ?? '—'} tokens`)
  }
  return lines
}

export function describeBalance(result: VisionBalanceResult): string[] {
  if (!result.success) return [result.message]
  if (result.balances.length === 0) return [`${result.provider} 未返回余额明细`]
  const lines = result.balances.map((balance) => {
    const items = balance.items.map((item) => `${item.label} ${item.amount}`).join('，')
    return `${result.provider} 余额：${balance.currency} ${balance.total}${items ? `（${items}）` : ''}`
  })
  if (result.available === false) lines.push('余额不足，当前无法调用该接口')
  return lines
}
