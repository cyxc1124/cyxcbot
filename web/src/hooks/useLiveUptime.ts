import { useEffect, useState } from 'react'

/** 基于 API 返回的基准值，在前端每秒递增显示运行时长 */
export function useLiveUptime(baselineSeconds: number, active = true): number {
  const [displaySeconds, setDisplaySeconds] = useState(baselineSeconds)

  useEffect(() => {
    setDisplaySeconds(baselineSeconds)
    if (!active) return

    const syncedAt = Date.now()
    const tick = () => {
      setDisplaySeconds(
        baselineSeconds + Math.floor((Date.now() - syncedAt) / 1000),
      )
    }

    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [baselineSeconds, active])

  return displaySeconds
}
