interface SubPageTabsProps<T extends string> {
  tabs: Record<T, string>
  value: T
  onChange: (value: T) => void
}

export function SubPageTabs<T extends string>({ tabs, value, onChange }: SubPageTabsProps<T>) {
  return (
    <div
      className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-700"
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
                ? 'relative -mb-px rounded-t-lg border border-b-0 border-brand-300 bg-brand-50 px-4 py-2.5 text-sm font-semibold text-brand-800 shadow-sm dark:border-brand-700 dark:bg-brand-950/80 dark:text-brand-200'
                : 'rounded-t-lg px-4 py-2.5 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800/60 dark:hover:text-slate-200'
            }
          >
            {tabs[key]}
          </button>
        )
      })}
    </div>
  )
}
