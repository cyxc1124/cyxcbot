interface SubPageTabsProps<T extends string> {
  tabs: Record<T, string>
  value: T
  onChange: (value: T) => void
}

export function SubPageTabs<T extends string>({ tabs, value, onChange }: SubPageTabsProps<T>) {
  return (
    <div
      className="flex flex-wrap gap-1 border-b border-border"
      role="tablist"
    >
      {(Object.keys(tabs) as T[]).map((key) => {
        const active = value === key
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(key)}
            className={
              active
                ? 'relative -mb-px rounded-t-lg border border-b-0 border-primary bg-sidebar-accent px-4 py-2.5 text-sm font-semibold text-sidebar-primary shadow-sm'
                : 'rounded-t-lg px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground'
            }
          >
            {tabs[key]}
          </button>
        )
      })}
    </div>
  )
}
