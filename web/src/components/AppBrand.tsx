import type { ReactNode } from 'react'

export function AppBrand({
  compact = false,
  version = import.meta.env.VITE_BUILD_VERSION || 'dev',
  subtitle,
}: { compact?: boolean; version?: ReactNode; subtitle?: string }) {
  return (
    <div className={compact ? 'flex min-w-0 items-center gap-3' : 'flex flex-col items-center text-center'}>
      <img
        src="/brand-avatar.png"
        alt="机器草头像"
        width={72}
        height={72}
        className={`${compact ? 'size-10' : 'mb-4 size-18'} shrink-0 rounded-2xl border border-border object-contain`}
      />
      <div className="min-w-0">
        <div className={`flex flex-wrap items-center gap-2 ${compact ? '' : 'justify-center'}`}>
          <span className={`${compact ? 'text-base' : 'text-3xl'} font-bold tracking-tight text-foreground`}>机器草</span>
          <span className={`${compact ? 'text-[10px]' : 'text-xs'} max-w-full break-all rounded-lg border border-border bg-background px-2 py-1 font-mono font-normal leading-tight text-muted-foreground`}>{version}</span>
        </div>
        {subtitle && <p className={`mt-2 ${compact ? 'text-sm' : 'text-base'} text-muted-foreground`}>{subtitle}</p>}
      </div>
    </div>
  )
}

export function AppFooter() {
  return <footer className="px-4 py-6 text-center text-xs text-muted-foreground">© 2026 cyxcbot. All rights reserved.</footer>
}
