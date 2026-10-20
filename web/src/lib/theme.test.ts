import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { applyTheme, getSavedThemeMode, initTheme, setThemeMode, subscribeThemeMode } from './theme'

let store: Map<string, string>
let classes: Set<string>
let media: EventTarget & { matches: boolean }
let cleanup: (() => void) | undefined

beforeEach(() => {
  store = new Map()
  classes = new Set()
  media = Object.assign(new EventTarget(), { matches: false })
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => store.set(key, value)),
  })
  vi.stubGlobal('window', Object.assign(new EventTarget(), { matchMedia: vi.fn(() => media) }))
  vi.stubGlobal('document', {
    documentElement: {
      classList: { toggle: (key: string, on: boolean) => on ? classes.add(key) : classes.delete(key) },
    },
  })
})

afterEach(() => {
  cleanup?.()
  cleanup = undefined
  vi.unstubAllGlobals()
})

describe('theme preferences', () => {
  it('keeps existing light/dark choices and the default light appearance', () => {
    expect(getSavedThemeMode()).toBe('light')
    store.set('cyxcbot_theme', 'dark')
    cleanup = initTheme()
    expect(classes.has('dark')).toBe(true)
    store.set('cyxcbot_theme', 'unknown')
    expect(getSavedThemeMode()).toBe('light')
  })

  it('follows live system changes without replacing the saved system preference', () => {
    store.set('cyxcbot_theme', 'system')
    media.matches = true
    cleanup = initTheme()
    expect(classes.has('dark')).toBe(true)
    media.matches = false
    media.dispatchEvent(new Event('change'))
    expect(classes.has('dark')).toBe(false)
    expect(store.get('cyxcbot_theme')).toBe('system')
  })

  it('ignores system changes when a mode is selected explicitly', () => {
    store.set('cyxcbot_theme', 'dark')
    cleanup = initTheme()
    media.dispatchEvent(new Event('change'))
    expect(classes.has('dark')).toBe(true)
  })

  it('retains the color scheme and font when changing mode and notifies controls', () => {
    applyTheme('light', 'claude', 'system')
    const listener = vi.fn()
    const unsubscribe = subscribeThemeMode(listener)
    setThemeMode('dark')
    expect(classes).toEqual(new Set(['dark', 'color-claude', 'font-system']))
    expect(store.get('cyxcbot_color_theme')).toBe('claude')
    expect(store.get('cyxcbot_font')).toBe('system')
    expect(listener).toHaveBeenCalledOnce()
    unsubscribe()
    setThemeMode('light')
    expect(listener).toHaveBeenCalledOnce()
  })

  it('refreshes from another tab without resetting its color and font', () => {
    cleanup = initTheme()
    store.set('cyxcbot_theme', 'dark')
    store.set('cyxcbot_color_theme', 'claude')
    store.set('cyxcbot_font', 'system')
    window.dispatchEvent(Object.assign(new Event('storage'), { key: 'cyxcbot_theme' }))
    expect(classes).toEqual(new Set(['dark', 'color-claude', 'font-system']))
  })

  it('keeps mode switching usable when browser storage is blocked', () => {
    vi.mocked(localStorage.getItem).mockImplementation(() => { throw new Error('blocked') })
    vi.mocked(localStorage.setItem).mockImplementation(() => { throw new Error('blocked') })
    applyTheme('dark', 'claude', 'system')
    setThemeMode('light')
    expect(getSavedThemeMode()).toBe('light')
    expect(classes).toEqual(new Set(['color-claude', 'font-system']))
  })

  it('removes system and storage listeners when disposed', () => {
    store.set('cyxcbot_theme', 'system')
    const dispose = initTheme()
    dispose()
    media.matches = true
    media.dispatchEvent(new Event('change'))
    store.set('cyxcbot_theme', 'dark')
    window.dispatchEvent(Object.assign(new Event('storage'), { key: null }))
    expect(classes.has('dark')).toBe(false)
  })
})
