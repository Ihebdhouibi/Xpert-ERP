import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { getTheme, type ThemeMode, type ThemePreference } from '../theme'
import { useLocalStoragePref } from '../hooks/useLocalStoragePref'

interface ThemeModeContextValue {
  /** What the user picked — may be 'system'. */
  preference: ThemePreference
  /** What's actually rendered right now — 'system' already resolved to light/dark. */
  resolvedMode: ThemeMode
  setPreference: (pref: ThemePreference) => void
  /** Convenience for a simple light/dark toggle button — cycles light → dark → system. */
  cyclePreference: () => void
}

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null)

function systemPrefersDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useLocalStoragePref<ThemePreference>('theme_mode', 'system')
  const [systemIsDark, setSystemIsDark] = useState(systemPrefersDark)

  // Track the OS setting live so 'system' preference updates without a reload.
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => setSystemIsDark(e.matches)
    media.addEventListener('change', handler)
    return () => media.removeEventListener('change', handler)
  }, [])

  const resolvedMode: ThemeMode = preference === 'system' ? (systemIsDark ? 'dark' : 'light') : preference

  const cyclePreference = useCallback(() => {
    setPreference(prev => (prev === 'light' ? 'dark' : prev === 'dark' ? 'system' : 'light'))
  }, [setPreference])

  const theme = useMemo(() => getTheme(resolvedMode), [resolvedMode])

  const value = useMemo(
    () => ({ preference, resolvedMode, setPreference, cyclePreference }),
    [preference, resolvedMode, setPreference, cyclePreference]
  )

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext)
  if (!ctx) throw new Error('useThemeMode must be used within a ThemeModeProvider')
  return ctx
}
