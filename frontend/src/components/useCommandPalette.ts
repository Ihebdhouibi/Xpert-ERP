import { createElement, useEffect, useState } from 'react'
import CommandPalette from './CommandPalette'

export function useCommandPalette() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(v => !v)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const palette = createElement(CommandPalette, { open, onClose: () => setOpen(false) })

  return { open, setOpen, palette }
}
