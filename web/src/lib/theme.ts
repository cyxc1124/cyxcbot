export type ThemeMode = 'light' | 'dark'
export type ColorTheme = 'default' | 'claude'
export type FontFamily = 'maple' | 'system'

const MODE_KEY = 'cyxcbot_theme'
const COLOR_KEY = 'cyxcbot_color_theme'
const FONT_KEY = 'cyxcbot_font'

export function getSavedThemeMode(): ThemeMode {
  return localStorage.getItem(MODE_KEY) === 'dark' ? 'dark' : 'light'
}

export function getSavedColorTheme(): ColorTheme {
  return localStorage.getItem(COLOR_KEY) === 'claude' ? 'claude' : 'default'
}

export function getSavedFontFamily(): FontFamily {
  return localStorage.getItem(FONT_KEY) === 'system' ? 'system' : 'maple'
}

export function applyTheme(mode: ThemeMode, color: ColorTheme, font: FontFamily): void {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
  root.classList.toggle('color-claude', color === 'claude')
  root.classList.toggle('color-default', color === 'default')
  root.classList.toggle('font-maple', font === 'maple')
  root.classList.toggle('font-system', font === 'system')
  localStorage.setItem(MODE_KEY, mode)
  localStorage.setItem(COLOR_KEY, color)
  localStorage.setItem(FONT_KEY, font)
}

export function initTheme(): void {
  applyTheme(getSavedThemeMode(), getSavedColorTheme(), getSavedFontFamily())
}
