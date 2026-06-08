import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import { repairOrderApi } from '../../lib/repairOrderApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { MoneyField } from '../../components/ui/MoneyField'
import { LoadingScreen } from '../../components/ui/LoadingScreen'

const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const
const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse',
  normal: 'Normale',
  high: 'Haute',
  urgent: 'Urgente',
}
const PRIORITY_COLORS: Record<string, string> = {
  low: '#64748B',
  normal: '#2563EB',
  high: '#F59E0B',
  urgent: '#EF4444',
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
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2.5}>
          <Box sx={{ color: 'primary.main' }}>{icon}</Box>
          <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        </Stack>
        <Divider sx={{ mb: 2.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function RepairOrderEditPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: ro, isLoading, isError } = useQuery({
    queryKey: ['repair-order', publicId],
    queryFn: () => repairOrderApi.get(publicId),
    enabled: !!publicId,
  })

  // Form state — initialised after data loads
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('normal')
  const [estimatedMinor, setEstimatedMinor] = useState('')
  const [estimatedCurrency, setEstimatedCurrency] = useState('EUR')
  const [notes, setNotes] = useState('')
  const [initialised, setInitialised] = useState(false)

  // Populate state once RO loads
  if (ro && !initialised) {
    setDescription(ro.description)
    setPriority(ro.priority ?? 'normal')
    setEstimatedMinor(ro.estimated_cost_minor != null ? String(ro.estimated_cost_minor) : '')
    setEstimatedCurrency(ro.estimated_cost_currency ?? 'EUR')
    setNotes(ro.notes ?? '')
    setInitialised(true)
  }

  const [fieldErrors, setFieldErrors] = useState<{ description?: string }>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: typeof fieldErrors = {}
    if (!description.trim()) errs.description = 'Description requise'
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await repairOrderApi.update(publicId, ro!.version, {
        description: description.trim(),
        priority: priority || null,
        estimated_cost_minor: estimatedMinor ? Number(estimatedMinor) : null,
        estimated_cost_currency: estimatedCurrency || null,
        notes: notes.trim() || null,
      })
      await queryClient.invalidateQueries({ queryKey: ['repair-order', publicId] })
      navigate(`/repair-orders/${publicId}`, { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status
        if (status === 409) {
          setSubmitError(
            'Cet OT a été modifié par quelqu\'un d\'autre. Rechargez la page et réessayez.',
          )
        } else {
          const d = err.response?.data
          const msg = typeof d?.detail === 'string' ? d.detail : JSON.stringify(d?.detail)
          setSubmitError(msg || 'Erreur lors de la mise à jour.')
        }
      } else {
        setSubmitError('Erreur lors de la mise à jour.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !ro) {
    return (
      <Box>
        <PageHeader
          title="Modifier l'OT"
          breadcrumbs={[{ label: 'Ordres de réparation', href: '/repair-orders' }, { label: 'Modifier' }]}
        />
        <Alert severity="error">Impossible de charger cet ordre de réparation.</Alert>
      </Box>
    )
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title={`Modifier — ${ro.description.length > 40 ? ro.description.slice(0, 40) + '…' : ro.description}`}
        subtitle={`#${ro.id.slice(-8).toUpperCase()} · v${ro.version}`}
        breadcrumbs={[
          { label: 'Ordres de réparation', href: '/repair-orders' },
          { label: `#${ro.id.slice(-8).toUpperCase()}`, href: `/repair-orders/${publicId}` },
          { label: 'Modifier' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate(`/repair-orders/${publicId}`)}
              disabled={isSubmitting}
            >
              Annuler
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRoundedIcon />}
              disabled={isSubmitting}
            >
              Enregistrer
            </Button>
          </Stack>
        }
      />

      {submitError && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSubmitError(null)}>
          {submitError}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ maxWidth: 860 }}>
        <Grid item xs={12} md={7}>
          <Stack spacing={3}>
            <SectionCard
              title="Informations principales"
              icon={<BuildRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2.5}>
                <TextField
                  label="Description *"
                  multiline
                  rows={4}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  error={!!fieldErrors.description}
                  helperText={fieldErrors.description ?? 'Décrivez le problème signalé par le client'}
                  fullWidth
                  autoFocus
                />

                <TextField
                  label="Notes internes"
                  multiline
                  rows={3}
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  helperText="Visible uniquement en interne"
                  fullWidth
                />
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>

        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Priorité & Estimation"
              icon={<TuneRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2.5}>
                <TextField
                  select
                  label="Priorité"
                  value={priority}
                  onChange={e => setPriority(e.target.value)}
                  fullWidth
                >
                  {PRIORITIES.map(p => (
                    <MenuItem key={p} value={p}>
                      <Stack direction="row" alignItems="center" spacing={1.25}>
                        <Box
                          sx={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            bgcolor: PRIORITY_COLORS[p],
                            flexShrink: 0,
                          }}
                        />
                        <span>{PRIORITY_LABELS[p]}</span>
                      </Stack>
                    </MenuItem>
                  ))}
                </TextField>

                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <MoneyField
                    label="Coût estimé"
                    valueMinor={Number(estimatedMinor) || 0}
                    onChangeMinor={(m) => setEstimatedMinor(m ? String(m) : '')}
                    fullWidth
                  />
                  <TextField
                    label="Devise"
                    value={estimatedCurrency}
                    onChange={e => setEstimatedCurrency(e.target.value.toUpperCase())}
                    sx={{ width: 100, flexShrink: 0 }}
                    inputProps={{
                      style: { fontFamily: 'monospace', textTransform: 'uppercase' },
                      maxLength: 3,
                    }}
                  />
                </Stack>
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  )
}
