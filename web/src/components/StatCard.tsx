import type { ReactNode } from 'react'

type SubtitleItem = string | ReactNode

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: SubtitleItem | SubtitleItem[]
}

export function StatCard({ title, value, subtitle }: StatCardProps) {
  const subtitles = subtitle ? (Array.isArray(subtitle) ? subtitle : [subtitle]) : []

  return (
    <div className="card">
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <p className="mt-2 text-2xl font-bold text-foreground">{value}</p>
      {subtitles.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {subtitles.map((line, index) => (
            <p key={typeof line === 'string' ? line : index} className="text-xs text-muted-foreground">
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
