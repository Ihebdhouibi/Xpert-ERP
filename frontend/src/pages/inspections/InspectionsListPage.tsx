import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
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
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import AssignmentIcon from '@mui/icons-material/Assignment'
import {
  inspectionApi,
  type InspectionStatus,
  INSPECTION_STATUS_LABELS,
  INSPECTION_ALLOWED_TRANSITIONS,
} from '../../lib/inspectionApi'

const STATUS_COLORS: Record<
  InspectionStatus,
  'default' | 'primary' | 'success' | 'error'
> = {
  draft: 'default',
  in_progress: 'primary',
  completed: 'success',
  cancelled: 'error',
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
            onChange={(e) => setTemplateId(e.target.value)}
          >
            {templates?.items.map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.name} (
                {t.sections.reduce((sum, s) => sum + s.items.length, 0)} éléments)
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
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
    placeholderData: (prev) => prev,
  })

  const handleCreated = (id: string) => {
    queryClient.invalidateQueries({ queryKey: ['inspections'] })
    navigate(`/inspections/${id}`)
  }

  const statuses: InspectionStatus[] = ['draft', 'in_progress', 'completed', 'cancelled']

  return (
    <Box sx={{ p: 3, maxWidth: 1000, mx: 'auto' }}>
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        mb={3}
        flexWrap="wrap"
        spacing={1}
        useFlexGap
      >
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Inspections
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {data?.total ?? 0} inspection{(data?.total ?? 0) !== 1 ? 's' : ''}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Statut</InputLabel>
            <Select
              value={statusFilter}
              label="Statut"
              onChange={(e) => setStatusFilter(e.target.value as InspectionStatus | '')}
            >
              <MenuItem value="">Tous</MenuItem>
              {statuses.map((s) => (
                <MenuItem key={s} value={s}>
                  {INSPECTION_STATUS_LABELS[s]}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouvelle inspection
          </Button>
        </Stack>
      </Stack>

      {isLoading && <CircularProgress />}
      {isError && <Alert severity="error">Impossible de charger les inspections.</Alert>}

      {data?.items.map((insp) => {
        const canContinue = INSPECTION_ALLOWED_TRANSITIONS[insp.status].includes('completed')
        return (
          <Paper
            key={insp.id}
            sx={{ mb: 1.5, p: 2, cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
            onClick={() => navigate(`/inspections/${insp.id}`)}
          >
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              flexWrap="wrap"
              spacing={1}
              useFlexGap
            >
              <Stack direction="row" spacing={1.5} alignItems="center">
                <AssignmentIcon color="action" />
                <Box>
                  <Typography fontWeight={600}>{insp.template_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    #{insp.id.slice(-8).toUpperCase()} ·{' '}
                    {new Date(insp.created_at).toLocaleDateString('fr-FR')}
                    {insp.vehicle_id ? ` · Véhicule #${insp.vehicle_id}` : ''}
                    {insp.repair_order_id ? ` · OR #${insp.repair_order_id.slice(-6).toUpperCase()}` : ''}
                  </Typography>
                </Box>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                {canContinue && (
                  <Chip label="En cours" color="primary" size="small" variant="outlined" />
                )}
                <Chip
                  label={INSPECTION_STATUS_LABELS[insp.status]}
                  color={STATUS_COLORS[insp.status]}
                  size="small"
                  sx={{ fontWeight: 700 }}
                />
              </Stack>
            </Stack>
          </Paper>
        )
      })}

      {data?.items.length === 0 && !isLoading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">Aucune inspection trouvée.</Typography>
        </Paper>
      )}

      <CreateInspectionDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </Box>
  )
}
