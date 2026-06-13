import { describe, expect, it } from 'vitest'
import {
  shouldAllowSetupRoute,
  shouldLeaveSetupRoute,
  shouldRedirectToSetup,
} from './guardLogic'

describe('setup guard routing', () => {
  it('does not redirect to setup when initialized is unknown', () => {
    expect(
      shouldRedirectToSetup({ initialized: null, loading: false, initError: null }),
    ).toBe(false)
  })

  it('redirects to setup only when backend reports uninitialized', () => {
    expect(
      shouldRedirectToSetup({ initialized: false, loading: false, initError: null }),
    ).toBe(true)
  })

  it('does not redirect to setup when init probe failed', () => {
    expect(
      shouldRedirectToSetup({
        initialized: null,
        loading: false,
        initError: '后端服务暂不可用，数据暂时无法加载',
      }),
    ).toBe(false)
  })

  it('allows setup route only for explicit uninitialized state', () => {
    expect(
      shouldAllowSetupRoute({ initialized: false, loading: false, initError: null }),
    ).toBe(true)
    expect(
      shouldAllowSetupRoute({ initialized: null, loading: false, initError: null }),
    ).toBe(false)
    expect(
      shouldAllowSetupRoute({
        initialized: null,
        loading: false,
        initError: '后端服务暂不可用，数据暂时无法加载',
      }),
    ).toBe(false)
  })

  it('leaves setup route only after explicit initialized state', () => {
    expect(
      shouldLeaveSetupRoute({ initialized: true, loading: false, initError: null }),
    ).toBe(true)
    expect(
      shouldLeaveSetupRoute({ initialized: null, loading: false, initError: null }),
    ).toBe(false)
  })
})
