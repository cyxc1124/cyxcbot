import { Children, isValidElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProxyEntry, Settings } from '../../api/types'
import { ProxyPicker } from '../../components/ProxyPicker'
import { useSettingsForm } from './SettingsContext'
import { ProxySettingCard } from './ProxySettingCard'

vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

const proxy: ProxyEntry = {
  id: 'px', name: '香港', scheme: 'socks5', host: 'hk.proxy.test', port: 1080, username: '', password_configured: false,
}
const savePartial = vi.fn()
let settings: Partial<Settings>

function render(props: Partial<Parameters<typeof ProxySettingCard>[0]> = {}) {
  return ProxySettingCard({ field: 'x_proxy_id', title: '出站代理', description: '说明', ...props })
}

describe('choosing a proxy for a feature', () => {
  beforeEach(() => {
    savePartial.mockReset()
    settings = { proxies: [proxy], x_proxy_id: '' }
    vi.mocked(useSettingsForm).mockImplementation(() => ({
      settings, savePartial, saving: false, formDisabled: false,
    }) as unknown as ReturnType<typeof useSettingsForm>)
  })

  it('shows direct connection and saves a choice immediately by default', () => {
    const html = renderToStaticMarkup(<MemoryRouter>{render()}</MemoryRouter>)
    expect(html).toContain('直接连接，未使用代理')
    expect(html).toContain('香港（SOCKS5 hk.proxy.test:1080）')
    expect(html).toContain('href="/system/proxies"')
    const picker = elements(render()).find((props) => props.id === 'proxy-x_proxy_id')!
    ;(picker.onChange as (proxyId: string) => void)('px')
    expect(savePartial).toHaveBeenCalledWith({ x_proxy_id: 'px' })
  })

  it('shows the saved proxy and flags an unsaved controlled choice', () => {
    settings = { ...settings, x_proxy_id: 'px' }
    expect(renderToStaticMarkup(<MemoryRouter>{render()}</MemoryRouter>)).toContain('经代理「香港」（SOCKS5 hk.proxy.test:1080）连接')
    const onChange = vi.fn()
    const html = renderToStaticMarkup(<MemoryRouter>{render({ value: '', onChange })}</MemoryRouter>)
    expect(html).toContain('修改尚未保存')
    const picker = elements(render({ value: '', onChange })).find((props) => props.id === 'proxy-x_proxy_id')!
    ;(picker.onChange as (proxyId: string) => void)('px')
    expect(onChange).toHaveBeenCalledWith('px')
    expect(savePartial).not.toHaveBeenCalled()
  })
})

describe('proxy picker guidance', () => {
  it('guides users to add a proxy when none exist and warns about deleted choices', () => {
    const empty = renderToStaticMarkup(
      <MemoryRouter><ProxyPicker id="p" value="" proxies={[]} disabled={false} onChange={vi.fn()} /></MemoryRouter>,
    )
    expect(empty).toContain('还没有添加代理')
    expect(empty).toContain('href="/system/proxies"')
    const deleted = renderToStaticMarkup(
      <MemoryRouter><ProxyPicker id="p" value="gone" proxies={[proxy]} disabled={false} onChange={vi.fn()} /></MemoryRouter>,
    )
    expect(deleted).toContain('之前选择的代理已被删除，当前直接连接')
  })
})
