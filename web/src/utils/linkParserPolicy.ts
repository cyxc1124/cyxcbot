export interface LinkParserToggleState {
  enabled: boolean
  video_enabled: boolean
  live_enabled: boolean
}

/** Apply master/sub switch coupling for link parser policy toggles. */
export function applyLinkParserToggle(
  current: LinkParserToggleState,
  patch: Partial<LinkParserToggleState>,
): LinkParserToggleState {
  const next: LinkParserToggleState = { ...current, ...patch }

  if (patch.enabled === false) {
    next.video_enabled = false
    next.live_enabled = false
    return next
  }

  if (patch.enabled === true && !next.video_enabled && !next.live_enabled) {
    next.video_enabled = true
    next.live_enabled = true
  }

  return next
}
