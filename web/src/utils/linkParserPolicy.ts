/** 链接解析策略开关的通用计算 */

export interface LinkParserPolicyFlags {
  video_enabled: boolean
  live_enabled: boolean
  dynamic_enabled: boolean
  send_video_enabled: boolean
}

export function buildPolicyPayload(
  row: LinkParserPolicyFlags,
  patch: Partial<LinkParserPolicyFlags>,
): LinkParserPolicyFlags & { customized: boolean } {
  const next = { ...row, ...patch }
  const payload = {
    video_enabled: Boolean(next.video_enabled),
    live_enabled: Boolean(next.live_enabled),
    dynamic_enabled: Boolean(next.dynamic_enabled),
    send_video_enabled: Boolean(next.send_video_enabled),
  }
  // 发送视频依赖视频链接解析；关闭视频链接时一并关掉发送视频
  if (!payload.video_enabled) {
    payload.send_video_enabled = false
  }
  return {
    ...payload,
    customized:
      payload.video_enabled ||
      payload.live_enabled ||
      payload.dynamic_enabled ||
      payload.send_video_enabled,
  }
}

/** 「全部启用」是否已满足：只看解析三项，不含发送视频 */
export function isAllPoliciesEnabled(items: LinkParserPolicyFlags[]): boolean {
  return (
    items.length > 0 &&
    items.every(
      (item) => item.video_enabled && item.live_enabled && item.dynamic_enabled,
    )
  )
}

export function isNoPoliciesEnabled(items: LinkParserPolicyFlags[]): boolean {
  return (
    items.length > 0 &&
    items.every(
      (item) =>
        !item.video_enabled &&
        !item.live_enabled &&
        !item.dynamic_enabled &&
        !item.send_video_enabled,
    )
  )
}

/** 批量开关：只动视频/直播/动态解析；发送视频需单独开，全关时一并关掉 */
export function buildToggleAllPayload(enabled: boolean): LinkParserPolicyFlags {
  return {
    video_enabled: enabled,
    live_enabled: enabled,
    dynamic_enabled: enabled,
    send_video_enabled: false,
  }
}

export function isAllSendVideoEnabled(items: LinkParserPolicyFlags[]): boolean {
  return items.length > 0 && items.every((item) => item.send_video_enabled)
}

export function isNoSendVideoEnabled(items: LinkParserPolicyFlags[]): boolean {
  return items.length > 0 && items.every((item) => !item.send_video_enabled)
}

/** 批量开关发送视频；开启时一并打开视频链接 */
export function buildToggleAllSendVideoPayload(
  row: LinkParserPolicyFlags,
  enabled: boolean,
): LinkParserPolicyFlags {
  if (!enabled) {
    return {
      video_enabled: row.video_enabled,
      live_enabled: row.live_enabled,
      dynamic_enabled: row.dynamic_enabled,
      send_video_enabled: false,
    }
  }
  return {
    video_enabled: true,
    live_enabled: row.live_enabled,
    dynamic_enabled: row.dynamic_enabled,
    send_video_enabled: true,
  }
}
