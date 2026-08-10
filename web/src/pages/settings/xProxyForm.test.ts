import { describe, expect, it } from 'vitest'
import { validateXProxyDraft } from './xProxyForm'

describe('validateXProxyDraft', () => {
  it('rejects enabled proxy without host', () => {
    expect(validateXProxyDraft({ enabled: true, host: '  ' })).toBe(
      '启用代理时请填写主机地址',
    )
  })

  it('allows disabling proxy while keeping host filled', () => {
    expect(validateXProxyDraft({ enabled: false, host: '127.0.0.1' })).toBeNull()
  })

  it('allows enabled proxy with host', () => {
    expect(validateXProxyDraft({ enabled: true, host: '127.0.0.1' })).toBeNull()
  })

  it('allows disabled proxy with empty host', () => {
    expect(validateXProxyDraft({ enabled: false, host: '' })).toBeNull()
  })
})
