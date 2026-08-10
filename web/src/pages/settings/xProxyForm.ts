export type XProxyDraft = {
  enabled: boolean
  host: string
}

/** Returns an error message if the draft cannot be saved; otherwise null. */
export function validateXProxyDraft(proxy: XProxyDraft): string | null {
  if (proxy.enabled && !proxy.host.trim()) {
    return '启用代理时请填写主机地址'
  }
  // disabled + host is intentional: keep address for later while direct-connecting
  return null
}
