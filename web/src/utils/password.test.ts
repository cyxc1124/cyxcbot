import { describe, expect, it } from 'vitest'
import {
  acceptPasswordInput,
  getLoginPasswordValidationError,
  getPasswordValidationError,
} from './password'

describe('legacy login passwords', () => {
  it.each(['a'.repeat(73), '中'.repeat(25), 'a'.repeat(71) + '中', '😀'.repeat(128)])(
    'accepts a legacy password above 72 UTF-8 bytes while setup rejects it',
    (password) => {
      expect(getLoginPasswordValidationError(password)).toBeNull()
      expect(getPasswordValidationError(password)).toBe('密码过长')
      expect(acceptPasswordInput('', password)).toBe('')
    },
  )

  it.each(['short', 'a'.repeat(129), '😀'.repeat(129)])(
    'keeps the login character length limits',
    (password) => {
      expect(getLoginPasswordValidationError(password)).not.toBeNull()
    },
  )
})
