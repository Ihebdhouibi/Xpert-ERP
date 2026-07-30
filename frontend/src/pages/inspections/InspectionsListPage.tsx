import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import AssignmentRoundedIcon from '@mui/icons-material/AssignmentRounded'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import {
  inspectionApi,
  type InspectionStatus,
  INSPECTION_STATUS_LABELS,
  INSPECTION_ALLOWED_TRANSITIONS,
} from '../../lib/inspectionApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { EmptyState } from '../../components/ui/EmptyState'

const STATUS_MAP: Record<InspectionStatus, string> = {
  draft: 'draft',
  in_progress: 'in_progress',
  completed: 'done',
  cancelled: 'cancelled',
}

function CreateInspectionDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (id: string) => void
}) {
  const [templateId, setTemplateId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: templates } = useQuery({
    queryKey: ['inspection-templates'],
    queryFn: () => inspectionApi.listTemplates({ page_size: 100 }),
    enabled: open,
  })

  const createMutation = useMutation({
    mutationFn: () => inspectionApi.createInspection({ template_public_id: templateId }),
    onSuccess: (data) => {
      setError(null)
      onCreated(data.id)
      onClose()
    },
    onError: () => setError("Erreur lors de la création de l'inspection."),
  })

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Nouvelle inspection</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <FormControl fullWidth sx={{ mt: 1 }}>
          <InputLabel>Modèle d'inspection</InputLabel>
          <Select
            value={templateId}
            label="Modèle d'inspection"
            onChange={e => setTemplateId(e.target.value)}
          >
            {templates?.items.map(t => (
              <MenuItem key={t.id} value={t.id}>
                {t.name} ({t.sections.reduce((s, sec) => s + sec.items.length, 0)} éléments)
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!templateId || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          Créer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

const FILTER_OPTIONS: Array<{ value: InspectionStatus | ''; label: string }> = [
  { value: '', label: 'Toutes' },
  { value: 'draft', label: 'Brouillon' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'completed', label: 'Terminées' },
  { value: 'cancelled', label: 'Annulées' },
]

export function InspectionsListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<InspectionStatus | ''>('')
  const [createOpen, setCreateOpen] = useState(false)
  const [page] = useState(1)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['inspections', statusFilter, page],
    queryFn: () =>
      inspectionApi.listInspections({
        status: statusFilter || undefined,
        page,
        page_size: 20,
      }),
    placeholderData: prev => prev,
  })

  const handleCreated = (id: string) => {
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
    navigate(`/inspections/${id}`)
  }

  return (
    <Box>
      <PageHeader
        title="Inspections"
        subtitle={data ? `${data.total} inspection${data.total !== 1 ? 's' : ''}` : 'Inspections véhicules'}
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouvelle inspection
          </Button>
        }
      />

      <Box mb={2}>
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_, v) => { if (v !== null || statusFilter !== '') { setStatusFilter(v ?? '') } }}
          size="small"
        >
          {FILTER_OPTIONS.map(opt => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{
                px: 2,
                py: 0.75,
                fontSize: '0.8125rem',
                fontWeight: 600,
                textTransform: 'none',
                border: '1px solid #E2E8F0 !important',
                borderRadius: '8px !important',
                mr: 0.75,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '&:hover': { bgcolor: 'primary.dark' },
                },
              }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      {isLoading && (
        <Stack spacing={1.5}>
          {[...Array(5)].map((_, i) => (
            <Paper key={i} sx={{ p: 2, height: 72, opacity: 0.4 }} />
          ))}
        </Stack>
      )}

      {isError && (
        <Alert severity="error">Impossible de charger les inspections.</Alert>
      )}

      {!isLoading && !isError && data?.items.length === 0 && (
        <EmptyState
          icon={<AssignmentRoundedIcon sx={{ fontSize: 48, color: '#CBD5E1' }} />}
          title="Aucune inspection"
          description={statusFilter ? 'Aucune inspection avec ce statut.' : 'Créez une inspection pour commencer.'}
          action={
            <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>
              Nouvelle inspection
            </Button>
          }
        />
      )}

      {!isLoading && !isError && (data?.items ?? []).length > 0 && (
        <Stack spacing={1.5}>
          {(data?.items ?? []).map(insp => {
            const canContinue = INSPECTION_ALLOWED_TRANSITIONS[insp.status].includes('completed')
            return (
              <Paper
                key={insp.id}
                sx={{
                  p: 2,
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    borderColor: 'primary.light',
                    boxShadow: '0 2px 8px rgba(37,99,235,0.08)',
                    transform: 'translateY(-1px)',
                  },
                }}
                onClick={() => navigate(`/inspections/${insp.id}`)}
              >
                <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Box
                      sx={{
                        width: 40,
                        height: 40,
                        borderRadius: '10px',
                        bgcolor: '#F1F5F9',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <AssignmentRoundedIcon sx={{ color: '#334155', fontSize: 20 }} />
                    </Box>
                    <Box>
                      <Typography variant="body2" fontWeight={700}>
                        {insp.template_name}
                      </Typography>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                        <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                          #{insp.id.slice(-8).toUpperCase()}
                        </Typography>
                        <Typography variant="caption" color="text.disabled">·</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(insp.created_at).toLocaleDateString('fr-FR')}
                        </Typography>
                        {insp.vehicle_id && (
                          <>
                            <Typography variant="caption" color="text.disabled">·</Typography>
                            <Stack direction="row" alignItems="center" spacing={0.5}>
                              <DirectionsCarRoundedIcon sx={{ fontSize: 12, color: 'text.disabled' }} />
                              <Typography variant="caption" color="text.secondary">
                                Véhicule #{insp.vehicle_id}
                              </Typography>
                            </Stack>
                          </>
                        )}
                        {insp.repair_order_id && (
                          <>
                            <Typography variant="caption" color="text.disabled">·</Typography>
                            <Typography variant="caption" color="text.secondary">
                              OR #{insp.repair_order_id.slice(-6).toUpperCase()}
                            </Typography>
                          </>
                        )}
                      </Stack>
                    </Box>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center">
                    {canContinue && (
                      <StatusChip status="in_progress" label="En cours" size="small" />
                    )}
                    <StatusChip
                      status={STATUS_MAP[insp.status] ?? insp.status}
                      label={INSPECTION_STATUS_LABELS[insp.status]}
                      size="small"
                    />
                  </Stack>
                </Stack>
              </Paper>
            )
          })}
        </Stack>
      )}

      <CreateInspectionDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </Box>
  )
}
