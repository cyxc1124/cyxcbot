/** bcrypt 仅使用前 72 个 UTF-8 字节，与后端 admin.auth.password 保持一致。 */
export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_UTF8_BYTES = 72

export function passwordUtf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length
}

/** 拒绝会导致 UTF-8 编码超过上限的输入。 */
export function acceptPasswordInput(current: string, next: string): string {
  if (passwordUtf8ByteLength(next) <= MAX_PASSWORD_UTF8_BYTES) {
    return next
  }
  return current
}

export function getPasswordValidationError(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return '密码至少需要 8 个字符'
  }
  if (passwordUtf8ByteLength(password) > MAX_PASSWORD_UTF8_BYTES) {
    return '密码过长'
  }
  return null
}
