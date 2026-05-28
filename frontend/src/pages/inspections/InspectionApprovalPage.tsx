import { useState, type ReactElement } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import ErrorIcon from '@mui/icons-material/Error'
import ThumbUpIcon from '@mui/icons-material/ThumbUp'
import ThumbDownIcon from '@mui/icons-material/ThumbDown'
import {
  inspectionApi,
  type ApprovalDecision,
  type ApprovalPublicItem,
  type ApprovalPublicSection,
} from '../../lib/inspectionApi'

const STATUS_ICONS: Record<string, ReactElement> = {
  ok: <CheckCircleIcon sx={{ color: '#22c55e' }} />,
  attention: <WarningAmberIcon sx={{ color: '#f59e0b' }} />,
  defective: <ErrorIcon sx={{ color: '#ef4444' }} />,
  not_applicable: <CheckCircleIcon sx={{ color: '#9ca3af' }} />,
}

const STATUS_LABELS: Record<string, string> = {
  ok: 'OK',
  attention: 'À surveiller',
  defective: 'Défectueux',
  not_applicable: 'N/A',
}

function ItemDecisionRow({
  item,
  decision,
  onDecide,
  submitted,
}: {
  item: ApprovalPublicItem
  decision: 'approved' | 'rejected' | null
  onDecide: (itemId: string, d: 'approved' | 'rejected') => void
  submitted: boolean
}) {
  return (
    <Box
      sx={{
        py: 1.5,
        px: 1,
        borderBottom: '1px solid',
        borderColor: 'divider',
        '&:last-child': { borderBottom: 'none' },
        bgcolor:
          decision === 'approved'
            ? '#f0fdf4'
            : decision === 'rejected'
            ? '#fef2f2'
            : 'transparent',
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
        {item.item_status && STATUS_ICONS[item.item_status]}
        <Box sx={{ flex: 1, minWidth: 160 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
            {item.item_label}
          </Typography>
          {item.notes && (
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              {item.notes}
            </Typography>
          )}
        </Box>
        {item.item_status && (
          <Chip
            label={STATUS_LABELS[item.item_status] ?? item.item_status}
            size="small"
            color={
              item.item_status === 'ok'
                ? 'success'
                : item.item_status === 'attention'
                ? 'warning'
                : item.item_status === 'defective'
                ? 'error'
                : 'default'
            }
            variant="outlined"
          />
        )}
        {item.actionable && !submitted && (
          <Stack direction="row" spacing={1}>
            <Button
              variant={decision === 'approved' ? 'contained' : 'outlined'}
              color="success"
              size="small"
              startIcon={<ThumbUpIcon />}
              sx={{ minWidth: 110 }}
              onClick={() => onDecide(item.item_id, 'approved')}
            >
              Accepter
            </Button>
            <Button
              variant={decision === 'rejected' ? 'contained' : 'outlined'}
              color="error"
              size="small"
              startIcon={<ThumbDownIcon />}
              sx={{ minWidth: 110 }}
              onClick={() => onDecide(item.item_id, 'rejected')}
            >
              Refuser
            </Button>
          </Stack>
        )}
        {item.actionable && submitted && decision && (
          <Chip
            label={decision === 'approved' ? 'Accepté' : 'Refusé'}
            color={decision === 'approved' ? 'success' : 'error'}
            size="small"
          />
        )}
      </Stack>
    </Box>
  )
}

function SectionBlock({
  section,
  decisions,
  onDecide,
  submitted,
}: {
  section: ApprovalPublicSection
  decisions: Record<string, 'approved' | 'rejected'>
  onDecide: (itemId: string, d: 'approved' | 'rejected') => void
  submitted: boolean
}) {
  const actionable = section.items.filter((i) => i.actionable)
  const decided = actionable.filter((i) => decisions[i.item_id])
  return (
    <Paper variant="outlined" sx={{ mb: 2, overflow: 'hidden' }}>
      <Box
        sx={{
          px: 2,
          py: 1,
          bgcolor: '#1e3a5f',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography sx={{ color: '#fff', fontWeight: 600 }}>{section.section_title}</Typography>
        {actionable.length > 0 && (
          <Chip
            label={`${decided.length}/${actionable.length} décidé(s)`}
            size="small"
            sx={{ bgcolor: '#fff', color: '#1e3a5f', fontWeight: 700 }}
          />
        )}
      </Box>
      <Box>
        {section.items.map((item) => (
          <ItemDecisionRow
            key={item.item_id}
            item={item}
            decision={decisions[item.item_id] ?? null}
            onDecide={onDecide}
            submitted={submitted}
          />
        ))}
      </Box>
    </Paper>
  )
}

export function InspectionApprovalPage() {
  const { token } = useParams<{ token: string }>()
  const [decisions, setDecisions] = useState<Record<string, 'approved' | 'rejected'>>({})
  const [submitted, setSubmitted] = useState(false)

  const {
    data: inspection,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['approval', token],
    queryFn: () => inspectionApi.getApprovalData(token!),
    enabled: !!token,
    retry: false,
  })

  const submitMutation = useMutation({
    mutationFn: (decisionList: ApprovalDecision[]) =>
      inspectionApi.submitApproval(token!, decisionList),
    onSuccess: () => setSubmitted(true),
  })

  const handleDecide = (itemId: string, decision: 'approved' | 'rejected') => {
    setDecisions((prev) => ({ ...prev, [itemId]: decision }))
  }

  const actionableItems =
    inspection?.sections.flatMap((s) => s.items.filter((i) => i.actionable)) ?? []
  const allDecided =
    actionableItems.length > 0 && actionableItems.every((i) => decisions[i.item_id])

  const handleSubmit = () => {
    const decisionList: ApprovalDecision[] = Object.entries(decisions).map(([item_id, decision]) => ({
      item_id,
      decision,
    }))
    submitMutation.mutate(decisionList)
  }

  // 410 Gone
  const is410 =
    isError &&
    (error as { response?: { status?: number } })?.response?.status === 410

  // 404
  const is404 =
    isError &&
    (error as { response?: { status?: number } })?.response?.status === 404

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress size={60} />
      </Box>
    )
  }

  if (is410) {
    return (
      <Box maxWidth={600} mx="auto" mt={8} p={3}>
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Lien déjà utilisé
          </Typography>
          Ce lien d'approbation a déjà été utilisé. Contactez votre garage pour obtenir un nouveau
          lien.
        </Alert>
      </Box>
    )
  }

  if (is404 || isError) {
    return (
      <Box maxWidth={600} mx="auto" mt={8} p={3}>
        <Alert severity="warning">
          Lien d'approbation invalide ou expiré. Contactez votre garage.
        </Alert>
      </Box>
    )
  }

  if (submitted) {
    const result = submitMutation.data
    return (
      <Box maxWidth={700} mx="auto" mt={8} p={3}>
        <Alert severity="success" sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Vos choix ont bien été enregistrés
          </Typography>
          {result && (
            <>
              <Typography variant="body2">
                {result.repair_tasks_created} réparation(s) ajoutée(s) à l'ordre de travail.
              </Typography>
              {result.recommendations_archived > 0 && (
                <Typography variant="body2">
                  {result.recommendations_archived} refus archivé(s) sur le dossier véhicule.
                </Typography>
              )}
            </>
          )}
        </Alert>
        <Typography color="text.secondary" textAlign="center">
          Vous pouvez fermer cette page.
        </Typography>
      </Box>
    )
  }

  return (
    <Box maxWidth={760} mx="auto" p={2} pb={12}>
      {/* Header */}
      <Box
        sx={{
          bgcolor: '#1e3a5f',
          color: '#fff',
          borderRadius: 2,
          p: 3,
          mb: 3,
        }}
      >
        <Typography variant="h5" fontWeight={700} gutterBottom>
          Rapport de diagnostic
        </Typography>
        <Typography variant="body2" sx={{ opacity: 0.85 }}>
          {inspection?.template_name}
        </Typography>
      </Box>

      {/* Vehicle / mechanic info */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={3}
          divider={<Divider orientation="vertical" flexItem />}
        >
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Véhicule
            </Typography>
            <Typography fontWeight={600}>{inspection?.vehicle_info}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary" display="block">
              Technicien
            </Typography>
            <Typography fontWeight={600}>{inspection?.mechanic_name}</Typography>
          </Box>
          {inspection?.completed_at && (
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                Date
              </Typography>
              <Typography fontWeight={600}>
                {new Date(inspection.completed_at).toLocaleDateString('fr-FR')}
              </Typography>
            </Box>
          )}
        </Stack>
      </Paper>

      {actionableItems.length > 0 && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Les éléments marqués <strong>À surveiller</strong> ou <strong>Défectueux</strong> nécessitent
          votre décision. Acceptez pour ajouter à l'ordre de réparation, ou refusez pour archiver
          comme recommandation.
        </Alert>
      )}

      {/* Sections */}
      {inspection?.sections.map((section) => (
        <SectionBlock
          key={section.section_id}
          section={section}
          decisions={decisions}
          onDecide={handleDecide}
          submitted={false}
        />
      ))}

      {/* Submit bar */}
      {actionableItems.length > 0 && (
        <Box
          sx={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            p: 2,
            bgcolor: 'background.paper',
            borderTop: 1,
            borderColor: 'divider',
            zIndex: 100,
          }}
        >
          <Stack direction="row" spacing={2} alignItems="center" maxWidth={760} mx="auto">
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              {Object.keys(decisions).length}/{actionableItems.length} éléments décidés
            </Typography>
            <Button
              variant="contained"
              color="primary"
              size="large"
              disabled={!allDecided || submitMutation.isPending}
              onClick={handleSubmit}
              sx={{ minHeight: 52, minWidth: 180 }}
            >
              {submitMutation.isPending ? 'Envoi…' : 'Valider mes choix'}
            </Button>
          </Stack>
          {submitMutation.isError && (
            <Alert severity="error" sx={{ mt: 1 }}>
              Une erreur s'est produite. Veuillez réessayer.
            </Alert>
          )}
        </Box>
      )}
    </Box>
  )
}
