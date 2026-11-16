import { Children, isValidElement, useState, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSettingsForm } from './SettingsContext'
import { SettingsAiImageCommandPage } from './SettingsAiImageCommand'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(), useState: vi.fn(),
}))
vi.mock('./SettingsContext', () => ({ useSettingsForm: vi.fn() }))
const showToast = vi.fn()
vi.mock('../../contexts/ToastContext', () => ({ useToast: () => ({ showToast }) }))

function elements(node: ReactNode): Record<string, unknown>[] {
  return Children.toArray(node).flatMap((child) => isValidElement<Record<string, unknown>>(child)
    ? [child.props, ...elements(child.props.children as ReactNode)] : [])
}

let state: unknown[]
let stateIndex: number
const savePartial = vi.fn()
const settings = {
  command_prefixes: ['/', '#'],
  command_aliases: { ai_image_detect: { enabled: true, triggers: ['鉴图'] } },
}

function renderPage() { stateIndex = 0; return SettingsAiImageCommandPage() }

function card() {
  return elements(renderPage()).find((props) => Boolean(props.onTextChange))!
}

function submit() {
  const form = elements(renderPage()).find((props) => Boolean(props.onSubmit))!
  ;(form.onSubmit as (event: unknown) => void)({ preventDefault: vi.fn() })
}

describe('AI image detection command', () => {
  beforeEach(() => {
    state = []
    savePartial.mockReset()
    showToast.mockReset()
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = typeof initial === 'function' ? (initial as () => unknown)() : initial
      return [state[index], (next: unknown) => { state[index] = next }]
    }) as typeof useState)
    vi.mocked(useSettingsForm).mockReturnValue({
      settings, savePartial, saving: false, formDisabled: false,
    } as unknown as ReturnType<typeof useSettingsForm>)
  })

  it('shows the saved trigger and only patches this command', () => {
    const html = renderToStaticMarkup(renderPage())
    expect(html).toContain('鉴图')
    expect(html).toContain('不区分英文大小写')
    expect(html).toContain('/ #')
    ;(card().onTextChange as (text: string) => void)('鉴图\n 是AI吗 \n')
    submit()
    expect(savePartial).toHaveBeenCalledWith({
      command_aliases: { ai_image_detect: { enabled: true, triggers: ['鉴图', '是AI吗'] } },
    })
  })

  it('restores defaults, allows disabling and rejects an enabled empty trigger list', () => {
    ;(card().onReset as () => void)()
    expect((card().value as { text: string }).text).toBe('ai吗？\nai吗?\nai吗')
    ;(card().onTextChange as (text: string) => void)('  ')
    submit()
    expect(savePartial).not.toHaveBeenCalled()
    expect(showToast).toHaveBeenCalledWith('error', expect.stringContaining('未填写触发词'))
    ;(card().onToggle as (enabled: boolean) => void)(false)
    submit()
    expect(savePartial).toHaveBeenCalledWith({
      command_aliases: { ai_image_detect: { enabled: false, triggers: [] } },
    })
  })
})
