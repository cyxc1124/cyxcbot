import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, getBotConnectionsStatus, getSetupStatus } from './client'

let replies: ((value: unknown) => void)[]
const fetchMock = vi.fn()

beforeEach(() => {
  replies = []
  fetchMock.mockReset().mockImplementation((_input: unknown, options: RequestInit = {}) => new Promise<Response>((resolve, reject) => {
    replies.push(value => resolve(new Response(JSON.stringify(value))))
    const abort = () => reject(new DOMException('Aborted', 'AbortError'))
    if (options.signal?.aborted) abort()
    else options.signal?.addEventListener('abort', abort, { once: true })
  }))
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('localStorage', { getItem: () => null })
})

afterEach(() => vi.unstubAllGlobals())

describe('API request cancellation', () => {
  it('does not share an aborted request with a newly mounted status indicator', async () => {
    const oldController = new AbortController()
    const first = getBotConnectionsStatus(oldController.signal)
    const rejected = expect(first).rejects.toBeInstanceOf(ApiClientError)
    oldController.abort()
    const newController = new AbortController()
    const second = getBotConnectionsStatus(newController.signal)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][1].signal).toBe(newController.signal)
    const data = {
      qq: { connected: true, bot_count: 1, bots: [], message: '已连接' },
      official_qq: { connected: false, configured: false, app_id: '', is_sandbox: false, use_websocket: false, message: '未配置' },
    }
    replies[1](data)
    await rejected
    await expect(second).resolves.toEqual(data)
  })

  it('still coalesces ordinary concurrent GET requests', async () => {
    const first = getSetupStatus()
    const second = getSetupStatus()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    replies[0]({ initialized: true })
    await expect(Promise.all([first, second])).resolves.toEqual([{ initialized: true }, { initialized: true }])
  })
})
