import { useState, type MouseEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  InputBase,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import { inboxApi, notificationSupportsEmail } from '../../lib/notificationApi'
import MenuRoundedIcon from '@mui/icons-material/MenuRounded'
import MenuOpenRoundedIcon from '@mui/icons-material/MenuOpenRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import NotificationsNoneRoundedIcon from '@mui/icons-material/NotificationsNoneRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import TabletAndroidRoundedIcon from '@mui/icons-material/TabletAndroidRounded'
import MailRoundedIcon from '@mui/icons-material/MailRounded'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { navSections } from './navConfig'

function getPageTitle(pathname: string): string {
  for (const section of navSections) {
    for (const item of section.items) {
      if (item.exact) {
        if (pathname === item.path) return item.label
      } else {
        if (pathname === item.path || pathname.startsWith(item.path + '/')) {
          return item.label
        }
      }
    }
  }
  return 'Xpert ERP'
}

interface TopBarProps {
  onMenuClick: () => void
  sidebarOpen: boolean
  onSearchClick: () => void
}

export function TopBar({ onMenuClick, sidebarOpen, onSearchClick }: TopBarProps) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const [notifAnchor, setNotifAnchor] = useState<HTMLElement | null>(null)
  const [sendingEmailId, setSendingEmailId] = useState<number | null>(null)

  const { data: inbox } = useQuery({
    queryKey: ['notifications', 'inbox'],
    queryFn: () => inboxApi.list(),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  })

  const openNotification = async (n: { id: number; link: string | null }) => {
    setNotifAnchor(null)
    try {
      await inboxApi.markRead(n.id)
    } catch {
      /* non-blocking */
    }
    queryClient.invalidateQueries({ queryKey: ['notifications', 'inbox'] })
    if (n.link) navigate(n.link)
  }

  const markAll = async () => {
    await inboxApi.markAllRead()
    queryClient.invalidateQueries({ queryKey: ['notifications', 'inbox'] })
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

  const pageTitle = getPageTitle(location.pathname)

  const initials =
    user?.full_name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) ?? '?'

  const handleLogout = async () => {
    setAnchorEl(null)
    await logout()
    navigate('/login', { replace: true })
  }

  // Detect Mac for the shortcut hint
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: '#FFFFFF',
        borderBottom: '1px solid #E2E8F0',
        color: 'text.primary',
        zIndex: theme => theme.zIndex.appBar,
      }}
    >
      <Toolbar sx={{ gap: 1, minHeight: '64px !important', px: { xs: 2, md: 3 } }}>
        {/* Mobile menu toggle */}
        <IconButton
          onClick={onMenuClick}
          size="small"
          sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', mr: 0.5 }}
        >
          <MenuRoundedIcon />
        </IconButton>

        {/* Desktop sidebar toggle */}
        <Tooltip title={sidebarOpen ? 'Réduire' : 'Développer'} placement="bottom">
          <IconButton
            onClick={onMenuClick}
            size="small"
            sx={{ display: { xs: 'none', md: 'flex' }, color: 'text.secondary', mr: 0.5 }}
          >
            {sidebarOpen ? <MenuOpenRoundedIcon /> : <MenuRoundedIcon />}
          </IconButton>
        </Tooltip>

        {/* Page title */}
        <Typography
          variant="h6"
          fontWeight={600}
          fontSize="1rem"
          letterSpacing="-0.01em"
          sx={{ color: 'text.primary', display: { xs: 'none', sm: 'block' } }}
        >
          {pageTitle}
        </Typography>

        {/* Cmd+K search trigger — desktop only */}
        <Box
          onClick={onSearchClick}
          sx={{
            display: { xs: 'none', md: 'flex' },
            alignItems: 'center',
            gap: 1,
            ml: 2,
            px: 1.5,
            py: 0.625,
            borderRadius: 1.5,
            border: '1px solid #E2E8F0',
            bgcolor: '#F8FAFC',
            cursor: 'pointer',
            minWidth: 200,
            transition: 'border-color 0.15s, background-color 0.15s',
            '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F1F5F9' },
          }}
        >
          <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
          <InputBase
            placeholder="Rechercher…"
            readOnly
            onClick={onSearchClick}
            sx={{
              flex: 1,
              pointerEvents: 'none',
              '& input': {
                p: 0,
                fontSize: '0.8125rem',
                color: '#94A3B8',
                cursor: 'pointer',
              },
            }}
          />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.375,
              flexShrink: 0,
            }}
          >
            <Box
              component="kbd"
              sx={{
                px: 0.5, py: 0.25,
                bgcolor: 'white',
                border: '1px solid #E2E8F0',
                borderRadius: '4px',
                fontSize: '0.6875rem',
                fontFamily: 'inherit',
                color: '#94A3B8',
                lineHeight: 1.4,
              }}
            >
              {isMac ? '⌘' : 'Ctrl'}
            </Box>
            <Box
              component="kbd"
              sx={{
                px: 0.5, py: 0.25,
                bgcolor: 'white',
                border: '1px solid #E2E8F0',
                borderRadius: '4px',
                fontSize: '0.6875rem',
                fontFamily: 'inherit',
                color: '#94A3B8',
                lineHeight: 1.4,
              }}
            >
              K
            </Box>
          </Box>
        </Box>

        {/* Mobile search icon */}
        <IconButton
          size="small"
          onClick={onSearchClick}
          sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', ml: 'auto' }}
        >
          <SearchRoundedIcon sx={{ fontSize: 20 }} />
        </IconButton>

        <Box sx={{ flex: 1, display: { xs: 'none', md: 'block' } }} />

        {/* Tablet view shortcut */}
        <Tooltip title="Vue mécanicien (tablette)" placement="bottom">
          <IconButton
            size="small"
            onClick={() => navigate('/tablet')}
            sx={{ color: 'text.secondary', display: { xs: 'none', sm: 'flex' } }}
          >
            <TabletAndroidRoundedIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Tooltip>

        {/* Notifications */}
        <Tooltip title="Notifications" placement="bottom">
          <IconButton
            size="small"
            sx={{ color: 'text.secondary' }}
            onClick={(e) => setNotifAnchor(e.currentTarget)}
          >
            <Badge badgeContent={inbox?.unread_count ?? 0} color="error" max={9}>
              <NotificationsNoneRoundedIcon sx={{ fontSize: 20 }} />
            </Badge>
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={notifAnchor}
          open={Boolean(notifAnchor)}
          onClose={() => setNotifAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          PaperProps={{ sx: { width: 360, maxHeight: 460 } }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1 }}>
            <Typography variant="subtitle2" fontWeight={700}>Notifications</Typography>
            {(inbox?.unread_count ?? 0) > 0 && (
              <Button size="small" onClick={markAll} sx={{ textTransform: 'none' }}>
                Tout marquer comme lu
              </Button>
            )}
          </Stack>
          <Divider />
          {(inbox?.items ?? []).length === 0 ? (
            <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">Aucune notification.</Typography>
            </Box>
          ) : (
            (inbox?.items ?? []).map((n) => (
              <MenuItem
                key={n.id}
                onClick={() => openNotification(n)}
                sx={{ alignItems: 'flex-start', py: 1, whiteSpace: 'normal', bgcolor: n.read_at ? 'transparent' : 'action.hover' }}
              >
                <ListItemText
                  primary={n.title}
                  secondary={
                    <>
                      {n.body}
                      <Typography component="span" variant="caption" color="text.disabled" display="block">
                        {new Date(n.created_at).toLocaleString('fr-FR')}
                      </Typography>
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
                    </>
                  }
                  primaryTypographyProps={{ fontWeight: n.read_at ? 500 : 700, variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption', component: 'div' }}
                />
              </MenuItem>
            ))
          )}
        </Menu>

        {/* User avatar */}
        <Tooltip title="Mon compte" placement="bottom">
          <IconButton
            size="small"
            onClick={e => setAnchorEl(e.currentTarget)}
            sx={{ ml: 0.5, p: 0.5 }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: 'primary.main',
                fontSize: '0.75rem',
                fontWeight: 700,
                background: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
              }}
            >
              {initials}
            </Avatar>
          </IconButton>
        </Tooltip>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={() => setAnchorEl(null)}
          PaperProps={{
            elevation: 3,
            sx: {
              borderRadius: 2,
              minWidth: 220,
              mt: 1,
              border: '1px solid #E2E8F0',
              '& .MuiMenuItem-root': {
                borderRadius: 1,
                mx: 0.5,
                fontSize: '0.875rem',
              },
            },
          }}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        >
          <Box sx={{ px: 2, py: 1.5 }}>
            <Typography variant="subtitle2" fontWeight={600} noWrap>
              {user?.full_name}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {user?.email}
            </Typography>
          </Box>
          <Divider sx={{ my: 0.5 }} />
          <MenuItem onClick={() => setAnchorEl(null)} disabled>
            <ListItemIcon>
              <PersonRoundedIcon fontSize="small" />
            </ListItemIcon>
            Mon profil
          </MenuItem>
          <Divider sx={{ my: 0.5 }} />
          <MenuItem
            onClick={handleLogout}
            sx={{ color: 'error.main', '& .MuiListItemIcon-root': { color: 'error.main' } }}
          >
            <ListItemIcon>
              <LogoutRoundedIcon fontSize="small" />
            </ListItemIcon>
            Se déconnecter
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
