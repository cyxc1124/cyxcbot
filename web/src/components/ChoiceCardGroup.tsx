import { useId, type ReactNode } from 'react'
import { CheckCircleIcon } from '@heroicons/react/24/solid'

interface Choice<T extends string> {
  value: T
  label: string
  description?: string
  icon?: ReactNode
}

interface ChoiceCardGroupProps<T extends string> {
  label: string
  value: T
  options: readonly Choice<T>[]
  onChange: (value: T) => void
  disabled?: boolean
}

/** Native radios keep arrow-key navigation and form semantics inside the card treatment. */
export function ChoiceCardGroup<T extends string>({
  label, value, options, onChange, disabled = false,
}: ChoiceCardGroupProps<T>) {
  const id = useId()
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="mb-3 text-sm font-medium text-foreground">{label}</legend>
      <div className={`grid gap-3 ${options.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
        {options.map((option) => {
          const selected = value === option.value
          const optionId = `${id}-${option.value}`
          return (
            <label key={option.value} className={`choice-card ${selected ? 'choice-card-selected' : ''} ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
              <input
                type="radio" name={id} value={option.value} checked={selected}
                onChange={() => onChange(option.value)} className="peer sr-only"
                aria-labelledby={`${optionId}-label`}
                aria-describedby={option.description ? `${optionId}-description` : undefined}
              />
              <span className="pointer-events-none absolute inset-0 rounded-xl peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring" />
              {option.icon && <span className={`choice-icon ${selected ? 'text-primary' : 'text-muted-foreground'}`} aria-hidden="true">{option.icon}</span>}
              <span className="min-w-0 flex-1 pr-4">
                <span id={`${optionId}-label`} className="block text-sm font-semibold">{option.label}</span>
                {option.description && <span id={`${optionId}-description`} className="mt-1 block text-xs leading-relaxed text-muted-foreground">{option.description}</span>}
              </span>
              {selected && <CheckCircleIcon className="absolute top-3 right-3 size-4 text-primary" aria-hidden="true" />}
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
