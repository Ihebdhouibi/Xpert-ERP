import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Box, useMediaQuery, useTheme } from '@mui/material'
import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar, DRAWER_WIDTH, COLLAPSED_WIDTH } from './Sidebar'
import { TopBar } from './TopBar'
import { useCommandPalette } from '../useCommandPalette'

// 130ms ease-out fade — masks React re-render flash, adds perceived polish.
// Deliberately subtle: users should feel snappy, not notice the animation.
const pageVariants = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -4 },
}

const pageTransition = {
  duration: 0.13,
  ease: [0.4, 0, 0.2, 1] as [number, number, number, number], // MUI standard easing
}

export function AppShell() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const location = useLocation()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const { palette, setOpen: openPalette } = useCommandPalette()

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
        <TopBar
          onMenuClick={handleMenuClick}
          sidebarOpen={sidebarOpen}
          onSearchClick={() => openPalette(true)}
        />

        <Box
          component="main"
          sx={{
            flex: 1,
            p: { xs: 2, sm: 3 },
            overflow: 'auto',
            minHeight: 0,
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={pageTransition}
              style={{ height: '100%' }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Box>
      </Box>

      {/* Command palette — portal, available on every page */}
      {palette}
    </Box>
  )
}
