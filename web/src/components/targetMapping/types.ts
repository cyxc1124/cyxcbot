import type { DynamicTarget, LiveTarget, XTarget } from '../../api/types'

export type TargetType = 'dynamic' | 'live' | 'x'
export type SubscriptionTarget = DynamicTarget | LiveTarget | XTarget

export interface TargetFormState {
  id: string
  name: string
  enabled: boolean
  at_all: boolean
  group_ids: string[]
  user_ids: string[]
}

export function emptyForm(type: TargetType): TargetFormState {
  return {
    id: '',
    name: '',
    enabled: true,
    at_all: type === 'live',
    group_ids: [],
    user_ids: [],
  }
}

export function getTargetId(target: SubscriptionTarget, type: TargetType) {
  if (type === 'dynamic') return (target as DynamicTarget).uid
  if (type === 'x') return (target as XTarget).username
  return (target as LiveTarget).room_id
}

export function getTargetDisplayName(
  target: SubscriptionTarget,
  type: TargetType,
  targetLabel: string,
) {
  const id = getTargetId(target, type)
  return target.name || `${targetLabel} ${id}`
}

export function formFromTarget(
  target: SubscriptionTarget,
  type: TargetType,
): TargetFormState {
  return {
    id: getTargetId(target, type),
    name: target.name ?? '',
    enabled: target.enabled,
    at_all: target.at_all,
    group_ids: [...target.group_ids],
    user_ids: [...target.user_ids],
  }
}

export function targetTypeMeta(type: TargetType) {
  if (type === 'dynamic') {
    return {
      idLabel: 'UP 主 UID',
      targetLabel: 'UP 主',
      nameSource: 'B 站',
    }
  }
  if (type === 'x') {
    return {
      idLabel: 'X 用户名',
      targetLabel: 'X 博主',
      nameSource: 'X',
    }
  }
  return {
    idLabel: '直播间房间号',
    targetLabel: '直播间',
    nameSource: 'B 站',
  }
}
