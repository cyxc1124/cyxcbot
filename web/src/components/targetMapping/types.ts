import type { DynamicTarget, LiveTarget } from '../../api/types'

export type TargetType = 'dynamic' | 'live'
export type SubscriptionTarget = DynamicTarget | LiveTarget

export interface TargetFormState {
  id: string
  name: string
  enabled: boolean
  at_all: boolean
  group_ids: string[]
  user_ids: string[]
}

export function emptyForm(isDynamic: boolean): TargetFormState {
  return {
    id: '',
    name: '',
    enabled: true,
    at_all: !isDynamic,
    group_ids: [],
    user_ids: [],
  }
}

export function getTargetId(target: SubscriptionTarget, isDynamic: boolean) {
  return isDynamic ? (target as DynamicTarget).uid : (target as LiveTarget).room_id
}

export function getTargetDisplayName(
  target: SubscriptionTarget,
  isDynamic: boolean,
  targetLabel: string,
) {
  const id = getTargetId(target, isDynamic)
  return target.name || `${targetLabel} ${id}`
}

export function formFromTarget(
  target: SubscriptionTarget,
  isDynamic: boolean,
): TargetFormState {
  return {
    id: getTargetId(target, isDynamic),
    name: target.name ?? '',
    enabled: target.enabled,
    at_all: target.at_all,
    group_ids: [...target.group_ids],
    user_ids: [...target.user_ids],
  }
}
