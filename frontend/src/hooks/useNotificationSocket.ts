import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../contexts/AuthContext'
import type { AppNotification, InboxResponse } from '../lib/notificationApi'

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''
const MAX_RECONNECT_DELAY_MS = 30_000

function buildSocketUrl(token: string): string {
  if (BASE_URL) {
    // e.g. https://api.example.com -> wss://api.example.com
    return `${BASE_URL.replace(/^http/, 'ws')}/api/v1/notifications/ws?token=${encodeURIComponent(token)}`
  }
  // No configured API base — same origin as the page (dev proxy setups).
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/notifications/ws?token=${encodeURIComponent(token)}`
}

/**
 * Real-time push for the notification bell — complements (does not replace)
 * TopBar.tsx's/NotificationsPage.tsx's REST polling, which stays as a
 * long-interval fallback in case a socket never connects or silently drops
 * (e.g. laptop sleep). Mount once near the app root (AppShell) so it isn't
 * torn down on every route change.
 */
export function useNotificationSocket(): void {
  const { isAuthenticated } = useAuth()
  const queryClient = useQueryClient()
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelayRef = useRef(1000)
  const stoppedRef = useRef(false)

  useEffect(() => {
    if (!isAuthenticated) return

    stoppedRef.current = false

    const connect = () => {
      if (stoppedRef.current) return
      const token = localStorage.getItem('access_token')
      if (!token) return

      const socket = new WebSocket(buildSocketUrl(token))
      socketRef.current = socket

      socket.onopen = () => {
        reconnectDelayRef.current = 1000
      }

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const notif = JSON.parse(event.data) as AppNotification
          // Merge directly into the bell's cache rather than invalidating —
          // avoids a race with the REST write this push originated from
          // (see backend/app/modules/notification/inbox_router.py).
          queryClient.setQueryData<InboxResponse>(['notifications', 'inbox'], prev => {
            if (!prev) return prev
            if (prev.items.some(n => n.id === notif.id)) return prev
            return {
              items: [notif, ...prev.items].slice(0, 10),
              unread_count: prev.unread_count + (notif.read_at ? 0 : 1),
            }
          })
          // The full history page (if open) just refetches — it's a rarer
          // view and paginated, not worth a similar manual merge.
          queryClient.invalidateQueries({ queryKey: ['notifications', 'history'] })
        } catch {
          // Ignore malformed frames rather than crash the socket handler.
        }
      }

      socket.onclose = () => {
        if (stoppedRef.current) return
        reconnectTimerRef.current = setTimeout(connect, reconnectDelayRef.current)
        reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, MAX_RECONNECT_DELAY_MS)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      stoppedRef.current = true
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [isAuthenticated, queryClient])
}
