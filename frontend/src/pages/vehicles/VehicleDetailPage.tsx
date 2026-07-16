import { useState } from 'react'
import { useNavigate, useParams, Link as RouterLink } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded'
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded'
import NumbersRoundedIcon from '@mui/icons-material/NumbersRounded'
import { vehiclesApi, FUEL_TYPE_LABELS } from '../../lib/vehiclesApi'
import { STATUS_LABELS as RO_STATUS_LABELS } from '../../lib/repairOrderApi'
import { customerApi } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { useToast } from '../../contexts/ToastContext'
import { useAuth } from '../../contexts/AuthContext'

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" py={1.25}>
      <Typography variant="body2" color="text.secondary" fontWeight={500}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={500} textAlign="right">
        {value ?? <span style={{ color: '#94A3B8' }}>—</span>}
      </Typography>
    </Stack>
  )
}

function SectionCard({ title, icon, children }: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent sx={{ p: 2.5 }}>
        <Stack direction="row" alignItems="center" spacing={1.25} mb={1.5}>
          <Box sx={{ color: 'primary.main' }}>{icon}</Box>
          <Typography variant="subtitle1" fontWeight={700}>
            {title}
          </Typography>
        </Stack>
        <Divider sx={{ mb: 1 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function VehicleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const hasPermission = (p: string) => user?.permissions.includes(p) ?? false
  const { success: toastSuccess, error: toastError } = useToast()

  const [reRegOpen, setReRegOpen] = useState(false)
  const [newReg, setNewReg] = useState('')
  const [reRegNote, setReRegNote] = useState('')

  const reRegMutation = useMutation({
    mutationFn: (vars: { id: number; registration: string; note: string }) =>
      vehiclesApi.reRegister(vars.id, { new_registration: vars.registration, note: vars.note || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicle-history', id] })
      queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      toastSuccess('Immatriculation mise à jour.')
      setReRegOpen(false)
      setNewReg('')
      setReRegNote('')
    },
    onError: () => toastError('Erreur lors du changement d\'immatriculation.'),
  })

  const { data: history, isLoading } = useQuery({
    queryKey: ['vehicle-history', id],
    queryFn: () => vehiclesApi.getHistory(Number(id)),
    enabled: !!id,
  })

  const { data: owner } = useQuery({
    queryKey: ['customer-by-int-id', history?.vehicle.customer_id],
    queryFn: () => customerApi.getByIntId(history!.vehicle.customer_id!),
    enabled: !!history?.vehicle.customer_id,
  })

  if (isLoading) return <LoadingScreen />
  if (!history) return null

  const v = history.vehicle

  return (
    <Box>
      <PageHeader
        title={`${v.make} ${v.model}`}
        subtitle={v.registration ?? v.vin ?? 'Véhicule sans immatriculation'}
        breadcrumbs={[
          { label: 'Véhicules', href: '/vehicles' },
          { label: v.registration ?? `${v.make} ${v.model}` },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            {hasPermission('vehicle.update') && (
              <Button
                variant="outlined"
                startIcon={<NumbersRoundedIcon />}
                onClick={() => { setNewReg(v.registration ?? ''); setReRegOpen(true) }}
              >
                Réimmatriculer
              </Button>
            )}
            <Button
              variant="outlined"
              startIcon={<BuildRoundedIcon />}
              onClick={() => {
                const params = new URLSearchParams()
                params.set('vehicleId', String(v.id))
                if (v.customer_id) params.set('customerId', String(v.customer_id))
                navigate(`/repair-orders/new?${params.toString()}`)
              }}
            >
              Nouvel OT
            </Button>
            <Button
              variant="contained"
              startIcon={<EditRoundedIcon />}
              onClick={() => navigate(`/vehicles/${v.id}/edit`)}
            >
              Modifier
            </Button>
          </Stack>
        }
      />

      <Grid container spacing={3}>
        {/* Left column — vehicle details */}
        <Grid item xs={12} md={7}>
          <Stack spacing={2.5}>
            {/* Identity */}
            <SectionCard
              title="Identité du véhicule"
              icon={<DirectionsCarRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack direction="row" spacing={2} mb={2} flexWrap="wrap">
                {v.registration && (
                  <Box
                    sx={{
                      px: 2,
                      py: 0.75,
                      bgcolor: '#1E3A8A',
                      borderRadius: 1.5,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 1,
                    }}
                  >
                    <Typography
                      sx={{
                        color: '#fff',
                        fontWeight: 700,
                        fontSize: '1.125rem',
                        fontFamily: 'monospace',
                        letterSpacing: '0.1em',
                      }}
                    >
                      {v.registration}
                    </Typography>
                  </Box>
                )}
                <StatusChip status={v.status} />
              </Stack>
              <InfoRow label="Marque" value={v.make} />
              <Divider />
              <InfoRow label="Modèle" value={v.model} />
              <Divider />
              <InfoRow label="Année" value={v.year} />
              <Divider />
              <InfoRow label="Carburant" value={v.fuel_type ? FUEL_TYPE_LABELS[v.fuel_type] : null} />
              <Divider />
              <InfoRow label="Couleur" value={v.color} />
              {v.vin && (
                <>
                  <Divider />
                  <InfoRow
                    label="Numéro VIN"
                    value={
                      <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                        {v.vin}
                      </Typography>
                    }
                  />
                </>
              )}
            </SectionCard>

            {/* Service info */}
            <SectionCard
              title="Entretien & contrôles"
              icon={<CalendarMonthRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <InfoRow
                label="Kilométrage actuel"
                value={
                  v.mileage_current != null ? (
                    <Stack direction="row" alignItems="center" spacing={0.75}>
                      <SpeedRoundedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                      <span>{v.mileage_current.toLocaleString('fr-FR')} km</span>
                    </Stack>
                  ) : null
                }
              />
              <Divider />
              <InfoRow
                label="Contrôle technique"
                value={
                  v.technical_inspection_due_at ? (
                    <Chip
                      size="small"
                      label={new Date(v.technical_inspection_due_at).toLocaleDateString('fr-FR')}
                      color={new Date(v.technical_inspection_due_at) < new Date() ? 'error' : 'default'}
                    />
                  ) : null
                }
              />
              <Divider />
              <InfoRow
                label="Prochain entretien"
                value={
                  v.maintenance_due_at ? (
                    <Chip
                      size="small"
                      label={new Date(v.maintenance_due_at).toLocaleDateString('fr-FR')}
                      color={new Date(v.maintenance_due_at) < new Date() ? 'error' : 'default'}
                    />
                  ) : null
                }
              />
              <Divider />
              <InfoRow
                label="Dernière intervention"
                value={
                  v.last_service_at
                    ? new Date(v.last_service_at).toLocaleDateString('fr-FR')
                    : null
                }
              />
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column — history */}
        <Grid item xs={12} md={5}>
          <Stack spacing={2.5}>
            {/* Ownership history */}
            <SectionCard
              title="Historique de propriété"
              icon={<HistoryRoundedIcon sx={{ fontSize: 20 }} />}
            >
              {history.ownership_history.length === 0 ? (
                <Typography variant="body2" color="text.secondary" py={1}>
                  Aucun transfert enregistré.
                </Typography>
              ) : (
                <Stack spacing={0}>
                  {history.ownership_history.map((h, i) => (
                    <Box key={h.id}>
                      {i > 0 && <Divider />}
                      <Stack py={1.25} spacing={0.25}>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(h.transferred_at).toLocaleDateString('fr-FR')}
                        </Typography>
                        <Typography variant="body2" fontWeight={500}>
                          Client #{h.previous_customer_id ?? '—'} → Client #{h.new_customer_id ?? '—'}
                        </Typography>
                        {h.note && (
                          <Typography variant="caption" color="text.secondary">
                            {h.note}
                          </Typography>
                        )}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </SectionCard>

            {/* Registration aliases */}
            {history.registration_aliases.length > 0 && (
              <SectionCard
                title="Anciennes immatriculations"
                icon={<DirectionsCarRoundedIcon sx={{ fontSize: 20 }} />}
              >
                <Stack spacing={0}>
                  {history.registration_aliases.map((a, i) => (
                    <Box key={a.id}>
                      {i > 0 && <Divider />}
                      <Stack py={1.25} spacing={0.25}>
                        <Typography variant="body2" fontWeight={600} fontFamily="monospace">
                          {a.registration}
                        </Typography>
                        {a.note && (
                          <Typography variant="caption" color="text.secondary">
                            {a.note}
                          </Typography>
                        )}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              </SectionCard>
            )}

            {/* Owner */}
            <SectionCard
              title="Propriétaire"
              icon={<PersonRoundedIcon sx={{ fontSize: 20 }} />}
            >
              {owner ? (
                <Stack spacing={0.5}>
                  <Link
                    href={`/customers/${owner.id}`}
                    underline="hover"
                    variant="body2"
                    fontWeight={700}
                    color="primary"
                  >
                    {owner.full_name}
                    {owner.company_name && (
                      <Typography component="span" variant="caption" color="text.secondary" ml={0.5}>
                        ({owner.company_name})
                      </Typography>
                    )}
                  </Link>
                  {owner.phone_e164 && (
                    <Typography variant="caption" color="text.secondary">{owner.phone_e164}</Typography>
                  )}
                  {owner.email && (
                    <Typography variant="caption" color="text.secondary">{owner.email}</Typography>
                  )}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary" py={1}>
                  Aucun propriétaire assigné.
                </Typography>
              )}
            </SectionCard>

            {/* Repair orders */}
            <SectionCard
              title="Ordres de réparation"
              icon={<BuildRoundedIcon sx={{ fontSize: 20 }} />}
            >
              {history.repair_orders.length === 0 ? (
                <Typography variant="body2" color="text.secondary" py={1}>
                  Aucun ordre de réparation lié à ce véhicule.
                </Typography>
              ) : (
                <Stack spacing={0}>
                  {history.repair_orders.slice(0, 10).map((ro, i) => (
                    <Box key={ro.id}>
                      {i > 0 && <Divider />}
                      <Stack
                        component={RouterLink}
                        to={`/repair-orders/${ro.public_id}`}
                        direction="row"
                        justifyContent="space-between"
                        alignItems="center"
                        py={1.25}
                        sx={{ textDecoration: 'none', color: 'inherit', '&:hover': { bgcolor: 'action.hover' }, px: 0.5, borderRadius: 1 }}
                      >
                        <Stack spacing={0.25}>
                          <Typography variant="body2" fontWeight={600}>
                            {ro.description && ro.description.length > 50 ? ro.description.slice(0, 50) + '…' : ro.description || 'Sans description'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(ro.created_at).toLocaleDateString('fr-FR')}
                          </Typography>
                        </Stack>
                        <Chip
                          label={RO_STATUS_LABELS[ro.status as keyof typeof RO_STATUS_LABELS] ?? ro.status}
                          size="small"
                          sx={{ fontSize: '0.65rem', height: 20 }}
                        />
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>

      {/* ── Re-registration dialog ────────────────────────────────────────── */}
      <Dialog open={reRegOpen} onClose={() => setReRegOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Changer d'immatriculation</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary" mb={2}>
            L'ancienne immatriculation sera conservée comme alias.
          </Typography>
          <TextField
            label="Nouvelle immatriculation"
            value={newReg}
            onChange={e => setNewReg(e.target.value.toUpperCase())}
            fullWidth
            autoFocus
            inputProps={{ style: { fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.1em' } }}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Note (optionnel)"
            value={reRegNote}
            onChange={e => setReRegNote(e.target.value)}
            fullWidth
            multiline
            rows={2}
            placeholder="Ex. : changement suite à vente, correction de plaque…"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setReRegOpen(false)} disabled={reRegMutation.isPending}>
            Annuler
          </Button>
          <Button
            variant="contained"
            disabled={!newReg.trim() || newReg.trim() === v.registration || reRegMutation.isPending}
            onClick={() => reRegMutation.mutate({ id: v.id, registration: newReg.trim(), note: reRegNote })}
          >
            {reRegMutation.isPending ? 'Enregistrement…' : 'Confirmer'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
