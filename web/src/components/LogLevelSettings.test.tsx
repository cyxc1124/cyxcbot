import { Children, isValidElement, useState, type ReactElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getSettings, patchSettings } from '../api/client'
import type { LogLevel, Settings } from '../api/types'
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

type ElementProps = { children?: ReactNode; name?: string; value?: string; checked?: boolean; onChange?: () => Promise<void> }

function elements(node: ReactNode): ReactElement<ElementProps>[] {
  return Children.toArray(node).flatMap((child) => (
    isValidElement<ElementProps>(child) ? [child, ...elements(child.props.children)] : []
  ))
}

function radio(name: 'log_level' | 'log_file_level', value: LogLevel) {
  return elements(render()).find((child) => child.type === 'input' && child.props.name === name && child.props.value === value)!
}

async function load(settings: Settings) {
  vi.mocked(getSettings).mockResolvedValue(settings)
  render()
  await vi.mocked(useMountAsync).mock.calls[0]![0]()
}

describe('log output settings', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    state = []
    vi.mocked(useState).mockImplementation(((initial: unknown) => {
      const index = stateIndex++
      if (!(index in state)) state[index] = initial
      return [state[index], (next: unknown) => {
        state[index] = typeof next === 'function' ? next(state[index]) : next
      }]
    }) as typeof useState)
  })

  it('saves the clicked level immediately and leaves other settings untouched, without a save button', async () => {
    const settings = { log_level: 'WARNING', log_file_level: 'DEBUG', nonebot_superusers: ['12345'] } as Settings
    await load(settings)
    vi.mocked(patchSettings).mockResolvedValue({ ...settings, log_level: 'TRACE' })
    const html = renderToStaticMarkup(render())
    expect(html).toContain('终端 WARNING · 文件 DEBUG')
    expect(html).toContain('终端日志级别</legend>')
    expect(html).toContain('文件日志级别</legend>')
    expect(html).toMatch(/<input type="radio"[^>]*name="log_level"/)
    expect(html).toMatch(/<input type="radio"[^>]*name="log_file_level"/)
    expect(html).toContain('value="TRACE"')
    expect(html).toContain('value="CRITICAL"')
    expect(html).not.toContain('<form')
    expect(html).not.toContain('<button')
    await radio('log_level', 'TRACE').props.onChange!()
    expect(patchSettings).toHaveBeenCalledExactlyOnceWith({ log_level: 'TRACE' })
    expect(radio('log_level', 'TRACE').props.checked).toBe(true)
    expect(radio('log_file_level', 'DEBUG').props.checked).toBe(true)
    await radio('log_level', 'TRACE').props.onChange!()
    expect(patchSettings).toHaveBeenCalledTimes(1)
  })

  it('lets both outputs save independently and ignores stale other-output values in reversed responses', async () => {
    const settings = { log_level: 'INFO', log_file_level: 'ERROR' } as Settings
    await load(settings)
    let finishTerminal!: (value: Settings) => void
    let finishFile!: (value: Settings) => void
    vi.mocked(patchSettings)
      .mockReturnValueOnce(new Promise((resolve) => { finishTerminal = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { finishFile = resolve }))
    const terminal = radio('log_level', 'DEBUG').props.onChange!()
    expect(renderToStaticMarkup(render()).match(/ disabled=""/g)).toHaveLength(1)
    const file = radio('log_file_level', 'CRITICAL').props.onChange!()
    expect(patchSettings).toHaveBeenNthCalledWith(1, { log_level: 'DEBUG' })
    expect(patchSettings).toHaveBeenNthCalledWith(2, { log_file_level: 'CRITICAL' })
    expect(radio('log_level', 'DEBUG').props.checked).toBe(true)
    expect(radio('log_file_level', 'CRITICAL').props.checked).toBe(true)
    finishFile({ ...settings, log_file_level: 'CRITICAL' })
    await file
    finishTerminal({ ...settings, log_level: 'DEBUG' })
    await terminal
    expect(renderToStaticMarkup(render())).toContain('终端 DEBUG · 文件 CRITICAL')
    expect(renderToStaticMarkup(render())).not.toContain('disabled=""')
  })

  it('restores a failed choice while preserving the other saved output and allowing retry', async () => {
    const settings = { log_level: 'INFO', log_file_level: 'ERROR' } as Settings
    await load(settings)
    vi.mocked(patchSettings)
      .mockRejectedValueOnce(new Error('终端保存失败，请重试'))
      .mockResolvedValueOnce({ ...settings, log_file_level: 'DEBUG' })
    await Promise.all([
      radio('log_level', 'TRACE').props.onChange!(),
      radio('log_file_level', 'DEBUG').props.onChange!(),
    ])
    const html = renderToStaticMarkup(render())
    expect(html).toContain('终端保存失败，请重试')
    expect(html).toContain('终端 INFO · 文件 DEBUG')
    expect(radio('log_level', 'INFO').props.checked).toBe(true)
    expect(radio('log_file_level', 'DEBUG').props.checked).toBe(true)
    expect(html).not.toContain('disabled=""')
    vi.mocked(patchSettings).mockResolvedValue({ ...settings, log_level: 'TRACE' })
    await radio('log_level', 'TRACE').props.onChange!()
    expect(renderToStaticMarkup(render())).toContain('终端 TRACE · 文件 DEBUG')
    expect(renderToStaticMarkup(render())).not.toContain('终端保存失败，请重试')
  })

  it('does not save before settings load and offers retry on load failure', async () => {
    vi.mocked(getSettings).mockRejectedValue(new Error('加载日志设置失败'))
    await radio('log_level', 'DEBUG').props.onChange!()
    expect(patchSettings).not.toHaveBeenCalled()
    await vi.mocked(useMountAsync).mock.calls[0]![0]()
    const html = renderToStaticMarkup(render())
    expect(html).toContain('加载日志设置失败')
    expect(html).toContain('重试')
    expect(html).toContain('disabled=""')
  })
})
