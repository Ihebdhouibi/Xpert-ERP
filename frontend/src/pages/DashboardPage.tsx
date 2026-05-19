import { Box, Typography } from '@mui/material'
import { useAuth } from '../contexts/AuthContext'

export function DashboardPage() {
  const { user, logout } = useAuth()

  return (
    <Box p={4}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Tableau de bord
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Bienvenue, {user?.full_name}
      </Typography>
      <Box mt={2}>
        <Typography
          component="span"
          color="primary"
          sx={{ cursor: 'pointer', textDecoration: 'underline' }}
          onClick={logout}
        >
          Se deconnecter
        </Typography>
      </Box>
    </Box>
  )
}
