/** restrict + enabled_ids 白名单策略的通用计算（群消息、好友消息、状态查询共用） */

export function isItemEnabled(
  itemId: string,
  restrict: boolean,
  enabledIds: string[],
): boolean {
  if (!restrict) return true
  return enabledIds.includes(itemId)
}

export function computePolicyAfterToggle(
  itemId: string,
  enabled: boolean,
  allIds: string[],
  restrict: boolean,
  enabledIds: string[],
): { restrict: boolean; enabled_ids: string[] } {
  if (enabled) {
    if (!restrict) {
      return { restrict: false, enabled_ids: [] }
    }
    const nextEnabled = [...new Set([...enabledIds, itemId])]
    if (nextEnabled.length >= allIds.length) {
      return { restrict: false, enabled_ids: [] }
    }
    return { restrict: true, enabled_ids: nextEnabled }
  }

  if (!restrict) {
    return {
      restrict: true,
      enabled_ids: allIds.filter((id) => id !== itemId),
    }
  }
  return {
    restrict: true,
    enabled_ids: enabledIds.filter((id) => id !== itemId),
  }
}

export function computeToggleAllPolicy(enabled: boolean): {
  restrict: boolean
  enabled_ids: string[]
} {
  return enabled
    ? { restrict: false, enabled_ids: [] }
    : { restrict: true, enabled_ids: [] }
}
