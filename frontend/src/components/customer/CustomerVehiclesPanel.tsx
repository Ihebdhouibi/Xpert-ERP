import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import { customerSubApi } from '../../lib/customerApi'
import type { VehicleOut } from '../../lib/vehiclesApi'
import { FUEL_TYPE_LABELS } from '../../lib/vehiclesApi'
import { PermissionGate } from '../auth/PermissionGate'

interface Props {
  customerPublicId: string
  customerIntId: number
}

const STATUS_COLORS: Record<string, 'success' | 'default' | 'error'> = {
  active: 'success',
  inactive: 'default',
  scrapped: 'error',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Actif',
  inactive: 'Inactif',
  scrapped: 'Épave',
}

function VehicleCard({ vehicle, customerIntId }: { vehicle: VehicleOut; customerIntId: number }) {
  const navigate = useNavigate()

  const plateLabel = vehicle.registration ?? vehicle.vin ?? '—'
  const makeModel = `${vehicle.make} ${vehicle.model}${vehicle.year ? ` (${vehicle.year})` : ''}`
  const fuel = vehicle.fuel_type ? FUEL_TYPE_LABELS[vehicle.fuel_type] : null

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Stack spacing={1.5}>
          {/* Header: plate + status */}
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Typography
              variant="subtitle2"
              fontFamily="monospace"
              fontWeight={700}
              fontSize="0.9rem"
              sx={{ letterSpacing: 1 }}
            >
              {plateLabel}
            </Typography>
            <Chip
              label={STATUS_LABELS[vehicle.status] ?? vehicle.status}
              size="small"
              color={STATUS_COLORS[vehicle.status] ?? 'default'}
              sx={{ fontSize: '0.65rem', height: 20 }}
            />
          </Stack>

          {/* Make / model */}
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {makeModel}
          </Typography>

          {/* Details row */}
          <Stack direction="row" spacing={2}>
            {fuel && (
              <Typography variant="caption" color="text.disabled">{fuel}</Typography>
            )}
            {vehicle.mileage_current != null && (
              <Typography variant="caption" color="text.disabled">
                {vehicle.mileage_current.toLocaleString('fr-FR')} km
              </Typography>
            )}
            {vehicle.last_service_at && (
              <Tooltip title="Dernier entretien">
                <Typography variant="caption" color="text.disabled">
                  Entretien: {new Date(vehicle.last_service_at).toLocaleDateString('fr-FR')}
                </Typography>
              </Tooltip>
            )}
          </Stack>

          <Divider />

          {/* Actions */}
          <Stack direction="row" spacing={1}>
            <PermissionGate permission="repair_order.create">
              <Button
                size="small"
                variant="contained"
                startIcon={<BuildRoundedIcon sx={{ fontSize: '0.8rem !important' }} />}
                onClick={() =>
                  navigate(
                    `/repair-orders/new?customerId=${customerIntId}&vehicleId=${vehicle.id}`,
                  )
                }
                sx={{ fontSize: '0.72rem', py: 0.4, px: 1 }}
              >
                Créer OdR
              </Button>
            </PermissionGate>
            <Button
              size="small"
              variant="outlined"
              startIcon={<OpenInNewRoundedIcon sx={{ fontSize: '0.8rem !important' }} />}
              onClick={() => navigate(`/vehicles/${vehicle.id}`)}
              sx={{ fontSize: '0.72rem', py: 0.4, px: 1 }}
            >
              Voir
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}

export function CustomerVehiclesPanel({ customerPublicId, customerIntId }: Props) {
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['customer-vehicles', customerPublicId],
    queryFn: () => customerSubApi.getVehicles(customerPublicId, { page_size: 50 }),
    enabled: !!customerPublicId,
  })

  const vehicles: VehicleOut[] = data?.items ?? []

  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <Box sx={{ color: 'primary.main' }}>
              <DirectionsCarRoundedIcon sx={{ fontSize: 20 }} />
            </Box>
            <Typography variant="subtitle1" fontWeight={700}>
              Véhicules
            </Typography>
            {data?.total != null && (
              <Chip
                label={data.total}
                size="small"
                sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600, height: 20 }}
              />
            )}
          </Stack>
          <PermissionGate permission="vehicle.create">
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate(`/vehicles/new?customerId=${customerIntId}&returnTo=/customers/${customerPublicId}`)}
            >
              Ajouter un véhicule
            </Button>
          </PermissionGate>
        </Stack>
        <Divider sx={{ mb: 2 }} />

        {isLoading ? (
          <Box display="flex" justifyContent="center" py={3}>
            <CircularProgress size={28} />
          </Box>
        ) : vehicles.length === 0 ? (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
              bgcolor: '#FAFAFA',
              borderRadius: 2,
              border: '1px dashed',
              borderColor: 'divider',
            }}
          >
            <DirectionsCarRoundedIcon sx={{ fontSize: 36, color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              Aucun véhicule enregistré pour ce client.
            </Typography>
            <PermissionGate permission="vehicle.create">
              <Button
                size="small"
                variant="text"
                startIcon={<AddRoundedIcon />}
                onClick={() => navigate(`/vehicles/new?customerId=${customerIntId}&returnTo=/customers/${customerPublicId}`)}
                sx={{ mt: 1 }}
              >
                Ajouter un véhicule
              </Button>
            </PermissionGate>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {vehicles.map((v) => (
              <Grid item key={v.id} xs={12} sm={6} lg={4}>
                <VehicleCard vehicle={v} customerIntId={customerIntId} />
              </Grid>
            ))}
          </Grid>
        )}
      </CardContent>
    </Card>
  )
}
