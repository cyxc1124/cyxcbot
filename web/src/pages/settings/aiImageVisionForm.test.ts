import { describe, expect, it } from 'vitest'
import type { AiImageVisionProvider } from '../../api/types'
import {
  balanceProviderName,
  describeBalance,
  describeTest,
  draftFromProvider,
  isDirty,
  needsKeyReentry,
  newDraft,
  probePayload,
  providerChanges,
  providerInput,
  providerSummary,
  sortModels,
  switchApiType,
  validateDraft,
} from './aiImageVisionForm'

const saved: AiImageVisionProvider = {
  id: 'p1', name: 'GPT', api_type: 'openai', base_url: '', model: 'gpt-4o',
  enabled: true, proxy_id: '', api_key_configured: true,
}

describe('single vision provider form', () => {
  it('only reports real field edits as unsaved; enabling is saved separately', () => {
    const draft = draftFromProvider(saved)
    expect(isDirty(draft, saved)).toBe(false)
    expect(isDirty({ ...draft, enabled: false }, saved)).toBe(false)
    expect(isDirty({ ...draft, name: ' GPT ' }, saved)).toBe(false)
    expect(isDirty({ ...draft, model: 'gpt-4o-mini' }, saved)).toBe(true)
    expect(isDirty({ ...draft, proxy_id: 'px' }, saved)).toBe(true)
    expect(isDirty({ ...draft, api_key: 'sk-new' }, saved)).toBe(true)
    expect(isDirty({ ...draft, clear_key: true }, saved)).toBe(true)
    expect(isDirty(newDraft())).toBe(true)
  })

  it('keeps stored keys unless a new key is typed or clearing is requested', () => {
    const draft = draftFromProvider(saved)
    expect(providerChanges(draft)).toEqual({
      name: 'GPT', api_type: 'openai', base_url: '', model: 'gpt-4o', proxy_id: '',
    })
    expect(providerChanges({ ...draft, api_key: '  sk-test-only  ' }).api_key).toBe('sk-test-only')
    expect(providerChanges({ ...draft, clear_key: true })).toHaveProperty('api_key', '')
    const added = { ...newDraft('anthropic'), name: ' Claude ', model: ' claude-test ', base_url: ' https://gateway.test ', enabled: false }
    expect(providerInput(added)).toEqual({
      name: 'Claude', api_type: 'anthropic', base_url: 'https://gateway.test', model: 'claude-test', enabled: false, proxy_id: '',
    })
  })

  it('requires the key again when the stored key would go to another endpoint', () => {
    const draft = draftFromProvider(saved)
    expect(needsKeyReentry({ ...draft, base_url: 'https://api.openai.com/v1/' }, saved)).toBe(false)
    expect(needsKeyReentry({ ...draft, base_url: 'https://other.test/v1' }, saved)).toBe(true)
    expect(needsKeyReentry(switchApiType(draft, 'anthropic'), saved)).toBe(true)
    expect(needsKeyReentry({ ...draft, base_url: 'https://other.test/v1', api_key: 'sk-new' }, saved)).toBe(false)
    expect(needsKeyReentry({ ...newDraft(), base_url: 'https://other.test/v1' })).toBe(false)
    expect(validateDraft({ ...draft, base_url: 'https://other.test/v1' }, saved)).toContain('重新填写 API Key')
  })

  it('validates name and model before saving', () => {
    expect(validateDraft({ ...newDraft(), name: 'A', model: 'm' })).toBeNull()
    expect(validateDraft({ ...newDraft(), name: ' ', model: 'm' })).toBe('请填写名称')
    expect(validateDraft({ ...newDraft(), name: 'A' })).toContain('模型')
    const keys = Array.from({ length: 20 }, () => newDraft().key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('resets an official base URL when switching API types', () => {
    const draft = { ...newDraft(), base_url: 'https://api.openai.com/v1' }
    expect(switchApiType(draft, 'anthropic').base_url).toBe('')
    expect(switchApiType({ ...draft, base_url: 'https://gateway.test/v1' }, 'anthropic').base_url).toBe('https://gateway.test/v1')
  })

  it('summarizes a collapsed provider in one line', () => {
    expect(providerSummary(saved, true)).toBe('OpenAI 兼容 · gpt-4o · 官方地址 · 已配置密钥 · 直接连接')
    expect(providerSummary(saved, true, '香港')).toBe('OpenAI 兼容 · gpt-4o · 官方地址 · 已配置密钥 · 代理「香港」')
    expect(providerSummary({ api_type: 'anthropic', base_url: 'https://api.anthropic.com/', model: '' }, false))
      .toBe('Anthropic · 未填写模型 · 官方地址 · 未配置密钥 · 直接连接')
    expect(providerSummary({ api_type: 'openai', base_url: 'http://127.0.0.1:11434/v1', model: 'llava' }, false))
      .toBe('OpenAI 兼容 · llava · 127.0.0.1:11434 · 未配置密钥 · 直接连接')
  })
})

describe('provider probes', () => {
  it('probes unsaved values with the same key rules as saving', () => {
    const draft = draftFromProvider(saved)
    expect(probePayload({ ...draft, model: ' gpt-4o-mini ', proxy_id: 'px' })).toEqual({
      id: 'p1', api_type: 'openai', base_url: '', model: 'gpt-4o-mini', proxy_id: 'px',
    })
    expect(probePayload({ ...draft, api_key: ' sk-typed ' }).api_key).toBe('sk-typed')
    expect(probePayload({ ...draft, clear_key: true })).toHaveProperty('api_key', '')
    expect(probePayload(newDraft())).not.toHaveProperty('id')
  })

  it('offers balance only for official hosts with a documented key-based API', () => {
    const draft = newDraft()
    expect(balanceProviderName(draft)).toBeNull()
    expect(balanceProviderName({ ...draft, base_url: 'https://api.deepseek.com' })).toBe('DeepSeek')
    expect(balanceProviderName({ ...newDraft('anthropic'), base_url: 'https://API.DeepSeek.com/anthropic' })).toBe('DeepSeek')
    expect(balanceProviderName({ ...draft, base_url: 'https://api.moonshot.ai/v1' })).toBe('Kimi')
    expect(balanceProviderName({ ...draft, base_url: 'https://deepseek.gateway.test/v1' })).toBeNull()
    expect(balanceProviderName({ ...draft, base_url: 'not a url' })).toBeNull()
  })

  it('lists image-capable models first', () => {
    expect(sortModels([
      { id: 'b-text', name: '', vision: false },
      { id: 'z-unknown', name: '', vision: null },
      { id: 'a-unknown', name: '', vision: null },
      { id: 'c-vision', name: '', vision: true },
    ]).map((model) => model.id)).toEqual(['c-vision', 'a-unknown', 'z-unknown', 'b-text'])
  })

  it('describes test results with latency, verdict and usage', () => {
    expect(describeTest({
      success: true, message: 'ok', latency_ms: 1640, verdict: 'uncertain', confidence: 30,
      reason: '合成渐变', input_tokens: 812, output_tokens: 41,
    })).toEqual([
      '响应正常，用时 1.6 秒；测试图判断：无法判断（置信度 30%）',
      '理由：合成渐变',
      '本次用量：输入 812 tokens，输出 41 tokens',
    ])
    expect(describeTest({
      success: false, message: 'API Key 无效。（Authentication Fails）', latency_ms: 300, verdict: null,
      confidence: null, reason: '', input_tokens: null, output_tokens: null,
    })).toEqual(['测试失败（用时 0.3 秒）：API Key 无效。（Authentication Fails）'])
  })

  it('describes balances per currency and warns when calls are blocked', () => {
    expect(describeBalance({
      success: true, message: '', provider: 'DeepSeek', available: false,
      balances: [{ currency: 'CNY', total: '0.00', items: [{ label: '赠送余额', amount: '0.00' }] }],
    })).toEqual(['DeepSeek 余额：CNY 0.00（赠送余额 0.00）', '余额不足，当前无法调用该接口'])
    expect(describeBalance({ success: false, message: '不支持', provider: '', available: null, balances: [] }))
      .toEqual(['不支持'])
  })
})
