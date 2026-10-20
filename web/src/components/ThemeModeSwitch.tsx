import { useSyncExternalStore } from 'react'
import { getSavedThemeMode, setThemeMode, subscribeThemeMode, type ThemeMode } from '../lib/theme'
import { Icon } from './Icon'

const modes: { value: ThemeMode; label: string; icon?: 'sun' | 'moon' }[] = [
  { value: 'system', label: '跟随系统' },
  { value: 'light', label: '白色', icon: 'sun' },
  { value: 'dark', label: '黑色', icon: 'moon' },
]

export function ThemeModeSwitch() {
  const mode = useSyncExternalStore(subscribeThemeMode, getSavedThemeMode, () => 'light')
  return (
    <div role="group" aria-label="颜色模式" className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border bg-background p-1">
      {modes.map(({ value, label, icon }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          aria-pressed={mode === value}
          title={label}
          onClick={() => setThemeMode(value)}
          className={`inline-flex min-h-9 min-w-9 items-center justify-center rounded-full px-2.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
            mode === value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
          }`}
        >
          {icon ? <Icon name={icon} /> : label}
        </button>
      ))}
    </div>
  )
}
