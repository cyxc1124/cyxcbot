interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

export function ToggleSwitch({ checked, onChange, disabled }: ToggleSwitchProps) {
  return (
    <label
      className={`relative inline-flex shrink-0 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
    >
      <input
        type="checkbox"
        className="peer sr-only"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="h-6 w-11 rounded-full bg-slate-200 transition-colors peer-checked:bg-brand-600 peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 peer-focus-visible:ring-offset-2 dark:bg-slate-700 dark:peer-focus-visible:ring-offset-slate-900" />
      <span
        className="pointer-events-none absolute left-0.5 top-0.5 h-5 w-5 rounded-full border border-slate-300 bg-white shadow-sm transition-transform peer-checked:translate-x-5 dark:border-slate-600"
        aria-hidden
      />
    </label>
  )
}
