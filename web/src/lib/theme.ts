export type ThemeMode = 'light' | 'dark' | 'system'
export type ColorTheme = 'default' | 'claude'
export type FontFamily = 'maple' | 'system'

const MODE_KEY = 'cyxcbot_theme'
const COLOR_KEY = 'cyxcbot_color_theme'
const FONT_KEY = 'cyxcbot_font'
const THEME_EVENT = 'cyxcbot:theme-change'
const sessionPreferences = new Map<string, string>()

function readPreference(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return sessionPreferences.get(key) ?? null
  }
}

function savePreference(key: string, value: string): void {
  sessionPreferences.set(key, value)
  try {
    localStorage.setItem(key, value)
  } catch {
    // Storage may be unavailable; keep the current tab usable.
  }
}

export function getSavedThemeMode(): ThemeMode {
  const mode = readPreference(MODE_KEY)
  return mode === 'dark' || mode === 'system' ? mode : 'light'
}

export function getSavedColorTheme(): ColorTheme {
  return readPreference(COLOR_KEY) === 'claude' ? 'claude' : 'default'
}

export function getSavedFontFamily(): FontFamily {
  return readPreference(FONT_KEY) === 'system' ? 'system' : 'maple'
}

export function applyTheme(mode: ThemeMode, color: ColorTheme, font: FontFamily): void {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark' || (
    mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches
  ))
  root.classList.toggle('color-claude', color === 'claude')
  root.classList.toggle('color-default', color === 'default')
  root.classList.toggle('font-maple', font === 'maple')
  root.classList.toggle('font-system', font === 'system')
  savePreference(MODE_KEY, mode)
  savePreference(COLOR_KEY, color)
  savePreference(FONT_KEY, font)
  window.dispatchEvent(new Event(THEME_EVENT))
}

export function setThemeMode(mode: ThemeMode): void {
  applyTheme(mode, getSavedColorTheme(), getSavedFontFamily())
}

export function subscribeThemeMode(listener: () => void): () => void {
  window.addEventListener(THEME_EVENT, listener)
  return () => window.removeEventListener(THEME_EVENT, listener)
}

export function initTheme(): () => void {
  const refresh = () => setThemeMode(getSavedThemeMode())
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const onSystemChange = () => {
    if (getSavedThemeMode() === 'system') refresh()
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || [MODE_KEY, COLOR_KEY, FONT_KEY].includes(event.key)) refresh()
  }
  refresh()
  media.addEventListener('change', onSystemChange)
  window.addEventListener('storage', onStorage)
  return () => {
    media.removeEventListener('change', onSystemChange)
    window.removeEventListener('storage', onStorage)
  }
}
