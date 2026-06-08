interface ResourceUsageCardProps {
  label: string
  percent: number | null | undefined
  detail?: string
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

export function ResourceUsageCard({ label, percent, detail }: ResourceUsageCardProps) {
  const value = percent ?? null
  const clamped = value !== null ? Math.min(100, Math.max(0, value)) : null

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
        <p
          className={`text-2xl font-bold tabular-nums ${
            clamped !== null ? textColor(clamped) : 'text-slate-400'
          }`}
        >
          {clamped !== null ? `${clamped.toFixed(1)}%` : '—'}
        </p>
      </div>

      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
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
        <p className="text-xs text-slate-500 dark:text-slate-400">{detail}</p>
      )}
    </div>
  )
}
