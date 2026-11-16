import { describe, expect, it } from 'vitest'
import type { ProxyEntry, Settings } from '../../api/types'
import {
  describeProxyTest,
  isProxyDirty,
  needsPasswordReentry,
  newProxyDraft,
  proxyAddress,
  proxyDraftFrom,
  proxyInput,
  proxySummary,
  proxyTestPayload,
  proxyUsages,
  validateProxyDraft,
} from './proxyForm'

const saved: ProxyEntry = {
  id: 'p1', name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: 'user', password_configured: true,
}

describe('proxy drafts', () => {
  it('treats real edits as unsaved and keeps the stored password unless replaced or cleared', () => {
    const draft = proxyDraftFrom(saved)
    expect(isProxyDirty(draft, saved)).toBe(false)
    expect(isProxyDirty({ ...draft, port: 1081 }, saved)).toBe(true)
    expect(isProxyDirty({ ...draft, password: 'new' }, saved)).toBe(true)
    expect(isProxyDirty(newProxyDraft())).toBe(true)
    expect(proxyInput({ ...draft, name: ' 香港 ', host: ' hk.proxy.test ' })).toEqual({
      name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: 'user',
    })
    expect(proxyInput({ ...draft, password: ' p@ss ' }).password).toBe(' p@ss ')
    expect(proxyInput({ ...draft, clear_password: true })).toHaveProperty('password', '')
    expect(proxyTestPayload(draft)).toEqual({ id: 'p1', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: 'user' })
    expect(proxyTestPayload(newProxyDraft())).not.toHaveProperty('id')
  })

  it('asks for the password again when the host changes', () => {
    const draft = proxyDraftFrom(saved)
    expect(needsPasswordReentry({ ...draft, host: 'HK.proxy.test', port: 8080 }, saved)).toBe(false)
    expect(needsPasswordReentry({ ...draft, host: 'other.test' }, saved)).toBe(true)
    expect(needsPasswordReentry({ ...draft, host: 'other.test', password: 'typed' }, saved)).toBe(false)
    expect(validateProxyDraft({ ...draft, host: 'other.test' }, saved)).toContain('重新填写密码')
  })

  it('validates name, host and port', () => {
    const valid = { ...newProxyDraft(), name: 'A', host: '127.0.0.1' }
    expect(validateProxyDraft(valid)).toBeNull()
    expect(validateProxyDraft({ ...valid, name: ' ' })).toBe('请填写代理名称')
    expect(validateProxyDraft({ ...valid, host: '' })).toContain('主机')
    expect(validateProxyDraft({ ...valid, port: 0 })).toContain('1–65535')
    expect(validateProxyDraft({ ...valid, port: 70000 })).toContain('1–65535')
  })

  it('summarizes proxies and test results', () => {
    expect(proxyAddress(saved)).toBe('SOCKS5 hk.proxy.test:1080')
    expect(proxySummary(saved)).toBe('SOCKS5 · hk.proxy.test:1080 · 需要认证')
    expect(proxySummary({ ...saved, username: '', password_configured: false })).toBe('SOCKS5 · hk.proxy.test:1080 · 无认证')
    expect(describeProxyTest({
      success: false,
      message: '经此代理可访问 1/2 个服务',
      targets: [
        { name: 'X API', url: 'https://x', reachable: true, message: '可访问（HTTP 200）', status_code: 200, latency_ms: 80 },
        { name: 'OpenAI API', url: 'https://o', reachable: false, message: '连接超时', status_code: null, latency_ms: null },
      ],
    })).toEqual(['经此代理可访问 1/2 个服务', 'X API：可访问（HTTP 200），80 ms', 'OpenAI API：连接超时'])
  })

  it('lists every feature that can choose a proxy, including each vision model', () => {
    const usages = proxyUsages({
      x_proxy_id: 'p1',
      ai_image_openai_proxy_id: '',
      ai_image_vision_providers: [{ id: 'v1', name: 'GPT', proxy_id: 'p1' }],
    } as unknown as Settings)
    expect(usages).toEqual([
      { label: 'X（推文订阅、链接解析）', proxyId: 'p1', to: '/x/account' },
      { label: 'AI 图片检测 · OpenAI 来源检测', proxyId: '', to: '/ai-image/sources' },
      { label: 'AI 图片检测 · 视觉模型「GPT」', proxyId: 'p1', to: '/ai-image/vision' },
    ])
    expect(proxyUsages(null)).toEqual([])
  })
})
