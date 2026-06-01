import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import MenuRoundedIcon from '@mui/icons-material/MenuRounded'
import MenuOpenRoundedIcon from '@mui/icons-material/MenuOpenRounded'
import NotificationsNoneRoundedIcon from '@mui/icons-material/NotificationsNoneRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import TabletAndroidRoundedIcon from '@mui/icons-material/TabletAndroidRounded'
import { useAuth } from '../../contexts/AuthContext'
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
}

export function TopBar({ onMenuClick, sidebarOpen }: TopBarProps) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)

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
          sx={{
            display: { xs: 'flex', md: 'none' },
            color: 'text.secondary',
            mr: 0.5,
          }}
        >
          <MenuRoundedIcon />
        </IconButton>

        {/* Desktop sidebar toggle */}
        <Tooltip
          title={sidebarOpen ? 'Réduire' : 'Développer'}
          placement="bottom"
        >
          <IconButton
            onClick={onMenuClick}
            size="small"
            sx={{
              display: { xs: 'none', md: 'flex' },
              color: 'text.secondary',
              mr: 0.5,
            }}
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
          sx={{ flex: 1, color: 'text.primary' }}
        >
          {pageTitle}
        </Typography>

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
          <IconButton size="small" sx={{ color: 'text.secondary' }}>
            <Badge badgeContent={0} color="error" max={9}>
              <NotificationsNoneRoundedIcon sx={{ fontSize: 20 }} />
            </Badge>
          </IconButton>
        </Tooltip>

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
