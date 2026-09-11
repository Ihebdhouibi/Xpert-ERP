import { useCallback, useState } from 'react'

/**
 * Persist a small piece of UI preference (sidebar collapse state, favorites,
 * saved filter views, theme mode, …) to localStorage, with the same API shape
 * as useState. First reusable instance of this pattern in the codebase —
 * every other localStorage usage in the app is auth-token specific
 * (AuthContext.tsx, apiClient.ts). Reads/writes are wrapped in try/catch so a
 * private window, blocked storage, or a quota error never breaks the UI —
 * it just falls back to `defaultValue` for that session.
 */
export function useLocalStoragePref<T>(
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw !== null ? (JSON.parse(raw) as T) : defaultValue
    } catch {
      return defaultValue
    }
  })

  const setPref = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue(prev => {
        const resolved = typeof next === 'function' ? (next as (prev: T) => T)(prev) : next
        try {
          localStorage.setItem(key, JSON.stringify(resolved))
        } catch {
          // ignore write errors — the value still updates for this session
        }
        return resolved
      })
    },
    [key]
  )

  return [value, setPref]
}
