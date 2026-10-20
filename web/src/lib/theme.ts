export type ThemeMode = 'light' | 'dark' | 'system'

const MODE_KEY = 'cyxcbot_theme'
const THEME_EVENT = 'cyxcbot:theme-change'
let sessionMode: ThemeMode = 'light'

export function getSavedThemeMode(): ThemeMode {
  try {
    const mode = localStorage.getItem(MODE_KEY)
    return mode === 'dark' || mode === 'system' ? mode : 'light'
  } catch {
    return sessionMode
  }
}

export function setThemeMode(mode: ThemeMode): void {
  document.documentElement.classList.toggle('dark', mode === 'dark' || (
    mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches
  ))
  sessionMode = mode
  try {
    localStorage.setItem(MODE_KEY, mode)
  } catch {
    // Storage may be unavailable; keep the current tab usable.
  }
  window.dispatchEvent(new Event(THEME_EVENT))
}

export function subscribeThemeMode(listener: () => void): () => void {
  window.addEventListener(THEME_EVENT, listener)
  return () => window.removeEventListener(THEME_EVENT, listener)
}

export function initTheme(): () => void {
  document.documentElement.classList.remove('color-claude', 'color-default', 'font-maple', 'font-system')
  try {
    localStorage.removeItem('cyxcbot_color_theme')
    localStorage.removeItem('cyxcbot_font')
  } catch {
    // Removed preferences must not block startup when storage is unavailable.
  }
  const refresh = () => setThemeMode(getSavedThemeMode())
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const onSystemChange = () => {
    if (getSavedThemeMode() === 'system') refresh()
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === MODE_KEY) refresh()
  }
  refresh()
  media.addEventListener('change', onSystemChange)
  window.addEventListener('storage', onStorage)
  return () => {
    media.removeEventListener('change', onSystemChange)
    window.removeEventListener('storage', onStorage)
  }
}
