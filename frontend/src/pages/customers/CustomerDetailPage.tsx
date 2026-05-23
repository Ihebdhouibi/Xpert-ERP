import { useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Grid,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import RestoreIcon from '@mui/icons-material/Restore'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { customerApi } from '../../lib/customerApi'
import type { CustomerDetail, CustomerStatus } from '../../lib/customerApi'

function StatusChip({ status }: { status: CustomerStatus }) {
  const palette: Record<CustomerStatus, 'success' | 'default' | 'error'> = {
    active: 'success',
    inactive: 'default',
    blocked: 'error',
  }
  return <Chip color={palette[status]} label={status} />
}

function formatMoney(minor: number, currency: string | null) {
  if (!currency) return `${minor}`
  return (minor / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency,
  })
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body1">{value || '-'}</Typography>
    </Box>
  )
}

export function CustomerDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customer', publicId],
    queryFn: () => customerApi.get(publicId),
    enabled: !!publicId,
  })

  const handleDelete = async () => {
    try {
      await customerApi.remove(publicId)
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      navigate('/customers', { replace: true })
    } catch {
      setActionError('Erreur lors de la suppression.')
      setConfirmDelete(false)
    }
  }

  const handleRestore = async () => {
    try {
      await customerApi.restore(publicId)
      await queryClient.invalidateQueries({ queryKey: ['customer', publicId] })
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
    } catch {
      setActionError('Erreur lors de la restauration.')
    }
  }

  if (isLoading) {
    return (
      <Box p={4} display="flex" justifyContent="center">
        <CircularProgress />
      </Box>
    )
  }
  if (isError || !data) {
    return (
      <Box p={4}>
        <Alert severity="error">Impossible de charger ce client.</Alert>
        <Button sx={{ mt: 2 }} onClick={() => navigate('/customers')}>
          Retour à la liste
        </Button>
      </Box>
    )
  }

  const c: CustomerDetail = data
  const isDeleted = c.status === 'inactive' // soft-deleted rows hide from list, but if shown via include_deleted=true the status is inactive

  return (
    <Box p={4} maxWidth={900} mx="auto">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        mb={3}
      >
        <Box>
          <Typography variant="h4" fontWeight={700}>
            {c.full_name}
          </Typography>
          {c.company_name && (
            <Typography variant="subtitle1" color="text.secondary">
              {c.company_name}
            </Typography>
          )}
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <StatusChip status={c.status} />
          <PermissionGate permission="customer.update">
            <Button
              startIcon={<EditIcon />}
              component={RouterLink}
              to={`/customers/${c.id}/edit`}
            >
              Modifier
            </Button>
          </PermissionGate>
          {isDeleted ? (
            <PermissionGate permission="customer.delete">
              <Button
                color="success"
                startIcon={<RestoreIcon />}
                onClick={handleRestore}
              >
                Restaurer
              </Button>
            </PermissionGate>
          ) : (
            <PermissionGate permission="customer.delete">
              <Button
                color="error"
                startIcon={<DeleteIcon />}
                onClick={() => setConfirmDelete(true)}
              >
                Supprimer
              </Button>
            </PermissionGate>
          )}
        </Stack>
      </Stack>

      {actionError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Typography variant="overline" color="text.secondary">
          Identité
        </Typography>
        <Grid container spacing={2} mt={0.5}>
          <Grid item xs={6} sm={4}>
            <Field label="Type" value={c.type === 'company' ? 'Société' : 'Particulier'} />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field label="Identifiant fiscal" value={c.fiscal_id} />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field label="Segment" value={c.segment} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Field label="Téléphone" value={c.phone_e164} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Field label="Email" value={c.email} />
          </Grid>
        </Grid>

        <Divider sx={{ my: 3 }} />

        <Typography variant="overline" color="text.secondary">
          Adresse
        </Typography>
        {c.address ? (
          <Stack mt={0.5}>
            {c.address.street && <Typography>{c.address.street}</Typography>}
            <Typography>
              {[c.address.postal_code, c.address.city].filter(Boolean).join(' ')}
            </Typography>
            {c.address.country && (
              <Typography color="text.secondary">{c.address.country}</Typography>
            )}
          </Stack>
        ) : (
          <Typography color="text.secondary" mt={0.5}>
            Aucune adresse renseignée
          </Typography>
        )}

        <Divider sx={{ my: 3 }} />

        <Typography variant="overline" color="text.secondary">
          Crédit
        </Typography>
        <Grid container spacing={2} mt={0.5}>
          <Grid item xs={6} sm={4}>
            <Field
              label="Limite de crédit"
              value={formatMoney(c.credit_limit_minor, c.credit_currency)}
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field
              label="Encours"
              value={formatMoney(c.outstanding_minor, c.credit_currency)}
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field label="Points fidélité" value={c.loyalty_points} />
          </Grid>
        </Grid>

        {c.notes && (
          <>
            <Divider sx={{ my: 3 }} />
            <Typography variant="overline" color="text.secondary">
              Notes
            </Typography>
            <Typography mt={0.5} whiteSpace="pre-wrap">
              {c.notes}
            </Typography>
          </>
        )}
      </Paper>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Supprimer ce client ?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Le client sera archivé et n'apparaîtra plus dans la liste. Vous
            pourrez le restaurer depuis le journal d'administration.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Annuler</Button>
          <Button color="error" onClick={handleDelete}>
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
