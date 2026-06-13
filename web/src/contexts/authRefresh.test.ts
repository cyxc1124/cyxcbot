import { describe, expect, it } from 'vitest'
import { ApiClientError } from '../api/client'
import { getInitErrorOnRefreshFailure } from './authRefresh'

describe('getInitErrorOnRefreshFailure', () => {
  it('returns error message when setup status probe fails', () => {
    const err = new ApiClientError('后端服务暂不可用，数据暂时无法加载', 503)

    expect(getInitErrorOnRefreshFailure(false, err)).toBe(
      '后端服务暂不可用，数据暂时无法加载',
    )
  })

  it('returns fallback message for unknown errors during setup probe', () => {
    expect(getInitErrorOnRefreshFailure(false, new Error('network'))).toBe(
      '无法获取初始化状态，请重试',
    )
  })

  it('does not treat getMe failure as init probe failure', () => {
    const err = new ApiClientError('未授权，请重新登录', 401)

    expect(getInitErrorOnRefreshFailure(true, err)).toBeNull()
  })
})
