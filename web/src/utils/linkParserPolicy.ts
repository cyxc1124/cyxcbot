/** 链接解析策略开关的通用计算 */

export interface LinkParserPolicyFlags {
  video_enabled: boolean
  live_enabled: boolean
}

export function buildPolicyPayload(
  row: LinkParserPolicyFlags,
  patch: Partial<LinkParserPolicyFlags>,
): LinkParserPolicyFlags & { customized: boolean } {
  const next = { ...row, ...patch }
  const payload = {
    video_enabled: Boolean(next.video_enabled),
    live_enabled: Boolean(next.live_enabled),
  }
  return {
    ...payload,
    customized: payload.video_enabled || payload.live_enabled,
  }
}

export function isAllPoliciesEnabled(items: LinkParserPolicyFlags[]): boolean {
  return items.length > 0 && items.every((item) => item.video_enabled && item.live_enabled)
}

export function isNoPoliciesEnabled(items: LinkParserPolicyFlags[]): boolean {
  return items.length > 0 && items.every((item) => !item.video_enabled && !item.live_enabled)
}

export function buildToggleAllPayload(enabled: boolean): LinkParserPolicyFlags {
  return { video_enabled: enabled, live_enabled: enabled }
}
