export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
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
