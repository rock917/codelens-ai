export const themes = [
  { id: 'midnight-violet', name: 'Midnight Violet', description: 'The original. Deep purple, softly illuminated.', short: 'Violet' },
  { id: 'cyber-cyan', name: 'Cyber Cyan', description: 'Electric cyan on a cool midnight canvas.', short: 'Cyan' },
  { id: 'emerald-matrix', name: 'Emerald Matrix', description: 'Forest shadows with fresh emerald accents.', short: 'Emerald' },
  { id: 'arctic-light', name: 'Arctic Light', description: 'A bright workspace with crisp blue details.', short: 'Light' },
] as const
export type ThemeId = typeof themes[number]['id']
export const DEFAULT_THEME: ThemeId = 'midnight-violet'
export const LAST_THEME_KEY = 'codelens.theme.v1.last'
export const themeKey = (userId?: string) => `codelens.theme.v1.${userId || 'guest'}`
export function isTheme(value: unknown): value is ThemeId {
  return themes.some(theme => theme.id === value)
}
export type CachedTheme = { theme: ThemeId; pending: boolean }
export function readTheme(userId?: string): CachedTheme | null {
  try {
    const value = JSON.parse(localStorage.getItem(themeKey(userId)) || 'null')
    return value && isTheme(value.theme) ? { theme: value.theme, pending: value.pending === true } : null
  } catch { return null }
}
export function cacheTheme(theme: ThemeId, userId?: string, pending = false): boolean {
  try {
    localStorage.setItem(themeKey(userId), JSON.stringify({ theme, pending }))
    localStorage.setItem(LAST_THEME_KEY, theme)
    return true
  } catch { return false }
}
export function initialTheme(): ThemeId {
  try {
    const value = localStorage.getItem(LAST_THEME_KEY)
    return isTheme(value) ? value : DEFAULT_THEME
  } catch { return DEFAULT_THEME }
}
export function applyTheme(theme: ThemeId) {
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme === 'arctic-light' ? 'light' : 'dark'
}
