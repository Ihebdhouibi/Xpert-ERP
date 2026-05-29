import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Button,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import PeopleIcon from '@mui/icons-material/People'
import BuildIcon from '@mui/icons-material/Build'
import ViewKanbanIcon from '@mui/icons-material/ViewKanban'
import TabletIcon from '@mui/icons-material/Tablet'
import InventoryIcon from '@mui/icons-material/Inventory'
import WarehouseIcon from '@mui/icons-material/Warehouse'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart'
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong'
import BarChartIcon from '@mui/icons-material/BarChart'
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
        <PermissionGate permission="repair_order.read">
          <Paper
            component={RouterLink}
            to="/repair-orders"
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
            <BuildIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Ordres de réparation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Atelier et suivi
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="repair_order.transition">
          <Paper
            component={RouterLink}
            to="/workshop"
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
            <ViewKanbanIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Kanban atelier
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Vue d'ensemble statuts
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="repair_order.update">
          <Paper
            component={RouterLink}
            to="/tablet"
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
            <TabletIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Vue mécanicien
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Tablette & pointage
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="part.read">
          <Paper
            component={RouterLink}
            to="/parts"
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
            <InventoryIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Catalogue pièces
              </Typography>
              <Typography variant="body2" color="text.secondary">
                SKU, catégories, équivalences
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="part.read">
          <Paper
            component={RouterLink}
            to="/stock"
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
            <WarehouseIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Gestion du stock
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Mouvements et alertes
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="purchase_order.read">
          <Paper
            component={RouterLink}
            to="/purchase-orders"
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
            <ShoppingCartIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Bons de commande
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Achats & réception
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="supplier_invoice.read">
          <Paper
            component={RouterLink}
            to="/supplier-invoices"
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
            <ReceiptLongIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Factures fournisseurs
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Rapprochement 3 voies
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="reporting.dashboard.read">
          <Paper
            component={RouterLink}
            to="/kpi"
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
            <BarChartIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Tableau de bord KPI
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Indicateurs & tendances
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
        <PermissionGate permission="supplier.read">
          <Paper
            component={RouterLink}
            to="/suppliers"
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
            <LocalShippingIcon color="primary" fontSize="large" />
            <Box>
              <Typography variant="h6" color="text.primary">
                Fournisseurs
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Gestion et prix
              </Typography>
            </Box>
          </Paper>
        </PermissionGate>
      </Stack>
    </Box>
  )
}
