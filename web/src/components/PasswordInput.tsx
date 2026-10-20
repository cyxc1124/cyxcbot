import { useState, type InputHTMLAttributes } from 'react'
import { Icon } from './Icon'

export function PasswordInput({
  className = '',
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-muted-foreground"><Icon name="lock-closed" /></span>
      <input {...props} type={visible ? 'text' : 'password'} className={`input h-14 pl-10 pr-12 text-base ${className}`} />
      <button
        type="button"
        aria-label={visible ? '隐藏密码' : '显示密码'}
        aria-pressed={visible}
        aria-controls={props.id}
        disabled={props.disabled}
        onClick={() => setVisible((value) => !value)}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-xl text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
      >
        <Icon name={visible ? 'eye-slash' : 'eye'} />
      </button>
    </div>
  )
}
