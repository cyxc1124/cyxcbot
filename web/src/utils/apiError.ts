import { ApiClientError } from '../api/client'

const BACKEND_UNAVAILABLE = '后端服务暂不可用，数据暂时无法加载'

export function formatApiError(err: unknown, fallback = '操作失败'): string {
  if (err instanceof ApiClientError) {
    if (err.status === 0 || err.status === 502 || err.status === 503 || err.status === 504) {
      return BACKEND_UNAVAILABLE
    }
    return err.message
  }
  if (err instanceof TypeError) {
    return BACKEND_UNAVAILABLE
  }
  return err instanceof Error ? err.message : fallback
}

export function isBackendUnavailable(err: unknown): boolean {
  if (err instanceof ApiClientError) {
    return err.status === 0 || err.status === 502 || err.status === 503 || err.status === 504
  }
  return err instanceof TypeError
}

export { BACKEND_UNAVAILABLE }
