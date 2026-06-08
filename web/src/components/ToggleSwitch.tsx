interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

export function ToggleSwitch({ checked, onChange, disabled }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation()
        if (!disabled) onChange(!checked)
      }}
      className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900 ${
        checked ? 'bg-brand-600' : 'bg-slate-300 dark:bg-slate-600'
      } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
    >
      <span
        aria-hidden
        className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform dark:bg-slate-100 ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}
