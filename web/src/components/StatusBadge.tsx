interface StatusBadgeProps {
  active: boolean
  activeLabel?: string
  inactiveLabel?: string
}

export function StatusBadge({
  active,
  activeLabel = '运行中',
  inactiveLabel = '已停止',
}: StatusBadgeProps) {
  return (
    <span className={active ? 'badge-success' : 'badge-neutral'}>
      {active ? activeLabel : inactiveLabel}
    </span>
  )
}

export function LevelBadge({ level }: { level: string }) {
  const styles: Record<string, string> = {
    debug: 'badge-neutral',
    info: 'badge-success',
    warning: 'badge-warning',
    error: 'badge-danger',
  }
  return <span className={styles[level] ?? 'badge-neutral'}>{level}</span>
}
