import { Children, isValidElement, type ReactElement, type ReactNode } from 'react'
import { createRoutesFromElements, matchRoutes, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { AuthGuard } from '../routes/Guards'
import { findNavigation, navigationSections } from './navigation'
import { allTemplateFields, groupTemplateFields } from './messageTemplates'

function descendants(node: ReactNode): ReactElement<{ children?: ReactNode }>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<{ children?: ReactNode }>(child)
    ? [child, ...descendants(child.props.children)] : [])
}

describe('navigation destinations', () => {
  const routes = createRoutesFromElements(descendants(App()).find((node) => node.type === Routes)!.props.children)
  const items = navigationSections.flatMap((section) => section.groups.flatMap((group) => group.items))

  it.each(items)('connects $to to an actual page and its breadcrumb', (item) => {
    const matches = matchRoutes(routes, item.to)
    expect(matches?.at(-1)?.route.path).not.toBe('*')
    expect(matches?.at(-1)?.route.element).toBeTruthy()
    expect(matches?.some(({ route }) => isValidElement(route.element) && route.element.type === AuthGuard)).toBe(true)
    expect(findNavigation(item.to)?.item).toBe(item)
    expect(findNavigation(`${item.to}/`)?.item).toBe(item)
  })

  it('has unique destinations and no platform accounts or parameters under system', () => {
    expect(new Set(items.map((item) => item.to)).size).toBe(items.length)
    const system = navigationSections.find((section) => section.section === '系统')!
    expect(system.groups.flatMap((group) => group.items).some((item) => /bilibili|douyin|\/x\//.test(item.to))).toBe(false)
    expect(findNavigation('/rust/remote/servers')?.group).toBe('远控与权限')
    expect(findNavigation('/rust/players/shop')?.group).toBe('玩家与积分')
  })
})

describe('template use cases', () => {
  it('keeps every existing field exactly once under its purpose', () => {
    const groups = groupTemplateFields(allTemplateFields)
    const keys = groups.flatMap((group) => group.fields.map((field) => field.key))
    expect(keys.sort()).toEqual(allTemplateFields.map((field) => field.key).sort())
    expect(new Set(keys).size).toBe(allTemplateFields.length)
    expect(groups.find((group) => group.label === '命令回复')?.fields.filter((field) => field.key.startsWith('dynamic_template_extract'))).toHaveLength(4)
    expect(groups.find((group) => group.label === '链接解析')?.fields.every((field) => field.key.startsWith('link_'))).toBe(true)
  })
})
