import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError, getBotConnectionsStatus, getRecentLogs, getSetupStatus, clearLegacyToken, getMe, postLogin, postLogout, postSetup, pollBilibiliQrcodeLogin, pollDouyinQrcodeLogin, putPassword, streamLogs } from './client'

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
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value) }),
    removeItem: vi.fn((key: string) => { values.delete(key) }),
  })
  vi.stubGlobal('sessionStorage', { removeItem: vi.fn() })
})

afterEach(() => vi.unstubAllGlobals())

it('never reads a legacy JWT when sending a browser API request', async () => {
  const getItem = vi.fn(() => 'legacy-jwt')
  vi.stubGlobal('localStorage', { getItem })
  fetchMock.mockResolvedValue(new Response('{}'))
  await getBotConnectionsStatus(new AbortController().signal)
  const [, options] = fetchMock.mock.calls[0]
  expect(options.headers.has('Authorization')).toBe(false)
  expect(options.headers.get('X-Cyxcbot-Session')).toBe('cookie')
  expect(options.credentials).toBe('same-origin')
  expect(getItem).not.toHaveBeenCalledWith('cyxcbot_access_token')
})

describe('cookie sessions', () => {
  const credentials = { username: 'admin', password: 'old-password' }
  const password = { current_password: 'old-password', new_password: 'new-password' }
  const changes = [
    ['login', () => postLogin(credentials), 'POST', '/auth/login', credentials],
    ['setup', () => postSetup(credentials), 'POST', '/setup', credentials],
    ['password', () => putPassword(password), 'PUT', '/auth/password', password],
    ['logout', () => postLogout(), 'POST', '/auth/logout', undefined],
  ] as const

  it('purges the old token without reading or migrating it', () => {
    clearLegacyToken()
    expect(localStorage.removeItem).toHaveBeenCalledWith('cyxcbot_access_token')
    expect(sessionStorage.removeItem).toHaveBeenCalledWith('cyxcbot_access_token')
    expect(localStorage.getItem).not.toHaveBeenCalled()
    expect(localStorage.setItem).not.toHaveBeenCalled()
  })

  it.each(changes)('uses a cookie-only %s response and keeps credentials out of the URL', async (_name, change, method, path, body) => {
    fetchMock.mockResolvedValue(new Response('{"message":"ok"}'))
    await expect(change()).resolves.toBeUndefined()
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe(`/api/v1${path}`)
    expect(options.method).toBe(method)
    expect(options.headers.has('Authorization')).toBe(false)
    expect(options.headers.get('X-Cyxcbot-Session')).toBe('cookie')
    expect(options.credentials).toBe('same-origin')
    expect(options.body ? JSON.parse(options.body) : undefined).toEqual(body)
    expect(localStorage.setItem).not.toHaveBeenCalledWith('cyxcbot_access_token', expect.anything())
  })

  it.each(changes)('ignores a late 401 after %s changes the session', async (_name, change) => {
    let finish!: (response: Response) => void
    const location = { pathname: '/about', href: '/about' }
    vi.stubGlobal('window', { location })
    fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
      .mockResolvedValue(new Response('{"message":"ok"}'))
    const pending = getBotConnectionsStatus(new AbortController().signal)
    await change()
    finish(new Response('{}', { status: 401 }))
    await expect(pending).rejects.toMatchObject({ status: 401, message: '登录状态已更新，请重试' })
    expect(location.href).toBe('/about')
  })

  it('ignores a late 401 after another tab rotates the session', async () => {
    const location = { pathname: '/about', href: '/about' }
    vi.stubGlobal('window', { location })
    fetchMock.mockResolvedValue(new Response('{}', { status: 401 }))
    const pending = getBotConnectionsStatus(new AbortController().signal)
    localStorage.setItem('cyxcbot_auth_version', 'another-tab-change')
    await expect(pending).rejects.toMatchObject({ message: '登录状态已更新，请重试' })
    expect(location.href).toBe('/about')
  })

  it('does not depend on browser storage being available', async () => {
    const unavailable = () => { throw new DOMException('Storage blocked', 'SecurityError') }
    vi.stubGlobal('localStorage', { getItem: unavailable, setItem: unavailable, removeItem: unavailable })
    fetchMock.mockResolvedValue(new Response('{"message":"ok"}'))
    expect(clearLegacyToken).not.toThrow()
    await expect(postLogin(credentials)).resolves.toBeUndefined()
  })

  it('sends logout after a pending password response sets the replacement cookie', async () => {
    let finish!: (response: Response) => void
    fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve }))
      .mockResolvedValueOnce(new Response('{"message":"ok"}'))
    const rotation = putPassword(password)
    const logout = postLogout()
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/auth/password')
    finish(new Response('{"message":"ok"}'))
    await rotation
    await logout
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/logout')
  })

  it('allows logout after a failed session update', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{"detail":"wrong password"}', { status: 400 }))
      .mockResolvedValueOnce(new Response('{"message":"ok"}'))
    await expect(putPassword(password)).rejects.toMatchObject({ status: 400 })
    await expect(postLogout()).resolves.toBeUndefined()
  })

  it('does not share an old in-flight GET across a session change', async () => {
    const first = getMe()
    const rotation = putPassword(password)
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    replies[1]({ message: 'ok' })
    await rotation
    const second = getMe()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    replies[0]({ username: 'old-session' })
    replies[2]({ username: 'new-session' })
    await expect(first).resolves.toEqual({ username: 'old-session' })
    await expect(second).resolves.toEqual({ username: 'new-session' })
  })

  it.each([
    ['bilibili', (signal: AbortSignal) => pollBilibiliQrcodeLogin({ key: 'qr' }, signal), { qrcode: { key: 'qr' } }],
    ['douyin', (signal: AbortSignal) => pollDouyinQrcodeLogin('qr-session', signal), { session_id: 'qr-session' }],
  ] as const)('uses the same cookie and cancellation boundary for %s QR polling', async (platform, poll, body) => {
    fetchMock.mockResolvedValue(new Response('{}'))
    const controller = new AbortController()
    await poll(controller.signal)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe(`/api/v1/${platform}/login/qrcode/poll`)
    expect(options.headers.has('Authorization')).toBe(false)
    expect(options.headers.get('X-Cyxcbot-Session')).toBe('cookie')
    expect(options.credentials).toBe('same-origin')
    expect(options.signal).toBe(controller.signal)
    expect(JSON.parse(options.body)).toEqual(body)
  })
})

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

  it('uses the shared cookie authentication and passes cancellation without putting credentials in the URL', async () => {
    fetchMock.mockResolvedValue(new Response(`data: ${JSON.stringify(log)}\n\n`, {
      headers: { 'Content-Type': 'text/event-stream; charset=utf-8' },
    }))
    const controller = new AbortController()
    const onOpen = vi.fn()
    const onLog = vi.fn()
    await streamLogs('WARNING', { signal: controller.signal, onOpen, onLog })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/logs/stream?min_level=WARNING')
    expect(options.headers.has('Authorization')).toBe(false)
    expect(options.headers.get('X-Cyxcbot-Session')).toBe('cookie')
    expect(options.credentials).toBe('same-origin')
    expect(options.headers.get('Accept')).toBe('text/event-stream')
    expect(options.signal).toBe(controller.signal)
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onLog).toHaveBeenCalledExactlyOnceWith(log)
  })

  it('preserves the existing login redirect on expired credentials', async () => {
    const location = { pathname: '/logs', href: '/logs' }
    vi.stubGlobal('window', { location })
    fetchMock.mockResolvedValue(new Response('{"detail":"Invalid token"}', { status: 401 }))
    const onOpen = vi.fn()
    await expect(streamLogs('INFO', { signal: new AbortController().signal, onOpen, onLog: vi.fn() }))
      .rejects.toMatchObject({ status: 401 })
    expect(location.href).toBe('/login')
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
