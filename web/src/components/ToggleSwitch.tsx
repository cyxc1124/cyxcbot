interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  busy?: boolean
  ariaLabelledBy?: string
}

/** Shared switch uses the console primary color and exposes its checked state. */
export function ToggleSwitch({ checked, onChange, disabled, busy, ariaLabelledBy }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-busy={busy || undefined}
      aria-labelledby={ariaLabelledBy}
      disabled={disabled || busy}
      onClick={(event) => {
        event.stopPropagation()
        if (!disabled && !busy) onChange(!checked)
      }}
      className={`relative inline-flex h-[31px] w-[51px] shrink-0 items-center rounded-full transition-colors duration-200 ease-out focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
        checked ? 'bg-primary' : 'bg-[#E9E9EB] dark:bg-[#39393D]'
      } ${disabled ? 'cursor-not-allowed opacity-50' : busy ? 'cursor-wait' : 'cursor-pointer'}`}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute top-1/2 left-[2px] size-[27px] -translate-y-1/2 rounded-full bg-white transition-transform duration-200 ease-out ${
          checked ? 'translate-x-[20px]' : 'translate-x-0'
        }`}
        style={{
          boxShadow:
            '0 3px 8px rgba(0, 0, 0, 0.15), 0 3px 1px rgba(0, 0, 0, 0.06), inset 0 0 0 0.5px rgba(0, 0, 0, 0.04)',
        }}
      />
    </button>
  )
}
