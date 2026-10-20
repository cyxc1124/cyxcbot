import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, getBotConnectionsStatus, getRecentLogs, getSetupStatus, streamLogs } from './client'

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

describe('authenticated log SSE requests', () => {
  const log = {
    session_id: 'session', entry_id: 1, ts: '2026-01-01',
    level: 'INFO', logger: 'test', message: 'hello',
  }

  it('uses the shared Bearer header and passes cancellation without putting credentials in the URL', async () => {
    vi.stubGlobal('localStorage', { getItem: () => 'test-token' })
    fetchMock.mockResolvedValue(new Response(`data: ${JSON.stringify(log)}\n\n`, {
      headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
    }))
    const controller = new AbortController()
    const onOpen = vi.fn()
    const onLog = vi.fn()
    await streamLogs('WARNING', { signal: controller.signal, onOpen, onLog })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/logs/stream?min_level=WARNING')
    expect(options.headers.get('Authorization')).toBe('Bearer test-token')
    expect(options.headers.get('Accept')).toBe('text/event-stream')
    expect(options.signal).toBe(controller.signal)
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onLog).toHaveBeenCalledExactlyOnceWith(log)
  })

  it('preserves the existing login redirect on expired credentials', async () => {
    const removeItem = vi.fn()
    vi.stubGlobal('localStorage', { getItem: () => 'expired', removeItem })
    const location = { pathname: '/logs', href: '/logs' }
    vi.stubGlobal('window', { location })
    fetchMock.mockResolvedValue(new Response('{"detail":"Invalid token"}', { status: 401 }))
    const onOpen = vi.fn()
    await expect(streamLogs('INFO', { signal: new AbortController().signal, onOpen, onLog: vi.fn() }))
      .rejects.toMatchObject({ status: 401 })
    expect(location.href).toBe('/login')
    expect(removeItem).toHaveBeenCalledWith('cyxcbot_access_token')
    expect(onOpen).not.toHaveBeenCalled()
  })

  it.each([403, 503])('surfaces HTTP %i for the page retry policy', async (status) => {
    fetchMock.mockResolvedValue(new Response('{"detail":"Admin required"}', { status }))
    const onOpen = vi.fn()
    await expect(streamLogs('INFO', { signal: new AbortController().signal, onOpen, onLog: vi.fn() }))
      .rejects.toMatchObject({ status })
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('rejects a proxy HTML response before marking the stream connected', async () => {
    fetchMock.mockResolvedValue(new Response('<html>error</html>', {
      headers: { 'Content-Type': 'text/html' },
    }))
    const onOpen = vi.fn()
    await expect(streamLogs('INFO', { signal: new AbortController().signal, onOpen, onLog: vi.fn() }))
      .rejects.toThrow('无效的事件流')
    expect(onOpen).not.toHaveBeenCalled()
  })

  it('aborts a pending body read on navigation', async () => {
    fetchMock.mockImplementation((_url: string, { signal }: RequestInit) => new Response(
      new ReadableStream({
        start(controller) {
          signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')))
        },
      }),
      { headers: { 'Content-Type': 'text/event-stream' } },
    ))
    const controller = new AbortController()
    let opened: () => void
    const ready = new Promise<void>(resolve => { opened = resolve })
    const stream = streamLogs('INFO', { signal: controller.signal, onOpen: () => opened(), onLog: vi.fn() })
    const rejected = expect(stream).rejects.toMatchObject({ name: 'AbortError' })
    await ready
    controller.abort()
    await rejected
  })

  it('allows cancelling the initial history request', async () => {
    const controller = new AbortController()
    const history = getRecentLogs({ min_level: 'ERROR' }, controller.signal)
    const rejected = expect(history).rejects.toBeInstanceOf(ApiClientError)
    controller.abort()
    await rejected
    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal)
  })
})
