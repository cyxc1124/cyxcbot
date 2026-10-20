import { describe, expect, it, vi } from 'vitest'
import { ToggleSwitch } from './ToggleSwitch'

describe('ToggleSwitch save lock', () => {
  it.each([
    { disabled: false, busy: false },
    { disabled: false, busy: true },
    { disabled: true, busy: false },
    { disabled: true, busy: true },
  ])('preserves readonly appearance and blocks changes with disabled=$disabled, busy=$busy', ({ disabled, busy }) => {
    const onChange = vi.fn()
    const stopPropagation = vi.fn()
    const button = ToggleSwitch({ checked: false, onChange, disabled, busy })

    expect(button.props.disabled).toBe(disabled || busy)
    expect(button.props['aria-busy']).toBe(busy || undefined)
    expect(button.props.className.includes('opacity-50')).toBe(disabled)

    button.props.onClick({ stopPropagation })
    expect(stopPropagation).toHaveBeenCalledOnce()
    if (disabled || busy) {
      expect(onChange).not.toHaveBeenCalled()
    } else {
      expect(onChange).toHaveBeenCalledExactlyOnceWith(true)
    }
  })
})
