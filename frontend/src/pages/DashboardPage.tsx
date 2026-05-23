import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Button,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import PeopleIcon from '@mui/icons-material/People'
import LogoutIcon from '@mui/icons-material/Logout'
import { PermissionGate } from '../components/auth/PermissionGate'
import { useAuth } from '../contexts/AuthContext'

export function DashboardPage() {
  const { user, logout } = useAuth()

  return (
    <Box p={4}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        mb={3}
      >
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Tableau de bord
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Bienvenue, {user?.full_name}
          </Typography>
        </Box>
        <Button
          startIcon={<LogoutIcon />}
          color="inherit"
          onClick={logout}
        >
          Se déconnecter
        </Button>
      </Stack>

      <Stack direction="row" spacing={2} flexWrap="wrap">
        <PermissionGate permission="customer.read">
          <Paper
            component={RouterLink}
            to="/customers"
            sx={{
              p: 3,
              minWidth: 220,
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              transition: 'box-shadow .15s',
              '&:hover': { boxShadow: 4 },
            }}
          >
            <PeopleIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Clients
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Rechercher et gérer
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
      </Stack>
    </Box>
  )
}
