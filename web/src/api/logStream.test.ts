import { describe, expect, it, vi } from 'vitest'
import { readLogStream } from './logStream'

const log = {
  session_id: 'session', entry_id: 1, ts: '2026-01-01 00:00:00.000',
  level: 'INFO', logger: 'test', message: '中文日志\n第二行',
}

function byteStream(text: string) {
  return new ReadableStream<Uint8Array<ArrayBuffer>>({
    start(controller) {
      for (const byte of new TextEncoder().encode(text)) {
        controller.enqueue(Uint8Array.of(byte))
      }
      controller.close()
    },
  })
}

describe('log SSE decoding', () => {
  it.each(['\n', '\r\n', '\r'])('handles split UTF-8, %j lines, comments and multiline data', async (eol) => {
    const data = JSON.stringify(log, null, 2).split('\n').map(line => `data: ${line}`).join(eol)
    const source = `: ping${eol}${eol}id: 1${eol}retry: 3000${eol}${data}${eol}${eol}`
    const onLog = vi.fn()
    await readLogStream(byteStream(source), onLog)
    expect(onLog).toHaveBeenCalledExactlyOnceWith(log)
  })

  it('ignores malformed events and discards an unfinished event at EOF', async () => {
    const onLog = vi.fn()
    await readLogStream(byteStream([
      'data: not-json\n\n',
      'data: null\n\n',
      'data: {}\n\n',
      `data:${JSON.stringify(log)}\n\n`,
      `data: ${JSON.stringify({ ...log, entry_id: 2 })}\n`,
    ].join('')), onLog)
    expect(onLog).toHaveBeenCalledExactlyOnceWith(log)
  })

  it('releases the body when the consumer fails', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream<Uint8Array<ArrayBuffer>>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(log)}\n\n`))
      },
      cancel,
    })
    await expect(readLogStream(body, () => { throw new Error('consumer failed') }))
      .rejects.toThrow('consumer failed')
    expect(cancel).toHaveBeenCalledTimes(1)
  })
})
