import { useState, type FormEvent, type ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getSettings, patchSettings } from '../api/client'
import type { Settings } from '../api/types'
import { useMountAsync } from '../hooks/useMountAsync'
import { LogLevelSettings } from './LogLevelSettings'

vi.mock('react', async (importOriginal) => ({
  ...await importOriginal<typeof import('react')>(),
  useState: vi.fn(),
  useCallback: (callback: unknown) => callback,
}))
vi.mock('../api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../api/client')>(),
  getSettings: vi.fn(),
  patchSettings: vi.fn(),
}))
vi.mock('../hooks/useMountAsync', () => ({ useMountAsync: vi.fn() }))
vi.mock('../contexts/ToastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

let state: unknown[]
let stateIndex: number

function render() {
  stateIndex = 0
  return LogLevelSettings()
}

function form(page: ReturnType<typeof LogLevelSettings>) {
  return page.props.children[1] as ReactElement<{ onSubmit: (event: FormEvent) => Promise<void> }>
}

describe('log output settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state = []
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? next(state[index]) : next
      }]
    }) as typeof useState)
  })

  it('loads and saves only output levels without changing Web filtering or other settings', async () => {
    const settings = { log_level: 'WARNING', log_file_level: 'DEBUG', nonebot_superusers: ['12345'] } as Settings
    vi.mocked(getSettings).mockResolvedValue(settings)
    vi.mocked(patchSettings).mockResolvedValue(settings)
    render()
    await vi.mocked(useMountAsync).mock.calls[0]![0]()
    const page = render()
    const html = renderToStaticMarkup(page)
    expect(html).toContain('终端 WARNING · 文件 DEBUG')
    expect(html).toContain('终端日志级别</legend>')
    expect(html).toContain('文件日志级别</legend>')
    expect(html).toMatch(/<input type="radio"[^>]*name="log_level"/)
    expect(html).toMatch(/<input type="radio"[^>]*name="log_file_level"/)
    expect(html).toContain('value="TRACE"')
    expect(html).toContain('value="CRITICAL"')
    await form(page).props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(patchSettings).toHaveBeenCalledWith({ log_level: 'WARNING', log_file_level: 'DEBUG' })
  })

  it('keeps the loaded values and draft available after a failed save', async () => {
    const settings = { log_level: 'INFO', log_file_level: 'ERROR' } as Settings
    vi.mocked(getSettings).mockResolvedValue(settings)
    vi.mocked(patchSettings).mockRejectedValue(new Error('保存失败，请重试'))
    render()
    await vi.mocked(useMountAsync).mock.calls[0]![0]()
    await form(render()).props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    const html = renderToStaticMarkup(render())
    expect(html).toContain('保存失败，请重试')
    expect(html).toContain('终端 INFO · 文件 ERROR')
    expect(html).not.toContain('disabled=""')
  })

  it('does not save before settings load and offers retry on load failure', async () => {
    vi.mocked(getSettings).mockRejectedValue(new Error('加载日志设置失败'))
    const page = render()
    await form(page).props.onSubmit({ preventDefault: vi.fn() } as unknown as FormEvent)
    expect(patchSettings).not.toHaveBeenCalled()
    await vi.mocked(useMountAsync).mock.calls[0]![0]()
    const html = renderToStaticMarkup(render())
    expect(html).toContain('加载日志设置失败')
    expect(html).toContain('重试')
    expect(html).toContain('disabled=""')
  })
})
