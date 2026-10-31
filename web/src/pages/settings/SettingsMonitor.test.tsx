import { Children, isValidElement, type FormEvent, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import type { Settings } from '../../api/types'
import { SettingsBilibiliMonitorPage, SettingsXMonitorPage } from './SettingsMonitor'
import { useSettingsForm } from './SettingsContext'

vi.mock('react', async (original) => ({
  ...await original<typeof import('react')>(),
  useState: (value: unknown) => [value, vi.fn()],
  useMemo: (fn: () => unknown) => fn(),
  useCallback: (fn: unknown) => fn,
}))
vi.mock('../../hooks/useMountAsync', () => ({ useMountAsync: vi.fn() }))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

function setup(mode: 'card' | 'screenshot' = 'card', stagger = true, imagesEnabled = true) {
  const settings = {
    dynamic_image_mode: mode, dynamic_card_color_source: 'image',
    dynamic_monitor_interval: 30, dynamic_monitor_use_stagger: stagger, dynamic_enable_screenshot: imagesEnabled,
    live_monitor_interval: 60, live_monitor_use_websocket: true, live_monitor_include_info: true,
  } as Settings
  const context = { settings, setSettings: vi.fn(), formDisabled: false, saving: false, savePartial: vi.fn() }
  vi.mocked(useSettingsForm).mockReturnValue(context as unknown as ReturnType<typeof useSettingsForm>)
  return { settings, context, page: SettingsBilibiliMonitorPage() }
}

describe('monitor card choices', () => {
  it.each([SettingsBilibiliMonitorPage, SettingsXMonitorPage])('keeps its own save button visible on desktop and mobile', (component) => {
    setup()
    const page = component()
    const save = elements(page).find((props) => props.type === 'submit')!
    expect(save.disabled).toBe(false)
    expect(save.className).not.toContain('hidden')
  })
  it('keeps conditional palette choices and saves their values with existing settings', () => {
    const { settings, context, page } = setup()
    const html = renderToStaticMarkup(page)
    expect(html).toContain('卡片取色来源')
    expect(html.match(/type="radio"/g)).toHaveLength(4)
    const choice = elements(page).find((props) => props.label === '卡片取色来源')!
    ;(choice.onChange as (value: string) => void)('avatar')
    const updater = context.setSettings.mock.calls[0][0]
    expect(updater(settings).dynamic_card_color_source).toBe('avatar')
    page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(context.savePartial).toHaveBeenCalledWith(settings)
  })

  it('hides palette choices for webpage screenshots without losing the saved source', () => {
    const { page } = setup('screenshot')
    const html = renderToStaticMarkup(page)
    expect(html).not.toContain('卡片取色来源')
    expect(html.match(/type="radio"/g)).toHaveLength(2)
  })

  it.each(['card', 'screenshot'] as const)('hides image choices when images are disabled in %s mode', (mode) => {
    const { settings, context, page } = setup(mode, true, false)
    const html = renderToStaticMarkup(page)
    expect(html).not.toContain('动态图片模式')
    expect(html).not.toContain('卡片取色来源')
    expect(html).not.toContain('type="radio"')
    page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(context.savePartial).toHaveBeenCalledWith(settings)
  })

  it('defaults an unset palette source to the author avatar when displaying and saving', () => {
    const { settings, context } = setup()
    delete settings.dynamic_card_color_source
    const page = SettingsBilibiliMonitorPage()
    const choice = elements(page).find((props) => props.label === '卡片取色来源')!
    expect(choice.value).toBe('avatar')
    page.props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(context.savePartial).toHaveBeenCalledWith({ ...settings, dynamic_card_color_source: 'avatar' })
  })

  it('describes the actual polling strategy when staggered checks are disabled', () => {
    const { page } = setup('card', false)
    const html = renderToStaticMarkup(page)
    expect(html).toContain('每 N 秒依次检查全部 UP 主')
    expect(html).not.toContain('分散检查的单次间隔不低于 3 秒')
  })
})
