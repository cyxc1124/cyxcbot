const FALLBACK_TZ = 'Asia/Shanghai'

/** 后端时间为 UTC；无时区后缀的 ISO 字符串按 UTC 解析 */
function parseApiDateTime(iso: string): Date {
  const trimmed = iso.trim()
  if (/[Zz]$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed)) {
    return new Date(trimmed)
  }
  const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  return new Date(`${normalized}Z`)
}

/** 优先用浏览器本地时区；无法检测时回退北京时间 */
export function resolveDisplayTimeZone(): string {
  try {
    const { timeZone } = Intl.DateTimeFormat().resolvedOptions()
    if (timeZone) return timeZone
  } catch {
    // ignore
  }
  return FALLBACK_TZ
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const date = parseApiDateTime(iso)
    if (Number.isNaN(date.getTime())) return iso

    const timeZone = resolveDisplayTimeZone()
    const showOffset = timeZone !== FALLBACK_TZ

    return date.toLocaleString('zh-CN', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      ...(showOffset ? { timeZoneName: 'shortOffset' as const } : {}),
    })
  } catch {
    return iso
  }
}

/** 运行时长：天时分秒，秒位实时递增 */
export function formatUptime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  const mins = Math.floor((s % 3600) / 60)
  const secs = s % 60
  return `${days}天${hours}时${mins}分${secs}秒`
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

const MEMORY_GB_THRESHOLD_MB = 1024

/** 内存容量：≥ 1 GB 时用 GB，否则用 MB */
export function formatMemoryMb(mb: number): string {
  if (mb >= MEMORY_GB_THRESHOLD_MB) {
    return `${(mb / MEMORY_GB_THRESHOLD_MB).toFixed(1)} GB`
  }
  return `${Math.round(mb)} MB`
}

/** 内存已用/总量，总量 ≥ 1 GB 时两项均以 GB 显示 */
export function formatMemoryUsage(usedMb: number, totalMb: number): string {
  if (totalMb >= MEMORY_GB_THRESHOLD_MB) {
    return `已用 ${(usedMb / MEMORY_GB_THRESHOLD_MB).toFixed(1)} / ${(totalMb / MEMORY_GB_THRESHOLD_MB).toFixed(1)} GB`
  }
  return `已用 ${Math.round(usedMb)} / ${Math.round(totalMb)} MB`
}
