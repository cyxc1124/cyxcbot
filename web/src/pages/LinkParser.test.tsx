import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { LinkParserPage } from './LinkParser'
import type { TemplateCategory } from '../constants/messageTemplates'

vi.mock('../components/LinkParserPolicyTabs', () => ({
  LinkParserGroupPolicyTab: () => <p>B站群原策略</p>,
  LinkParserUserPolicyTab: () => <p>B站好友原策略</p>,
}))
vi.mock('../components/DouyinLinkParserPolicyTabs', () => ({
  DouyinLinkParserGroupPolicyTab: () => <p>抖音群原策略</p>,
  DouyinLinkParserUserPolicyTab: () => <p>抖音好友原策略</p>,
}))
vi.mock('../components/XLinkParserPolicyTabs', () => ({
  XLinkParserGroupPolicyTab: () => <p>X群原策略</p>,
  XLinkParserUserPolicyTab: () => <p>X好友原策略</p>,
}))

describe('platform parsers reuse conversation policy editors', () => {
  it.each([
    ['bilibili', 'groups', 'B站群原策略'], ['bilibili', 'friends', 'B站好友原策略'],
    ['douyin', 'groups', '抖音群原策略'], ['douyin', 'friends', '抖音好友原策略'],
    ['x', 'groups', 'X群原策略'], ['x', 'friends', 'X好友原策略'],
  ])('opens %s / %s from a direct link', (platform, scope, editor) => {
    const html = renderToStaticMarkup(<MemoryRouter initialEntries={[`/${platform}/parser?scope=${scope}`]}><LinkParserPage platform={platform as TemplateCategory} /></MemoryRouter>)
    expect(html).toContain(editor)
    expect(html).toContain(`href="/${platform}/account"`)
    expect(html).toContain(`href="/${platform}/templates"`)
    expect(html).toContain(`href="${scope === 'friends' ? '/friends' : '/groups'}"`)
    expect(html).toContain('href="/system/advanced"')
  })
})
