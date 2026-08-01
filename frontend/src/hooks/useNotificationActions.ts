import { useState, type MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { inboxApi } from '../lib/notificationApi'
import { useToast } from '../contexts/ToastContext'

/** Shared click/read/email-send behavior for the bell dropdown and the full notifications page. */
export function useNotificationActions() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [sendingEmailId, setSendingEmailId] = useState<number | null>(null)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['notifications'] })
  }

  const openNotification = async (n: { id: number; link: string | null }) => {
    try {
      await inboxApi.markRead(n.id)
    } catch {
      /* non-blocking */
    }
    invalidate()
    if (n.link) navigate(n.link)
  }

  const markAll = async () => {
    await inboxApi.markAllRead()
    invalidate()
  }

  const sendNotificationEmail = async (
    e: MouseEvent,
    notificationId: number,
    recipient: 'client' | 'admin',
  ) => {
    e.stopPropagation()
    setSendingEmailId(notificationId)
    try {
      await inboxApi.sendEmail(notificationId, recipient)
      success(recipient === 'client' ? 'Email envoyé au client' : "Email envoyé à l'admin")
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : "Impossible d'envoyer l'email.")
    } finally {
      setSendingEmailId(null)
    }
  }

  return { openNotification, markAll, sendNotificationEmail, sendingEmailId }
}
