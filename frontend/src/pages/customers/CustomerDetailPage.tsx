import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Stack,
  Typography,
} from '@mui/material'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import SettingsBackupRestoreRoundedIcon from '@mui/icons-material/SettingsBackupRestoreRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded'
import EmailRoundedIcon from '@mui/icons-material/EmailRounded'
import PhoneRoundedIcon from '@mui/icons-material/PhoneRounded'
import LocationOnRoundedIcon from '@mui/icons-material/LocationOnRounded'
import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { customerApi } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const TYPE_LABELS = { individual: 'Particulier', company: 'Société' }
const STATUS_LABELS = { active: 'Actif', inactive: 'Inactif', blocked: 'Bloqué' }

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" py={1.25} gap={2}>
      <Typography variant="body2" color="text.secondary" fontWeight={500} flexShrink={0}>
        {label}
      </Typography>
      <Box textAlign="right">
        {value ?? <Typography variant="body2" color="text.disabled">—</Typography>}
      </Box>
    </Stack>
  )
}

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
          <Box sx={{ color: 'primary.main' }}>{icon}</Box>
          <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        </Stack>
        <Divider sx={{ mb: 0.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function CustomerDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customer', publicId],
    queryFn: () => customerApi.get(publicId),
    enabled: !!publicId,
  })

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await customerApi.remove(publicId)
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      success('Client archivé')
      navigate('/customers', { replace: true })
    } catch {
      toastError('Erreur lors de la suppression.')
      setConfirmDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  const handleRestore = async () => {
    try {
      await customerApi.restore(publicId)
      await queryClient.invalidateQueries({ queryKey: ['customer', publicId] })
      await queryClient.invalidateQueries({ queryKey: ['customers'] })
      success('Client restauré')
    } catch {
      toastError('Erreur lors de la restauration.')
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !data) {
    return (
      <Box>
        <PageHeader
          title="Client"
          breadcrumbs={[{ label: 'Clients', href: '/customers' }, { label: '—' }]}
        />
        <Typography color="error">Impossible de charger ce client.</Typography>
      </Box>
    )
  }

  const c = data
  const isArchived = c.status === 'inactive'

  return (
    <Box>
      <PageHeader
        title={c.full_name}
        subtitle={c.company_name ?? TYPE_LABELS[c.type]}
        breadcrumbs={[
          { label: 'Clients', href: '/customers' },
          { label: c.full_name },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <StatusChip status={c.status} label={STATUS_LABELS[c.status]} />
            <PermissionGate permission="customer.update">
              <Button
                variant="outlined"
                startIcon={<EditRoundedIcon />}
                onClick={() => navigate(`/customers/${c.id}/edit`)}
              >
                Modifier
              </Button>
            </PermissionGate>
            {isArchived ? (
              <PermissionGate permission="customer.delete">
                <Button
                  variant="outlined"
                  color="success"
                  startIcon={<SettingsBackupRestoreRoundedIcon />}
                  onClick={handleRestore}
                >
                  Restaurer
                </Button>
              </PermissionGate>
            ) : (
              <PermissionGate permission="customer.delete">
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteRoundedIcon />}
                  onClick={() => setConfirmDelete(true)}
                >
                  Archiver
                </Button>
              </PermissionGate>
            )}
          </Stack>
        }
      />

      <Grid container spacing={3}>
        {/* Left column */}
        <Grid item xs={12} md={7}>
          <Stack spacing={3}>
            <SectionCard
              title="Identité"
              icon={c.type === 'company'
                ? <BusinessRoundedIcon sx={{ fontSize: 20 }} />
                : <PersonRoundedIcon sx={{ fontSize: 20 }} />
              }
            >
              <InfoRow label="Type" value={
                <Chip
                  label={TYPE_LABELS[c.type]}
                  size="small"
                  sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600 }}
                />
              } />
              {c.company_name && (
                <>
                  <Divider />
                  <InfoRow label="Raison sociale" value={
                    <Typography variant="body2" fontWeight={600}>{c.company_name}</Typography>
                  } />
                </>
              )}
              {c.fiscal_id && (
                <>
                  <Divider />
                  <InfoRow label="Identifiant fiscal" value={
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>{c.fiscal_id}</Typography>
                  } />
                </>
              )}
              {c.segment && (
                <>
                  <Divider />
                  <InfoRow label="Segment" value={
                    <Chip label={c.segment} size="small" variant="outlined" sx={{ fontWeight: 500 }} />
                  } />
                </>
              )}
              <Divider />
              <InfoRow label="Dernière visite" value={
                c.last_visit_at
                  ? <Typography variant="body2" color="text.secondary">
                      {new Date(c.last_visit_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
                    </Typography>
                  : null
              } />
              <Divider />
              <InfoRow label="Client depuis" value={
                <Typography variant="body2" color="text.secondary">
                  {new Date(c.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
                </Typography>
              } />
            </SectionCard>

            <SectionCard
              title="Coordonnées"
              icon={<EmailRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <InfoRow label="Email" value={
                c.email
                  ? <Typography
                      component="a"
                      href={`mailto:${c.email}`}
                      variant="body2"
                      fontWeight={500}
                      color="primary.main"
                      sx={{ textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                    >
                      {c.email}
                    </Typography>
                  : null
              } />
              <Divider />
              <InfoRow label="Téléphone" value={
                c.phone_e164
                  ? <Typography
                      component="a"
                      href={`tel:${c.phone_e164}`}
                      variant="body2"
                      fontWeight={500}
                      fontFamily="monospace"
                      color="primary.main"
                      sx={{ textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                    >
                      {c.phone_e164}
                    </Typography>
                  : null
              } />
              {c.contacts.length > 0 && (
                <>
                  <Divider sx={{ mt: 0.5, mb: 1.5 }} />
                  <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={1}>
                    Contacts supplémentaires
                  </Typography>
                  <Stack spacing={1}>
                    {c.contacts.map((contact, i) => (
                      <Stack key={i} direction="row" alignItems="center" justifyContent="space-between">
                        <Stack direction="row" spacing={1} alignItems="center">
                          {contact.channel === 'email'
                            ? <EmailRoundedIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
                            : <PhoneRoundedIcon sx={{ fontSize: 15, color: 'text.disabled' }} />
                          }
                          <Typography
                            variant="body2"
                            fontFamily={contact.channel !== 'email' ? 'monospace' : undefined}
                          >
                            {contact.value}
                          </Typography>
                          {contact.label && (
                            <Typography variant="caption" color="text.disabled">({contact.label})</Typography>
                          )}
                        </Stack>
                        {contact.is_primary && (
                          <Chip
                            label="Principal"
                            size="small"
                            color="primary"
                            sx={{ fontSize: '0.6875rem', height: 20 }}
                          />
                        )}
                      </Stack>
                    ))}
                  </Stack>
                </>
              )}
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column */}
        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Finance & Fidélité"
              icon={<AccountBalanceWalletRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <InfoRow label="Limite de crédit" value={
                <Typography variant="body2" fontWeight={600} fontFamily="monospace">
                  {formatMinor(c.credit_limit_minor, c.credit_currency ?? 'EUR')}
                </Typography>
              } />
              <Divider />
              <InfoRow label="Encours" value={
                <Typography
                  variant="body2"
                  fontWeight={700}
                  fontFamily="monospace"
                  color={c.outstanding_minor > 0 ? 'error.main' : 'text.secondary'}
                >
                  {formatMinor(c.outstanding_minor, c.credit_currency ?? 'EUR')}
                </Typography>
              } />
              <Divider />
              <InfoRow label="Points fidélité" value={
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2" fontWeight={700}>
                    {c.loyalty_points.toLocaleString('fr-FR')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">pts</Typography>
                </Stack>
              } />
            </SectionCard>

            <SectionCard
              title="Adresse"
              icon={<LocationOnRoundedIcon sx={{ fontSize: 20 }} />}
            >
              {c.address && (c.address.street || c.address.city || c.address.postal_code) ? (
                <Stack spacing={0.5} pt={1} pb={0.5}>
                  {c.address.street && (
                    <Typography variant="body2" fontWeight={500}>{c.address.street}</Typography>
                  )}
                  <Typography variant="body2" color="text.secondary">
                    {[c.address.postal_code, c.address.city].filter(Boolean).join(' ')}
                  </Typography>
                  {c.address.country && (
                    <Typography variant="caption" color="text.disabled">{c.address.country}</Typography>
                  )}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.disabled" py={1}>
                  Aucune adresse renseignée.
                </Typography>
              )}
            </SectionCard>

            {c.notes && (
              <Card>
                <CardContent sx={{ p: 3 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={1.5}>Notes</Typography>
                  <Divider sx={{ mb: 1.5 }} />
                  <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                    {c.notes}
                  </Typography>
                </CardContent>
              </Card>
            )}
          </Stack>
        </Grid>
      </Grid>

      <ConfirmDialog
        open={confirmDelete}
        title="Archiver ce client ?"
        message="Le client sera archivé et n'apparaîtra plus dans la liste active. Il pourra être restauré depuis cette même page."
        confirmLabel="Archiver"
        dangerous
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </Box>
  )
}
