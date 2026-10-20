type IconName = 'sun' | 'moon' | 'user' | 'lock-closed' | 'eye' | 'eye-slash' | 'arrow-right'

export function Icon({ name, className = 'size-4' }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" focusable="false">
      <use href={`/ui-icons.svg#${name}`} />
    </svg>
  )
}
