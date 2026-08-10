interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

/** iOS-style switch: systemGreen when on, system gray track when off. */
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
      className={`relative inline-flex h-[31px] w-[51px] shrink-0 items-center rounded-full transition-colors duration-200 ease-out focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#34C759]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
        checked ? 'bg-[#34C759]' : 'bg-[#E9E9EB] dark:bg-[#39393D]'
      } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
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
