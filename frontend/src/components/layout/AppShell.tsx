import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Box, useMediaQuery, useTheme } from '@mui/material'
import { Sidebar, DRAWER_WIDTH, COLLAPSED_WIDTH } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleMenuClick = () => {
    if (isMobile) {
      setMobileOpen(prev => !prev)
    } else {
      setSidebarOpen(prev => !prev)
    }
  }

  const drawerWidth = isMobile ? 0 : sidebarOpen ? DRAWER_WIDTH : COLLAPSED_WIDTH

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(prev => !prev)}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      <Box
        component="div"
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          transition: theme.transitions.create(['width', 'margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        }}
      >
        <TopBar onMenuClick={handleMenuClick} sidebarOpen={sidebarOpen} />

        <Box
          component="main"
          sx={{
            flex: 1,
            p: { xs: 2, sm: 3 },
            overflow: 'auto',
            minHeight: 0,
          }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
