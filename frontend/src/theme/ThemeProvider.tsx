import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { supabase } from '../auth/client'
import { applyTheme, cacheTheme, DEFAULT_THEME, initialTheme, isTheme, readTheme, themeKey } from './preferences'
import type { ThemeId } from './preferences'

type ThemeContextValue = { theme: ThemeId; selectTheme: (theme: ThemeId) => void; saving: boolean; message: string }
const ThemeContext = createContext<ThemeContextValue>({ theme: DEFAULT_THEME, selectTheme: () => {}, saving: false, message: '' })
export const useTheme = () => useContext(ThemeContext)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  const userId = session?.user.id
  const remoteTheme: unknown = session?.user.user_metadata?.codelens_theme
  const [theme, setTheme] = useState<ThemeId>(initialTheme)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const currentUser = useRef(userId)
  const mounted = useRef(true)
  const running = useRef(false)
  const queued = useRef<{ theme: ThemeId; userId: string } | null>(null)
  const localChoice = useRef<{ theme: ThemeId; userId?: string } | null>(null)
  useLayoutEffect(() => { currentUser.current = userId }, [userId])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useLayoutEffect(() => { applyTheme(theme) }, [theme])

  // Auth metadata is cosmetic only; it is never used for authorization.
  useLayoutEffect(() => {
    if (loading) return
    const cached = readTheme(userId)
    const choice = localChoice.current
    const selected = choice && choice.userId === userId ? choice.theme
      : cached?.pending ? cached.theme
      : isTheme(remoteTheme) ? remoteTheme : cached?.theme || (userId ? DEFAULT_THEME : initialTheme())
    setTheme(selected)
    applyTheme(selected)
    if (!choice || choice.userId !== userId) {
      setMessage(cached?.pending ? 'Saved on this browser. Select the theme again to retry account sync.' : '')
      cacheTheme(selected, userId, cached?.pending)
    }
  }, [userId, remoteTheme, loading])

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key !== themeKey(userId)) return
      const cached = readTheme(userId)
      if (cached) { localChoice.current = { theme: cached.theme, userId }; setTheme(cached.theme) }
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [userId])

  async function flush() {
    if (running.current || !supabase) return
    running.current = true
    setSaving(true)
    try {
      while (queued.current) {
        const request = queued.current
        queued.current = null
        if (currentUser.current !== request.userId) continue
        try {
          const { data } = await supabase.auth.getSession()
          if (data.session?.user.id !== request.userId || currentUser.current !== request.userId) continue
          const { error } = await supabase.auth.updateUser({ data: { codelens_theme: request.theme } })
          if (error) throw error
          if (mounted.current && currentUser.current === request.userId && !queued.current) {
            cacheTheme(request.theme, request.userId)
            setMessage('Saved to your account.')
          }
        } catch {
          if (mounted.current && currentUser.current === request.userId && !queued.current) {
            setMessage('Applied on this browser. Account sync failed; select the theme again to retry.')
          }
        }
      }
    } finally {
      running.current = false
      if (mounted.current) setSaving(false)
    }
  }
  function selectTheme(next: ThemeId) {
    if (!isTheme(next)) return
    localChoice.current = { theme: next, userId }
    setTheme(next)
    applyTheme(next)
    const persisted = cacheTheme(next, userId, Boolean(userId))
    // The public landing page keeps this device's appearance after sign-out.
    if (userId) cacheTheme(next)
    setMessage(persisted ? 'Saved on this browser.' : 'Applied for this visit. Browser storage is unavailable.')
    if (userId && supabase) {
      queued.current = { theme: next, userId }
      void flush()
    }
  }
  return <ThemeContext.Provider value={{ theme, selectTheme, saving, message }}>{children}</ThemeContext.Provider>
}
