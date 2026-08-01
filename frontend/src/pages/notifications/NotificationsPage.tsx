import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import MailRoundedIcon from '@mui/icons-material/MailRounded'
import NotificationsNoneRoundedIcon from '@mui/icons-material/NotificationsNoneRounded'
import { inboxApi, notificationSupportsEmail } from '../../lib/notificationApi'
import { useNotificationActions } from '../../hooks/useNotificationActions'
import { PageHeader } from '../../components/ui/PageHeader'

const PAGE_SIZE = 20

export function NotificationsPage() {
  const [page, setPage] = useState(1)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const { openNotification, markAll, sendNotificationEmail, sendingEmailId } = useNotificationActions()

  const { data, isLoading } = useQuery({
    queryKey: ['notifications', 'history', page, unreadOnly],
    queryFn: () => inboxApi.history({ page, page_size: PAGE_SIZE, unread_only: unreadOnly }),
    refetchInterval: 30_000,
  })

  const items = data?.items ?? []
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <Box>
      <PageHeader
        title="Notifications"
        actions={
          <>
            <Button
              size="small"
              variant={unreadOnly ? 'contained' : 'outlined'}
              onClick={() => { setUnreadOnly(u => !u); setPage(1) }}
              sx={{ textTransform: 'none', borderRadius: 2 }}
            >
              Non lues uniquement
            </Button>
            {(data?.unread_count ?? 0) > 0 && (
              <Button size="small" onClick={markAll} sx={{ textTransform: 'none' }}>
                Tout marquer comme lu
              </Button>
            )}
          </>
        }
      />

      <Paper sx={{ borderRadius: 2, overflow: 'hidden' }}>
        {isLoading ? (
          <Stack alignItems="center" py={6}>
            <CircularProgress />
          </Stack>
        ) : items.length === 0 ? (
          <Stack alignItems="center" py={6} spacing={1}>
            <NotificationsNoneRoundedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
            <Typography color="text.secondary">Aucune notification.</Typography>
          </Stack>
        ) : (
          items.map((n, i) => (
            <Box key={n.id}>
              {i > 0 && <Divider />}
              <Box
                onClick={() => openNotification(n)}
                sx={{
                  px: 2.5,
                  py: 1.5,
                  cursor: 'pointer',
                  bgcolor: n.read_at ? 'transparent' : 'action.hover',
                  '&:hover': { bgcolor: 'action.selected' },
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={2}>
                  <Typography variant="body2" fontWeight={n.read_at ? 500 : 700}>
                    {n.title}
                  </Typography>
                  <Typography variant="caption" color="text.disabled" whiteSpace="nowrap">
                    {new Date(n.created_at).toLocaleString('fr-FR')}
                  </Typography>
                </Stack>
                {n.body && (
                  <Typography variant="body2" color="text.secondary" mt={0.5}>
                    {n.body}
                  </Typography>
                )}
                {notificationSupportsEmail(n.link) && (
                  <Stack direction="row" spacing={1} mt={0.5}>
                    <Button
                      size="small"
                      variant="text"
                      startIcon={<MailRoundedIcon fontSize="small" />}
                      disabled={sendingEmailId === n.id}
                      onClick={(e) => sendNotificationEmail(e, n.id, 'client')}
                      sx={{ textTransform: 'none', minWidth: 0, p: 0 }}
                    >
                      Email client
                    </Button>
                    <Button
                      size="small"
                      variant="text"
                      startIcon={<MailRoundedIcon fontSize="small" />}
                      disabled={sendingEmailId === n.id}
                      onClick={(e) => sendNotificationEmail(e, n.id, 'admin')}
                      sx={{ textTransform: 'none', minWidth: 0, p: 0 }}
                    >
                      Email admin
                    </Button>
                  </Stack>
                )}
              </Box>
            </Box>
          ))
        )}
      </Paper>

      {totalPages > 1 && (
        <Stack direction="row" justifyContent="flex-end" alignItems="center" spacing={1} mt={1.5}>
          <Button size="small" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
            Précédent
          </Button>
          <Typography variant="body2" color="text.secondary">
            Page {page} / {totalPages}
          </Typography>
          <Button size="small" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            Suivant
          </Button>
        </Stack>
      )}
    </Box>
  )
}
