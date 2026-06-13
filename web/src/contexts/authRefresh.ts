import { ApiClientError } from '../api/client'

export function getInitErrorOnRefreshFailure(
  setupKnown: boolean,
  err: unknown,
): string | null {
  if (setupKnown) return null
  if (err instanceof ApiClientError) return err.message
  return '无法获取初始化状态，请重试'
}
