import type { RuntimeLogEntry } from './types'

function parseLog(data: string): RuntimeLogEntry | undefined {
  let entry: Partial<RuntimeLogEntry> | null
  try {
    entry = JSON.parse(data)
  } catch {
    return
  }
  if (
    entry && typeof entry === 'object'
    && typeof entry.session_id === 'string'
    && typeof entry.entry_id === 'number'
    && typeof entry.ts === 'string'
    && typeof entry.level === 'string'
    && typeof entry.logger === 'string'
    && typeof entry.message === 'string'
  ) {
    return entry as RuntimeLogEntry
  }
}

export async function readLogStream(
  body: ReadableStream<Uint8Array<ArrayBuffer>>,
  onLog: (entry: RuntimeLogEntry) => void,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let pendingLine = ''
  let skipLF = false
  let data: string[] = []
  try {
    while (true) {
      const { value: bytes, done } = await reader.read()
      if (done) return
      const value = decoder.decode(bytes, { stream: true })
      if (!value) continue
      // CRLF may straddle chunks; a trailing CR has already ended its line.
      const chunk = skipLF && value.startsWith('\n') ? value.slice(1) : value
      skipLF = value.endsWith('\r')
      const lines = (pendingLine + chunk).split(/\r\n|\r|\n/)
      pendingLine = lines.pop() ?? ''
      for (const line of lines) {
        if (line === '') {
          if (data.length) {
            const entry = parseLog(data.join('\n'))
            if (entry) onLog(entry)
          }
          data = []
        } else if (line === 'data' || line.startsWith('data:')) {
          data.push(line.slice(5).replace(/^ /, ''))
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
