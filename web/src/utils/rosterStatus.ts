import type { OneBotListStatus } from '../api/types'

export function resolveOneBotListStatus(
  status: OneBotListStatus | null | undefined,
  available: boolean,
): OneBotListStatus {
  return status ?? (available ? 'ok' : 'incomplete')
}
