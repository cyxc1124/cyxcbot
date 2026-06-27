interface ResourceUsageCardProps {
  label: string
  /** Normalized 0-100 value for progress bar width and color */
  percent: number | null | undefined
  detail?: string
  /** Override the displayed number (e.g. "180.0%") when percent is a normalized ratio */
  displayValue?: string
}

function barColor(percent: number): string {
  if (percent >= 85) return 'bg-red-500'
  if (percent >= 60) return 'bg-amber-500'
  return 'bg-emerald-500'
}

function textColor(percent: number): string {
  if (percent >= 85) return 'text-red-600 dark:text-red-400'
  if (percent >= 60) return 'text-amber-600 dark:text-amber-400'
  return 'text-emerald-600 dark:text-emerald-400'
}

export function ResourceUsageCard({ label, percent, detail, displayValue }: ResourceUsageCardProps) {
  const pct = percent ?? null
  const clamped = pct !== null ? Math.min(100, Math.max(0, pct)) : null

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p
          className={`text-2xl font-bold tabular-nums ${
            clamped !== null ? textColor(clamped) : 'text-muted-foreground'
          }`}
        >
          {displayValue ?? (clamped !== null ? `${clamped.toFixed(1)}%` : '—')}
        </p>
      </div>

      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-secondary"
        role="progressbar"
        aria-valuenow={clamped ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        {clamped !== null && (
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${barColor(clamped)}`}
            style={{ width: `${clamped}%` }}
          />
        )}
      </div>

      {detail && (
        <p className="text-xs text-muted-foreground">{detail}</p>
      )}
    </div>
  )
}
