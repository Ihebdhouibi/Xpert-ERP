import { useState, useRef } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import UndoRoundedIcon from '@mui/icons-material/UndoRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import AddPhotoAlternateRoundedIcon from '@mui/icons-material/AddPhotoAlternateRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import BrokenImageRoundedIcon from '@mui/icons-material/BrokenImageRounded'
import SavingsRoundedIcon from '@mui/icons-material/SavingsRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  isBackwardTransition,
  type ROStatus,
  type RepairOrderDetail,
  type ROPartLine,
  type ROLaborLine,
  type Comment,
  type ROPhotoSummary,
  type MechanicSummary,
} from '../../lib/repairOrderApi'
import { customerApi } from '../../lib/customerApi'
import { vehiclesApi } from '../../lib/vehiclesApi'
import { quotationApi } from '../../lib/quotationApi'
import { invoiceApi } from '../../lib/invoiceApi'
import { deliveryNoteApi } from '../../lib/deliveryNoteApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { advancePaymentApi } from '../../lib/advancePaymentApi'
import { PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

// ─── helpers ────────────────────────────────────────────────────────────────

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Basse', normal: 'Normale', high: 'Haute', urgent: 'Urgente',
}
const PRIORITY_COLOR: Record<string, string> = {
  low: '#64748B', normal: '#334155', high: '#F59E0B', urgent: '#EF4444',
}

const SECTION_LABEL_SX = {
  textTransform: 'uppercase' as const,
  letterSpacing: '0.08em',
  display: 'block',
  mb: 2,
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block" mb={0.25}>
        {label}
      </Typography>
      {typeof value === 'string' || typeof value === 'number' ? (
        <Typography variant="body2" fontWeight={500}>{value}</Typography>
      ) : (
        value
      )}
    </Box>
  )
}

// Status accent colors — same palette as Kanban for consistency
const STATUS_ACCENT_COLOR: Record<string, string> = {
  created:      '#94A3B8',
  diagnosis:    '#334155',
  in_repair:    '#F59E0B',
  finished:     '#10B981',
  delivered:    '#6366F1',
  paused_parts: '#EF4444',
}

// ─── Status transition ───────────────────────────────────────────────────────
// Each allowed transition is a quiet pill — flat bg, colored left border,
// muted text. Selected state reveals the confirm step inline.
// Zero competing colors at rest — only the selected pill activates.

function StatusTransitionPanel({
  ro,
  onTransitioned,
}: {
  ro: RepairOrderDetail
  onTransitioned: () => void
}) {
  const { success, error: toastError } = useToast()
  const [selectedStatus, setSelectedStatus] = useState<ROStatus | null>(null)
  const [reason, setReason] = useState('')
  const [backwardTarget, setBackwardTarget] = useState<ROStatus | null>(null)
  const [backwardReason, setBackwardReason] = useState('')
  const allowed = ALLOWED_TRANSITIONS[ro.status]
  const forwardTargets = allowed.filter(s => !isBackwardTransition(ro.status, s))
  const backwardTargets = allowed.filter(s => isBackwardTransition(ro.status, s))

  const mutation = useMutation({
    mutationFn: (vars: { target: ROStatus; reason: string }) =>
      repairOrderApi.transition(ro.id, {
        new_status: vars.target,
        reason: vars.reason || null,
      }),
    onSuccess: (_data, vars) => {
      success(`Statut → ${STATUS_LABELS[vars.target]}`)
      setSelectedStatus(null)
      setReason('')
      setBackwardTarget(null)
      setBackwardReason('')
      onTransitioned()
    },
    onError: (e) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : 'Transition invalide ou accès refusé.')
    },
  })

  // Step preconditions that must be met before moving forward.
  const blockReason = (target: ROStatus): string | null => {
    if (ro.status === 'diagnosis' && target === 'in_repair') {
      if (!ro.assigned_user_id) return "Affectez d'abord un mécanicien."
      if (!ro.assignment_accepted_at) return "L'affectation doit être acceptée."
      if (!ro.diagnosis_completed_at) return 'Terminez le diagnostic.'
    }
    return null
  }

  if (allowed.length === 0) return null

  return (
    <Box>
      <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" mb={1.5}>
        Changer le statut
      </Typography>
      <Stack spacing={0.75}>
        {forwardTargets.map(s => {
          const accent = STATUS_ACCENT_COLOR[s] ?? '#94A3B8'
          const isSelected = selectedStatus === s
          return (
            <Box key={s}>
              {/* Quiet pill — left accent border, flat background */}
              <Box
                onClick={() => setSelectedStatus(isSelected ? null : s)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.25,
                  px: 1.5,
                  py: 1,
                  borderRadius: 1.5,
                  border: '1px solid',
                  borderLeft: `3px solid ${accent}`,
                  borderColor: isSelected ? accent : '#E2E8F0',
                  borderLeftColor: accent,
                  bgcolor: isSelected ? `${accent}10` : '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    borderColor: accent,
                    bgcolor: `${accent}08`,
                  },
                }}
              >
                <Box
                  sx={{
                    width: 8, height: 8,
                    borderRadius: '50%',
                    bgcolor: accent,
                    flexShrink: 0,
                  }}
                />
                <Typography
                  variant="body2"
                  fontWeight={isSelected ? 600 : 500}
                  color={isSelected ? 'text.primary' : 'text.secondary'}
                  flex={1}
                >
                  {STATUS_LABELS[s]}
                </Typography>
                <ArrowForwardRoundedIcon
                  sx={{
                    fontSize: 14,
                    color: isSelected ? accent : '#CBD5E1',
                    transition: 'color 0.15s',
                  }}
                />
              </Box>

              {/* Inline confirm step — expands below the selected pill */}
              {isSelected && (
                <Box
                  sx={{
                    mt: 0.75,
                    ml: 0.5,
                    pl: 1.5,
                    borderLeft: `2px solid ${accent}40`,
                  }}
                >
                  <TextField
                    size="small"
                    fullWidth
                    placeholder="Motif (optionnel)"
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    sx={{ mb: 1 }}
                  />
                  {blockReason(s) && (
                    <Typography variant="caption" color="error" display="block" mb={1}>
                      {blockReason(s)}
                    </Typography>
                  )}
                  <Button
                    variant="contained"
                    fullWidth
                    size="small"
                    disabled={mutation.isPending || blockReason(s) !== null}
                    onClick={() => mutation.mutate({ target: s, reason })}
                    sx={{
                      background: accent,
                      '&:hover': { background: accent, opacity: 0.9 },
                      fontWeight: 600,
                    }}
                  >
                    {mutation.isPending ? 'En cours…' : `Confirmer → ${STATUS_LABELS[s]}`}
                  </Button>
                </Box>
              )}
            </Box>
          )
        })}
      </Stack>

      {backwardTargets.length > 0 && (
        <>
          <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" mt={2} mb={1}>
            Revenir en arrière
          </Typography>
          <Stack spacing={0.75}>
            {backwardTargets.map(s => (
              <Box
                key={s}
                onClick={() => { setBackwardReason(''); setBackwardTarget(s) }}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.25,
                  px: 1.5,
                  py: 1,
                  borderRadius: 1.5,
                  border: '1px dashed #CBD5E1',
                  bgcolor: '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  '&:hover': { borderColor: '#94A3B8', bgcolor: '#F1F5F9' },
                }}
              >
                <UndoRoundedIcon sx={{ fontSize: 16, color: '#94A3B8' }} />
                <Typography variant="body2" fontWeight={500} color="text.secondary" flex={1}>
                  Revenir à {STATUS_LABELS[s]}
                </Typography>
              </Box>
            ))}
          </Stack>
        </>
      )}

      <ConfirmDialog
        open={backwardTarget !== null}
        title={backwardTarget ? `Revenir à « ${STATUS_LABELS[backwardTarget]} » ?` : ''}
        message="Cette action ramène l'ordre de réparation à une étape précédente. Si des pièces avaient été engagées, le stock correspondant sera remis en réservation. Merci d'indiquer le motif de ce retour."
        confirmLabel="Confirmer le retour"
        dangerous
        loading={mutation.isPending}
        confirmDisabled={!backwardReason.trim()}
        onConfirm={() => backwardTarget && mutation.mutate({ target: backwardTarget, reason: backwardReason })}
        onCancel={() => { setBackwardTarget(null); setBackwardReason('') }}
      >
        <TextField
          size="small"
          fullWidth
          required
          autoFocus
          placeholder="Motif du retour (obligatoire)"
          value={backwardReason}
          onChange={e => setBackwardReason(e.target.value)}
          sx={{ mt: 2 }}
        />
      </ConfirmDialog>
    </Box>
  )
}

// ─── Diagnosis ───────────────────────────────────────────────────────────────

const DIAGNOSIS_QUESTIONS: { code: string; label: string }[] = [
  { code: 'D1', label: 'Problème au niveau de la motorisation (moteur)' },
  { code: 'D2', label: 'Problème au niveau du freinage' },
  { code: 'D3', label: "Problème de transmission / embrayage" },
  { code: 'D4', label: 'Problème électrique ou électronique' },
  { code: 'D5', label: 'Problème de suspension / direction' },
]

function DiagnosisPanel({ ro, onUpdated }: { ro: RepairOrderDetail; onUpdated: () => void }) {
  const { success, error: toastError } = useToast()
  const [answers, setAnswers] = useState<Record<string, boolean>>(
    () => ro.diagnosis?.answers ?? {},
  )
  const [notes, setNotes] = useState(ro.diagnosis?.notes ?? '')
  const completed = ro.diagnosis_completed_at !== null
  const [editing, setEditing] = useState(false)
  const allAnswered = DIAGNOSIS_QUESTIONS.every((q) => answers[q.code] !== undefined)
  const locked = completed && !editing

  const save = useMutation({
    mutationFn: (finish: boolean) =>
      repairOrderApi.saveDiagnosis(ro.id, { answers, notes: notes || null, completed: finish }),
    onSuccess: (_d, finish) => {
      success(finish ? 'Diagnostic terminé.' : 'Diagnostic enregistré.')
      setEditing(false)
      onUpdated()
    },
    onError: () => toastError("Impossible d'enregistrer le diagnostic."),
  })

  const cancelEdit = () => {
    setAnswers(ro.diagnosis?.answers ?? {})
    setNotes(ro.diagnosis?.notes ?? '')
    setEditing(false)
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
        <Typography variant="subtitle1" fontWeight={700}>
          Diagnostic
        </Typography>
        {completed && (
          <Chip
            size="small"
            color="success"
            label={`Terminé le ${new Date(ro.diagnosis_completed_at!).toLocaleDateString('fr-FR')}`}
          />
        )}
      </Stack>

      <Stack spacing={1.5}>
        {DIAGNOSIS_QUESTIONS.map((q) => (
          <Stack
            key={q.code}
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            spacing={2}
          >
            <Typography variant="body2">
              <strong>{q.code}</strong> — {q.label}
            </Typography>
            <ToggleButtonGroup
              exclusive
              size="small"
              disabled={locked}
              value={answers[q.code] === undefined ? null : answers[q.code]}
              onChange={(_e, v) => {
                if (v === null) return
                setAnswers((prev) => ({ ...prev, [q.code]: v }))
              }}
            >
              <ToggleButton value={true} color="error" sx={{ textTransform: 'none', px: 2 }}>
                Oui
              </ToggleButton>
              <ToggleButton value={false} color="success" sx={{ textTransform: 'none', px: 2 }}>
                Non
              </ToggleButton>
            </ToggleButtonGroup>
          </Stack>
        ))}
      </Stack>

      <TextField
        label="Observations (optionnel)"
        multiline
        minRows={2}
        fullWidth
        size="small"
        disabled={locked}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        sx={{ mt: 2 }}
      />

      {locked ? (
        <Stack alignItems="flex-end" spacing={0.5} mt={2}>
          {ro.status !== 'diagnosis' && (
            <Typography variant="caption" color="text.secondary">
              Diagnostic déjà utilisé — modifier peut désynchroniser le devis ou la réparation en cours.
            </Typography>
          )}
          <Button
            variant="outlined"
            size="small"
            onClick={() => setEditing(true)}
            sx={{ textTransform: 'none', fontWeight: 600 }}
          >
            Modifier
          </Button>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1.5} justifyContent="flex-end" mt={2}>
          {completed ? (
            <>
              <Button
                variant="text"
                size="small"
                disabled={save.isPending}
                onClick={cancelEdit}
                sx={{ textTransform: 'none', fontWeight: 600 }}
              >
                Annuler
              </Button>
              <Tooltip title={allAnswered ? '' : 'Répondez à toutes les questions (D1 à D5).'}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={save.isPending || !allAnswered}
                    onClick={() => save.mutate(true)}
                    sx={{ textTransform: 'none', fontWeight: 700 }}
                  >
                    Enregistrer les modifications
                  </Button>
                </span>
              </Tooltip>
            </>
          ) : (
            <>
              <Button
                variant="outlined"
                size="small"
                disabled={save.isPending}
                onClick={() => save.mutate(false)}
                sx={{ textTransform: 'none', fontWeight: 600 }}
              >
                Enregistrer
              </Button>
              <Tooltip title={allAnswered ? '' : 'Répondez à toutes les questions (D1 à D5).'}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={save.isPending || !allAnswered}
                    onClick={() => save.mutate(true)}
                    sx={{ textTransform: 'none', fontWeight: 700 }}
                  >
                    Terminer le diagnostic
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
        </Stack>
      )}
    </Box>
  )
}

// ─── Mechanic assignment ─────────────────────────────────────────────────────

function MechanicPanel({ ro, onUpdated }: { ro: RepairOrderDetail; onUpdated: () => void }) {
  const { success, error: toastError } = useToast()
  const [selected, setSelected] = useState<number | ''>(ro.assigned_user_id ?? '')

  const { data: mechanics } = useQuery<MechanicSummary[]>({
    queryKey: ['mechanics'],
    queryFn: () => repairOrderApi.listMechanics(),
  })

  const assignMutation = useMutation({
    mutationFn: () =>
      repairOrderApi.assignMechanic(ro.id, selected === '' ? null : Number(selected)),
    onSuccess: () => {
      success('Mécanicien assigné. Notification envoyée.')
      onUpdated()
    },
    onError: () => toastError("Impossible d'assigner le mécanicien."),
  })

  const acceptMutation = useMutation({
    mutationFn: () => repairOrderApi.acceptAssignment(ro.id),
    onSuccess: () => {
      success('Affectation acceptée.')
      onUpdated()
    },
    onError: () => toastError("Impossible d'accepter l'affectation."),
  })

  const changed = (selected === '' ? null : Number(selected)) !== ro.assigned_user_id

  return (
    <Box>
      <Typography variant="caption" fontWeight={700} color="text.secondary" sx={SECTION_LABEL_SX}>
        Mécanicien
      </Typography>

      <FormControl fullWidth size="small" sx={{ mb: 1 }}>
        <InputLabel>Affecter à</InputLabel>
        <Select
          label="Affecter à"
          value={selected}
          onChange={(e) => setSelected(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <MenuItem value="">
            <em>Non affecté</em>
          </MenuItem>
          {(mechanics ?? []).map((m) => (
            <MenuItem key={m.id} value={m.id}>
              {m.name}
              {m.active_orders > 0
                ? ` · ${m.active_orders} OR en cours`
                : ' · disponible'}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {changed && (
        <Button
          variant="contained"
          size="small"
          fullWidth
          disabled={assignMutation.isPending}
          onClick={() => assignMutation.mutate()}
          sx={{ textTransform: 'none', fontWeight: 700, mb: 1 }}
        >
          {assignMutation.isPending ? <CircularProgress size={18} /> : 'Assigner'}
        </Button>
      )}

      {ro.assigned_user_id && (
        <Box sx={{ mt: 0.5 }}>
          {ro.assignment_accepted_at ? (
            <Chip
              size="small"
              color="success"
              label={`Accepté le ${new Date(ro.assignment_accepted_at).toLocaleString('fr-FR')}`}
            />
          ) : (
            <Stack spacing={1}>
              <Chip size="small" color="warning" label="En attente d'acceptation" />
              <Button
                variant="outlined"
                size="small"
                fullWidth
                disabled={acceptMutation.isPending || changed}
                onClick={() => acceptMutation.mutate()}
                sx={{ textTransform: 'none', fontWeight: 600 }}
              >
                Accepter l'affectation
              </Button>
            </Stack>
          )}
        </Box>
      )}
    </Box>
  )
}

// ─── Status timeline ─────────────────────────────────────────────────────────

function StatusTimeline({ events }: { events: RepairOrderDetail['status_events'] }) {
  if (events.length === 0) {
    return <Typography variant="body2" color="text.secondary">Aucun historique.</Typography>
  }
  return (
    <Stack spacing={0}>
      {events.map((evt, i) => (
        <Stack key={evt.id} direction="row" spacing={1.5} sx={{ position: 'relative', pb: i < events.length - 1 ? 2 : 0 }}>
          {i < events.length - 1 && (
            <Box sx={{ position: 'absolute', left: 6, top: 16, width: 2, bottom: 0, bgcolor: '#E2E8F0', zIndex: 0 }} />
          )}
          <Box
            sx={{
              width: 14, height: 14, borderRadius: '50%',
              bgcolor: i === 0 ? 'primary.main' : '#94A3B8',
              flexShrink: 0, mt: 0.3, zIndex: 1,
              border: '2px solid white',
              boxShadow: i === 0 ? '0 0 0 2px #1E293B' : '0 0 0 2px #94A3B8',
            }}
          />
          <Box>
            <Stack direction="row" alignItems="center" spacing={0.5} flexWrap="wrap">
              {evt.old_status && (
                <>
                  <Typography variant="caption" color="text.secondary">
                    {STATUS_LABELS[evt.old_status as ROStatus] ?? evt.old_status}
                  </Typography>
                  <ArrowForwardRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
                </>
              )}
              <Typography variant="caption" fontWeight={700} color={i === 0 ? 'primary.main' : 'text.primary'}>
                {STATUS_LABELS[evt.new_status as ROStatus] ?? evt.new_status}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.disabled" display="block">
              {new Date(evt.occurred_at).toLocaleString('fr-FR')}
            </Typography>
          </Box>
        </Stack>
      ))}
    </Stack>
  )
}

// ─── Comments ────────────────────────────────────────────────────────────────

function CommentsPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const { error: toastError } = useToast()
  const [newBody, setNewBody] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editBody, setEditBody] = useState('')

  const { data } = useQuery({
    queryKey: ['comments', publicId],
    queryFn: () => repairOrderApi.listComments(publicId),
  })

  const createMutation = useMutation({
    mutationFn: () => repairOrderApi.createComment(publicId, newBody),
    onSuccess: () => {
      setNewBody('')
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => toastError("Impossible d'ajouter le commentaire."),
  })

  const updateMutation = useMutation({
    mutationFn: (comment: Comment) =>
      repairOrderApi.updateComment(publicId, comment.id, editBody),
    onSuccess: () => {
      setEditingId(null)
      setEditBody('')
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => toastError('Impossible de modifier le commentaire.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (commentId: number) => repairOrderApi.deleteComment(publicId, commentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['comments', publicId] }),
    onError: () => toastError('Impossible de supprimer le commentaire.'),
  })

  return (
    <Box>
      <Stack spacing={1.5} mb={2} sx={{ maxHeight: 400, overflowY: 'auto' }}>
        {data?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Aucun commentaire pour l'instant.
          </Typography>
        )}
        {data?.items.map(comment => (
          <Box
            key={comment.id}
            sx={{ p: 1.5, bgcolor: '#F8FAFC', borderRadius: 1.5, border: '1px solid #E2E8F0' }}
          >
            {editingId === comment.id ? (
              <Stack spacing={1}>
                <TextField size="small" multiline fullWidth value={editBody} onChange={e => setEditBody(e.target.value)} />
                <Stack direction="row" spacing={1} justifyContent="flex-end">
                  <Button size="small" variant="outlined" onClick={() => setEditingId(null)}>Annuler</Button>
                  <Button
                    size="small"
                    variant="contained"
                    disabled={updateMutation.isPending || !editBody.trim()}
                    onClick={() => updateMutation.mutate(comment)}
                  >
                    Sauvegarder
                  </Button>
                </Stack>
              </Stack>
            ) : (
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                <Box flex={1}>
                  <Typography variant="body2" whiteSpace="pre-wrap">{comment.body}</Typography>
                  <Typography variant="caption" color="text.disabled">
                    {new Date(comment.created_at).toLocaleString('fr-FR')}
                    {comment.created_at !== comment.updated_at && ' · modifié'}
                  </Typography>
                </Box>
                <Stack direction="row" flexShrink={0}>
                  <Tooltip title="Modifier">
                    <IconButton
                      size="small"
                      onClick={() => { setEditingId(comment.id); setEditBody(comment.body) }}
                    >
                      <EditRoundedIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Supprimer">
                    <IconButton
                      size="small"
                      color="error"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(comment.id)}
                    >
                      <DeleteRoundedIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            )}
          </Box>
        ))}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="flex-end">
        <TextField
          size="small"
          multiline
          fullWidth
          placeholder="Ajouter un commentaire… (Ctrl+Entrée pour envoyer)"
          value={newBody}
          onChange={e => setNewBody(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && newBody.trim()) {
              createMutation.mutate()
            }
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<SendRoundedIcon />}
          disabled={createMutation.isPending || !newBody.trim()}
          onClick={() => createMutation.mutate()}
          sx={{ height: 40, flexShrink: 0, textTransform: 'none', fontWeight: 700 }}
        >
          Envoyer
        </Button>
      </Stack>
    </Box>
  )
}

// ─── Photos ──────────────────────────────────────────────────────────────────

function PhotosPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const { error: toastError } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [brokenIds, setBrokenIds] = useState<Set<number>>(new Set())

  const { data } = useQuery({
    queryKey: ['photos', publicId],
    queryFn: () => repairOrderApi.listPhotos(publicId),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => repairOrderApi.uploadPhoto(publicId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['photos', publicId] }),
    onError: () => toastError("Impossible d'envoyer la photo."),
  })

  function handleFiles(files: FileList | null) {
    if (!files) return
    Array.from(files).forEach(f => uploadMutation.mutate(f))
  }

  const photos: ROPhotoSummary[] = data?.items ?? []

  return (
    <Box>
      {photos.length === 0 && !uploadMutation.isPending && (
        <Typography variant="body2" color="text.secondary" mb={2}>
          Aucune photo pour l'instant.
        </Typography>
      )}

      {photos.length > 0 && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 1,
            mb: 2,
          }}
        >
          {photos.map(photo => (
            <Box
              key={photo.id}
              component="a"
              href={photo.url}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'block',
                aspectRatio: '1',
                borderRadius: 1,
                overflow: 'hidden',
                bgcolor: '#F1F5F9',
                border: '1px solid #E2E8F0',
                '&:hover': { opacity: 0.85 },
              }}
            >
              {brokenIds.has(photo.id) ? (
                <Box
                  sx={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <BrokenImageRoundedIcon sx={{ color: '#CBD5E1', fontSize: 32 }} />
                </Box>
              ) : photo.mime_type?.startsWith('video/') ? (
                <video
                  src={photo.url}
                  muted
                  preload="metadata"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              ) : (
                <img
                  src={photo.url}
                  alt={photo.filename}
                  onError={() => setBrokenIds(prev => new Set(prev).add(photo.id))}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              )}
            </Box>
          ))}
        </Box>
      )}

      <PermissionGate permission="repair_order.media.upload">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,video/mp4,video/quicktime,video/webm"
          multiple
          style={{ display: 'none' }}
          onChange={e => handleFiles(e.target.files)}
        />
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddPhotoAlternateRoundedIcon />}
          disabled={uploadMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
          sx={{ textTransform: 'none', fontWeight: 600 }}
        >
          {uploadMutation.isPending ? 'Envoi…' : 'Ajouter photos/vidéos'}
        </Button>
      </PermissionGate>
    </Box>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export function RepairOrderDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  // Advance payment dialog state
  const [advanceOpen, setAdvanceOpen] = useState(false)
  const [advanceAmount, setAdvanceAmount] = useState('')
  const [advanceMethod, setAdvanceMethod] = useState<PaymentMethod>('cash')
  const [advanceRef, setAdvanceRef] = useState('')

  // Add-labor inline form state
  const [showAddLabor, setShowAddLabor] = useState(false)
  const [laborType, setLaborType] = useState('')
  const [laborRate, setLaborRate] = useState('')

  // Add-part inline form state
  const [showAddPart, setShowAddPart] = useState(false)
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | 'none' | null>(null)
  const [selectedPart, setSelectedPart] = useState<PartSummary | null>(null)
  const [partQty, setPartQty] = useState('')
  const [partUnitPrice, setPartUnitPrice] = useState('')
  const [partRemise, setPartRemise] = useState('0')
  const [newPartPrice, setNewPartPrice] = useState('')

  // Edit/delete labor line state
  const [editLaborLineId, setEditLaborLineId] = useState<number | null>(null)
  const [editLaborType, setEditLaborType] = useState('')
  const [editLaborRate, setEditLaborRate] = useState('')
  const [deleteLaborLineId, setDeleteLaborLineId] = useState<number | null>(null)

  // Edit/delete part line state
  const [editPartLineId, setEditPartLineId] = useState<number | null>(null)
  const [editPartQty, setEditPartQty] = useState('')
  const [editPartUnitPrice, setEditPartUnitPrice] = useState('')
  const [editPartRemise, setEditPartRemise] = useState('0')
  const [deletePartLineId, setDeletePartLineId] = useState<number | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['repair-order', publicId],
    queryFn: () => repairOrderApi.get(publicId),
    enabled: !!publicId,
    // Poll so changes from other users (e.g. a mechanic accepting) appear live.
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  })

  const roForQueries = data

  const { data: customer } = useQuery({
    queryKey: ['customer-by-int-id', roForQueries?.customer_id],
    queryFn: () => customerApi.getByIntId(roForQueries!.customer_id),
    enabled: !!roForQueries?.customer_id,
    staleTime: 5 * 60 * 1000,
  })

  const { data: vehicle } = useQuery({
    queryKey: ['vehicle', roForQueries?.vehicle_id],
    queryFn: () => vehiclesApi.get(roForQueries!.vehicle_id!),
    enabled: !!roForQueries?.vehicle_id,
    staleTime: 5 * 60 * 1000,
  })

  const { data: partCategories } = useQuery({
    queryKey: ['part-categories'],
    queryFn: () => partsApi.listCategories(),
    enabled: showAddPart,
    staleTime: 5 * 60 * 1000,
  })

  const { data: partsResults } = useQuery({
    queryKey: ['parts-by-category', selectedCategoryId],
    queryFn: () => selectedCategoryId === 'none'
      ? partsApi.list({ uncategorized: true, page_size: 200, status: 'active' })
      : partsApi.list({ category_id: selectedCategoryId!, page_size: 200, status: 'active' }),
    enabled: showAddPart && selectedCategoryId !== null,
    staleTime: 30_000,
  })

  const { data: advancesData } = useQuery({
    queryKey: ['advance-payments', 'customer', roForQueries?.customer_id],
    queryFn: () => advancePaymentApi.listByCustomer(roForQueries!.customer_id),
    enabled: !!roForQueries?.customer_id,
    staleTime: 60_000,
  })

  const createDevisMutation = useMutation({
    mutationFn: () => quotationApi.fromRepairOrder(publicId),
    onSuccess: (quotation) => {
      success('Devis créé avec succès.')
      navigate(`/quotations/${quotation.public_id}`)
    },
    onError: () => toastError('Impossible de créer le devis.'),
  })

  const createInvoiceMutation = useMutation({
    mutationFn: () => invoiceApi.fromRepairOrder(publicId),
    onSuccess: (invoice) => {
      success('Facture créée avec succès.')
      navigate(`/invoices/${invoice.public_id}`)
    },
    onError: () => toastError('Impossible de créer la facture.'),
  })

  const createDeliveryNoteMutation = useMutation({
    mutationFn: () => deliveryNoteApi.fromRepairOrder(publicId),
    onSuccess: (deliveryNote) => {
      success('Bon de livraison créé avec succès.')
      navigate(`/delivery-notes/${deliveryNote.public_id}`)
    },
    onError: () => toastError('Impossible de créer le bon de livraison.'),
  })

  const addLaborMutation = useMutation({
    mutationFn: () => repairOrderApi.addLaborLine(publicId, {
      labor_type: laborType,
      rate_minor: Math.round(parseFloat(laborRate) * 100),
    }),
    onSuccess: () => {
      success('Ligne de main d\'œuvre ajoutée.')
      setShowAddLabor(false)
      setLaborType(''); setLaborRate('')
      refetch()
    },
    onError: () => toastError('Impossible d\'ajouter la ligne.'),
  })

  const addPartMutation = useMutation({
    mutationFn: () => repairOrderApi.addPartLine(publicId, {
      part_name: selectedPart!.name,
      quantity: parseInt(partQty, 10),
      unit_cost_minor: Math.round(parseFloat(partUnitPrice) * 100),
      part_public_id: selectedPart!.id,
      remise_pct: parseFloat(partRemise) || 0,
    }),
    onSuccess: () => {
      success('Pièce ajoutée.')
      setShowAddPart(false)
      setSelectedPart(null); setSelectedCategoryId(null); setPartQty('')
      setPartUnitPrice(''); setPartRemise('0')
      refetch()
    },
    onError: () => toastError('Impossible d\'ajouter la pièce.'),
  })

  const setPartPriceMutation = useMutation({
    mutationFn: () => partsApi.update(selectedPart!.id, selectedPart!.version, {
      selling_price_minor: Math.round((parseFloat(newPartPrice) || 0) * 100),
    }),
    onSuccess: (updated) => {
      success('Prix de la pièce mis à jour.')
      setSelectedPart(updated)
      setPartUnitPrice((updated.selling_price_minor / 100).toFixed(2))
      setNewPartPrice('')
      queryClient.invalidateQueries({ queryKey: ['parts-by-category', selectedCategoryId] })
    },
    onError: () => toastError('Impossible de mettre à jour le prix de la pièce.'),
  })

  const updateLaborLineMutation = useMutation({
    mutationFn: () => repairOrderApi.updateLaborLine(publicId, editLaborLineId!, {
      labor_type: editLaborType,
      rate_minor: Math.round(parseFloat(editLaborRate) * 100),
    }),
    onSuccess: () => {
      success('Ligne de main d\'œuvre modifiée.')
      setEditLaborLineId(null)
      refetch()
    },
    onError: () => toastError('Impossible de modifier la ligne.'),
  })

  const removeLaborLineMutation = useMutation({
    mutationFn: (lineId: number) => repairOrderApi.removeLaborLine(publicId, lineId),
    onSuccess: () => {
      success('Ligne de main d\'œuvre supprimée.')
      setDeleteLaborLineId(null)
      refetch()
    },
    onError: () => { toastError('Impossible de supprimer la ligne.'); setDeleteLaborLineId(null) },
  })

  const updatePartLineMutation = useMutation({
    mutationFn: () => repairOrderApi.updatePartLine(publicId, editPartLineId!, {
      quantity: parseInt(editPartQty, 10),
      unit_cost_minor: Math.round(parseFloat(editPartUnitPrice) * 100),
      remise_pct: parseFloat(editPartRemise) || 0,
    }),
    onSuccess: () => {
      success('Pièce modifiée.')
      setEditPartLineId(null)
      refetch()
    },
    onError: () => toastError('Impossible de modifier la pièce.'),
  })

  const removePartLineMutation = useMutation({
    mutationFn: (lineId: number) => repairOrderApi.removePartLine(publicId, lineId),
    onSuccess: () => {
      success('Pièce supprimée.')
      setDeletePartLineId(null)
      refetch()
    },
    onError: () => { toastError('Impossible de supprimer la pièce.'); setDeletePartLineId(null) },
  })

  function openEditLaborLine(line: ROLaborLine) {
    setEditLaborLineId(line.id)
    setEditLaborType(line.labor_type)
    setEditLaborRate((line.rate_minor / 100).toFixed(2))
  }

  function openEditPartLine(line: ROPartLine) {
    setEditPartLineId(line.id)
    setEditPartQty(String(line.quantity))
    setEditPartUnitPrice((line.unit_cost_minor / 100).toFixed(2))
    setEditPartRemise(String(line.remise_pct))
  }

  const createAdvanceMutation = useMutation({
    mutationFn: () =>
      advancePaymentApi.create({
        customer_id: data!.customer_id,
        repair_order_id: data!.int_id,
        amount_minor: Math.round(parseFloat(advanceAmount) * 100),
        payment_method: advanceMethod,
        reference: advanceRef || null,
      }),
    onSuccess: () => {
      success('Acompte enregistré avec succès.')
      setAdvanceOpen(false)
      setAdvanceAmount(''); setAdvanceMethod('cash'); setAdvanceRef('')
      queryClient.invalidateQueries({ queryKey: ['advance-payments', 'customer', roForQueries?.customer_id] })
    },
    onError: () => toastError("Erreur lors de l'enregistrement de l'acompte."),
  })

  const handleDelete = async () => {
    try {
      await repairOrderApi.remove(publicId)
      await queryClient.invalidateQueries({ queryKey: ['repair-orders'] })
      navigate('/repair-orders', { replace: true })
    } catch {
      toastError('Erreur lors de la suppression.')
      setConfirmDelete(false)
    }
  }

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const { url } = await repairOrderApi.getPdfUrl(publicId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      toastError('Erreur lors de la génération du PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) {
    return <LoadingScreen message="Chargement de l'ordre de réparation…" />
  }
  if (isError || !data) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>Impossible de charger cet ordre de réparation.</Alert>
        <Button variant="outlined" onClick={() => navigate('/repair-orders')}>
          ← Retour à la liste
        </Button>
      </Box>
    )
  }

  const ro = data as RepairOrderDetail
  const currency = ro.estimated_cost_currency ?? 'EUR'
  const laborTotal = ro.labor_lines.reduce((s, l) => s + (l.amount_minor ?? 0), 0)
  const partsTotal = ro.part_lines.reduce((s, l) => s + (l.amount_minor ?? 0), 0)
  const canEditLaborLines = ro.status === 'diagnosis' || ro.status === 'in_repair'
  const canEditPartLines = ro.status === 'paused_parts'
  const pendingAdvances = (advancesData?.items ?? []).filter(a => a.applied_to_invoice_id === null)
  const pendingAdvancesTotal = pendingAdvances.reduce((s, a) => s + a.amount_minor, 0)

  return (
    <Box>
      <PageHeader
        title={ro.description || 'Ordre de réparation'}
        subtitle={`#${String(ro.id).slice(-8).toUpperCase()} · Créé le ${new Date(ro.created_at).toLocaleDateString('fr-FR')}`}
        breadcrumbs={[
          { label: 'Ordres de réparation', href: '/repair-orders' },
          { label: ro.description || 'Détail' },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              Étape actuelle :
            </Typography>
            <StatusChip status={ro.status} label={STATUS_LABELS[ro.status]} size="medium" />
            <PermissionGate permission="repair_order.read">
              <Button
                size="small"
                variant="outlined"
                startIcon={<PictureAsPdfRoundedIcon />}
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
                sx={{ textTransform: 'none' }}
              >
                {pdfLoading ? 'Génération…' : 'PDF'}
              </Button>
            </PermissionGate>
            <PermissionGate permission="repair_order.update">
              <Button
                size="small"
                variant="outlined"
                startIcon={<EditRoundedIcon />}
                component={RouterLink}
                to={`/repair-orders/${ro.id}/edit`}
                sx={{ textTransform: 'none' }}
              >
                Modifier
              </Button>
            </PermissionGate>
            <PermissionGate permission="repair_order.delete">
              <Button
                size="small"
                color="error"
                variant="outlined"
                startIcon={<DeleteRoundedIcon />}
                onClick={() => setConfirmDelete(true)}
                sx={{ textTransform: 'none' }}
              >
                Supprimer
              </Button>
            </PermissionGate>
          </Stack>
        }
      />

      <Grid container spacing={3}>
        {/* ── LEFT COLUMN ─────────────────────────────────────────────── */}
        <Grid item xs={12} md={8}>

          {/* Key info */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="caption" fontWeight={700} color="text.secondary" sx={SECTION_LABEL_SX}>
                Informations
              </Typography>
              <Grid container spacing={2.5}>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Client"
                    value={
                      customer ? (
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          component={RouterLink}
                          to={`/customers/${customer.id}`}
                          sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                        >
                          {customer.full_name}
                        </Typography>
                      ) : (ro.customer_name ?? `#${ro.customer_id}`)
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Véhicule"
                    value={
                      vehicle ? (
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          component={RouterLink}
                          to={`/vehicles/${vehicle.id}`}
                          sx={{ color: 'primary.main', textDecoration: 'none', fontFamily: 'monospace', '&:hover': { textDecoration: 'underline' } }}
                        >
                          {[vehicle.registration, `${vehicle.make} ${vehicle.model}`].filter(Boolean).join(' — ')}
                        </Typography>
                      ) : ro.vehicle_id ? `#${ro.vehicle_id}` : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Priorité"
                    value={
                      ro.priority ? (
                        <Typography
                          variant="body2"
                          fontWeight={700}
                          sx={{ color: PRIORITY_COLOR[ro.priority] ?? 'text.primary' }}
                        >
                          {PRIORITY_LABEL[ro.priority] ?? ro.priority}
                        </Typography>
                      ) : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField label="Version" value={`v${ro.version}`} />
                </Grid>
                <Grid item xs={6} sm={4}>
                  <InfoField
                    label="Coût estimé"
                    value={
                      ro.estimated_cost_minor != null
                        ? <Typography variant="body2" fontWeight={600}>{formatMinor(ro.estimated_cost_minor, currency)}</Typography>
                        : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={4}>
                  <InfoField
                    label="Coût réel"
                    value={
                      ro.actual_cost_minor != null
                        ? <Typography variant="body2" fontWeight={700} color="primary.main">{formatMinor(ro.actual_cost_minor, currency)}</Typography>
                        : '—'
                    }
                  />
                </Grid>
              </Grid>

              {ro.notes && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Notes
                  </Typography>
                  <Typography variant="body2" color="text.secondary" whiteSpace="pre-wrap">
                    {ro.notes}
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>

          {/* Diagnosis (during the diagnosis step) */}
          {ro.status === 'diagnosis' && (
            <PermissionGate permission="repair_order.transition">
              <Card sx={{ mb: 3 }}>
                <CardContent sx={{ p: 3 }}>
                  <DiagnosisPanel ro={ro} onUpdated={() => refetch()} />
                </CardContent>
              </Card>
            </PermissionGate>
          )}

          {/* Labor lines */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 0 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 3, py: 2 }}>
                <Typography variant="subtitle2" fontWeight={700}>
                  Main d'œuvre
                  <Typography component="span" variant="caption" color="text.secondary" ml={1} fontWeight={400}>
                    {ro.labor_lines.length} ligne{ro.labor_lines.length !== 1 ? 's' : ''}
                  </Typography>
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" fontWeight={700} color={laborTotal > 0 ? 'text.primary' : 'text.disabled'}>
                    {formatMinor(laborTotal, currency)}
                  </Typography>
                  {(ro.status === 'diagnosis' || ro.status === 'in_repair') && (
                    <PermissionGate permission="repair_order.transition">
                      <Button size="small" variant="outlined" startIcon={<AddRoundedIcon />} onClick={() => setShowAddLabor(v => !v)} sx={{ textTransform: 'none', fontWeight: 600, fontSize: 12 }}>
                        Ajouter
                      </Button>
                    </PermissionGate>
                  )}
                </Stack>
              </Stack>
              {showAddLabor && (
                <Box sx={{ px: 3, pb: 2 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} mb={1} alignItems="center">
                    <TextField size="small" label="Désignation" value={laborType} onChange={e => setLaborType(e.target.value)} sx={{ flex: 2 }} />
                    <TextField size="small" label="Prix HT (€)" type="number" value={laborRate} onChange={e => setLaborRate(e.target.value)} inputProps={{ min: 0, step: 0.01 }} sx={{ flex: 1 }} />
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, whiteSpace: 'nowrap' }}>
                      <Typography variant="caption" color="text.secondary">TVA&nbsp;20%</Typography>
                    </Box>
                    {laborRate && parseFloat(laborRate) > 0 && (
                      <Box sx={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
                        <Typography variant="body2" color="text.secondary">Total TTC :&nbsp;</Typography>
                        <Typography variant="body2" fontWeight={700}>
                          {(parseFloat(laborRate) * 1.20).toFixed(2)} €
                        </Typography>
                      </Box>
                    )}
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => setShowAddLabor(false)} sx={{ textTransform: 'none' }}>Annuler</Button>
                    <Button
                      size="small" variant="contained"
                      disabled={addLaborMutation.isPending || !laborType.trim() || !laborRate}
                      onClick={() => addLaborMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {addLaborMutation.isPending ? 'Enregistrement…' : 'Ajouter'}
                    </Button>
                  </Stack>
                </Box>
              )}
              <Divider />
              {ro.labor_lines.length === 0 ? (
                <Box sx={{ px: 3, py: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">Aucune ligne de main d'œuvre.</Typography>
                </Box>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Désignation</TableCell>
                      <TableCell align="right">Prix HT</TableCell>
                      <TableCell align="right">TVA</TableCell>
                      <TableCell align="right">Montant TTC</TableCell>
                      {canEditLaborLines && <TableCell align="right">Actions</TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ro.labor_lines.map(line => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>{line.labor_type}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{formatMinor(line.rate_minor, currency)}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" color="text.secondary">20%</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontWeight={600}>{formatMinor(line.amount_minor, currency)}</Typography>
                        </TableCell>
                        {canEditLaborLines && (
                          <TableCell align="right">
                            <PermissionGate permission="repair_order.transition">
                              <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                <IconButton size="small" onClick={() => openEditLaborLine(line)}>
                                  <EditRoundedIcon sx={{ fontSize: 15 }} />
                                </IconButton>
                                <IconButton size="small" onClick={() => setDeleteLaborLineId(line.id)}>
                                  <DeleteRoundedIcon sx={{ fontSize: 15 }} />
                                </IconButton>
                              </Stack>
                            </PermissionGate>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                    <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                      <TableCell colSpan={3}>
                        <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Total MO
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={700}>{formatMinor(laborTotal, currency)}</Typography>
                      </TableCell>
                      {canEditLaborLines && <TableCell />}
                    </TableRow>
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Parts lines */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 0 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 3, py: 2 }}>
                <Typography variant="subtitle2" fontWeight={700}>
                  Pièces
                  <Typography component="span" variant="caption" color="text.secondary" ml={1} fontWeight={400}>
                    {ro.part_lines.length} ligne{ro.part_lines.length !== 1 ? 's' : ''}
                  </Typography>
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" fontWeight={700} color={partsTotal > 0 ? 'text.primary' : 'text.disabled'}>
                    {formatMinor(partsTotal, currency)}
                  </Typography>
                  {ro.status === 'paused_parts' && (
                    <PermissionGate permission="repair_order.transition">
                      <Button size="small" variant="outlined" startIcon={<AddRoundedIcon />} onClick={() => setShowAddPart(v => !v)} sx={{ textTransform: 'none', fontWeight: 600, fontSize: 12 }}>
                        Ajouter
                      </Button>
                    </PermissionGate>
                  )}
                </Stack>
              </Stack>
              {showAddPart && (
                <Box sx={{ px: 3, pb: 2 }}>
                  {/* Step 1 — category */}
                  <FormControl fullWidth size="small" sx={{ mb: 1 }}>
                    <InputLabel>Catégorie</InputLabel>
                    <Select
                      label="Catégorie"
                      value={selectedCategoryId ?? ''}
                      onChange={(e) => {
                        const v = e.target.value
                        setSelectedCategoryId(v === '' ? null : v === 'none' ? 'none' : Number(v))
                        setSelectedPart(null)
                        setPartQty('')
                        setPartUnitPrice('')
                        setNewPartPrice('')
                      }}
                    >
                      <MenuItem value=""><em>— Sélectionner une catégorie —</em></MenuItem>
                      {(partCategories ?? []).filter(cat => cat.part_count > 0).map(cat => (
                        <MenuItem key={cat.id} value={cat.id}>{cat.name}</MenuItem>
                      ))}
                      <MenuItem value="none"><em>Sans catégorie</em></MenuItem>
                    </Select>
                  </FormControl>
                  {/* Step 2 — part (only after category chosen) */}
                  {selectedCategoryId !== null && (
                    <Autocomplete
                      sx={{ mb: 1 }}
                      size="small"
                      options={partsResults?.items ?? []}
                      getOptionLabel={(o) => `${o.sku_code} — ${o.name}`}
                      getOptionDisabled={(o) => o.stock_on_hand === 0}
                      value={selectedPart}
                      onChange={(_, val) => {
                        setSelectedPart(val)
                        setPartQty('1')
                        setPartUnitPrice(val ? (val.selling_price_minor / 100).toFixed(2) : '')
                        setNewPartPrice('')
                      }}
                      noOptionsText={partsResults ? (selectedCategoryId === 'none' ? 'Aucune pièce sans catégorie' : 'Aucune pièce dans cette catégorie') : 'Chargement…'}
                      renderOption={(props, option) => (
                        <Box component="li" {...props} key={option.int_id}>
                          <Stack direction="row" justifyContent="space-between" width="100%" spacing={1}>
                            <Typography variant="body2">{option.sku_code} — {option.name}</Typography>
                            <Typography variant="caption" color={option.stock_on_hand > 0 ? 'success.main' : 'error.main'}>
                              Stock : {option.stock_on_hand}
                            </Typography>
                          </Stack>
                        </Box>
                      )}
                      renderInput={(params) => (
                        <TextField {...params} label="Pièce" placeholder="Rechercher dans la catégorie…" />
                      )}
                    />
                  )}
                  {/* Row 2: qty, price, remise, tva — always visible below dropdown */}
                  <Stack direction="row" spacing={1} mb={1} flexWrap="wrap">
                    <TextField
                      size="small"
                      label="Quantité"
                      type="number"
                      value={partQty}
                      onChange={e => setPartQty(e.target.value)}
                      inputProps={{ min: 1, max: selectedPart?.stock_on_hand ?? undefined, step: 1 }}
                      sx={{ width: 110 }}
                      helperText={selectedPart ? `Max : ${selectedPart.stock_on_hand}` : ' '}
                      disabled={!selectedPart}
                    />
                    <TextField
                      size="small"
                      label="Prix unit. (€)"
                      type="number"
                      value={partUnitPrice}
                      inputProps={{ min: 0, step: 0.01, readOnly: true }}
                      sx={{ width: 130, '& .MuiInputBase-input': { bgcolor: 'action.hover', cursor: 'default' } }}
                      helperText=" "
                      disabled={!selectedPart}
                    />
                    <TextField
                      size="small"
                      label="Remise (%)"
                      type="number"
                      value={partRemise}
                      onChange={e => setPartRemise(e.target.value)}
                      inputProps={{ min: 0, max: 100, step: 0.01 }}
                      sx={{ width: 110 }}
                      helperText=" "
                      disabled={!selectedPart}
                    />
                    <Box sx={{ display: 'flex', alignItems: 'center', px: 1, pb: '20px', minWidth: 80 }}>
                      <Typography variant="caption" color="text.secondary">TVA&nbsp;20%</Typography>
                    </Box>
                    {selectedPart && partQty && partUnitPrice && parseFloat(partUnitPrice) > 0 && (
                      <Box sx={{ display: 'flex', alignItems: 'center', pb: '20px' }}>
                        <Typography variant="body2" color="text.secondary">
                          Total TTC :&nbsp;
                        </Typography>
                        <Typography variant="body2" fontWeight={700}>
                          {(
                            parseInt(partQty, 10) *
                            parseFloat(partUnitPrice) *
                            (1 - (parseFloat(partRemise) || 0) / 100) *
                            1.20
                          ).toFixed(2)} €
                        </Typography>
                      </Box>
                    )}
                  </Stack>
                  {selectedPart && parseFloat(partUnitPrice || '0') <= 0 && (
                    <Alert severity="warning" sx={{ mb: 1 }}>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        Cette pièce n'a pas de prix de vente défini. Définissez un prix avant de l'ajouter à l'OR.
                      </Typography>
                      <PermissionGate permission="part.update">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <TextField
                            size="small"
                            label="Nouveau prix (€)"
                            type="number"
                            value={newPartPrice}
                            onChange={e => setNewPartPrice(e.target.value)}
                            inputProps={{ min: 0.01, step: 0.01 }}
                            sx={{ width: 150 }}
                          />
                          <Button
                            size="small"
                            variant="outlined"
                            disabled={setPartPriceMutation.isPending || !newPartPrice || parseFloat(newPartPrice) <= 0}
                            onClick={() => setPartPriceMutation.mutate()}
                            sx={{ textTransform: 'none' }}
                          >
                            {setPartPriceMutation.isPending ? 'Enregistrement…' : 'Enregistrer le prix'}
                          </Button>
                        </Stack>
                      </PermissionGate>
                    </Alert>
                  )}
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      onClick={() => {
                        setShowAddPart(false)
                        setSelectedPart(null); setSelectedCategoryId(null); setPartQty('')
                        setPartUnitPrice(''); setPartRemise('0'); setNewPartPrice('')
                      }}
                      sx={{ textTransform: 'none' }}
                    >
                      Annuler
                    </Button>
                    <Button
                      size="small" variant="contained"
                      disabled={
                        addPartMutation.isPending ||
                        !selectedPart ||
                        !partQty ||
                        !partUnitPrice ||
                        parseFloat(partUnitPrice) <= 0 ||
                        parseInt(partQty, 10) < 1 ||
                        parseInt(partQty, 10) > (selectedPart?.stock_on_hand ?? 0)
                      }
                      onClick={() => addPartMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {addPartMutation.isPending ? 'Enregistrement…' : 'Ajouter'}
                    </Button>
                  </Stack>
                </Box>
              )}
              <Divider />
              {ro.part_lines.length === 0 ? (
                <Box sx={{ px: 3, py: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">Aucune pièce.</Typography>
                </Box>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Pièce</TableCell>
                      <TableCell align="right">Qté</TableCell>
                      <TableCell align="right">Prix unit.</TableCell>
                      <TableCell align="right">Remise</TableCell>
                      <TableCell align="right">TVA</TableCell>
                      <TableCell align="right">Montant</TableCell>
                      {canEditPartLines && <TableCell align="right">Actions</TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ro.part_lines.map(line => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>{line.part_name}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{line.quantity}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{formatMinor(line.unit_cost_minor, currency)}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" color={line.remise_pct > 0 ? 'error.main' : 'text.secondary'}>
                            {line.remise_pct > 0 ? `-${line.remise_pct}%` : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" color="text.secondary">
                            {line.tva_pct > 0 ? `${line.tva_pct}%` : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontWeight={600}>{formatMinor(line.amount_minor, currency)}</Typography>
                        </TableCell>
                        {canEditPartLines && (
                          <TableCell align="right">
                            <PermissionGate permission="repair_order.transition">
                              <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                <IconButton size="small" onClick={() => openEditPartLine(line)}>
                                  <EditRoundedIcon sx={{ fontSize: 15 }} />
                                </IconButton>
                                <IconButton size="small" onClick={() => setDeletePartLineId(line.id)}>
                                  <DeleteRoundedIcon sx={{ fontSize: 15 }} />
                                </IconButton>
                              </Stack>
                            </PermissionGate>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                    <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                      <TableCell colSpan={5}>
                        <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Total Pièces
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={700}>{formatMinor(partsTotal, currency)}</Typography>
                      </TableCell>
                      {canEditPartLines && <TableCell />}
                    </TableRow>
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Grand total banner */}
          {(laborTotal > 0 || partsTotal > 0) && (
            <Card sx={{ mb: 3, bgcolor: '#0F172A', color: 'white' }}>
              <CardContent sx={{ py: 2, px: 3 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle2" fontWeight={700} color="rgba(255,255,255,0.7)">
                    Total estimé (MO + Pièces)
                  </Typography>
                  <Typography variant="h6" fontWeight={800} color="white">
                    {formatMinor(laborTotal + partsTotal, currency)}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={2}>
                Commentaires
              </Typography>
              <CommentsPanel publicId={publicId} />
            </CardContent>
          </Card>

          {/* Photos */}
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={2}>
                Photos
              </Typography>
              <PhotosPanel publicId={publicId} />
            </CardContent>
          </Card>
        </Grid>

        {/* ── RIGHT COLUMN ────────────────────────────────────────────── */}
        <Grid item xs={12} md={4}>
          <Stack spacing={3} sx={{ position: { md: 'sticky' }, top: { md: 24 } }}>

            {/* Pending advances banner */}
            {pendingAdvancesTotal > 0 && (
              <Card sx={{ border: '1px solid #FDE68A', bgcolor: '#FFFBEB' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                  <Stack direction="row" spacing={1.5} alignItems="flex-start">
                    <SavingsRoundedIcon sx={{ color: '#D97706', fontSize: 20, mt: 0.25, flexShrink: 0 }} />
                    <Box>
                      <Typography variant="subtitle2" fontWeight={700} color="#92400E">
                        Acomptes disponibles
                      </Typography>
                      <Typography variant="body2" color="#92400E" mt={0.25}>
                        Ce client a{' '}
                        <strong>{formatMinor(pendingAdvancesTotal)}</strong>
                        {' '}en acomptes non imputés — ils seront automatiquement déduits à l'émission de la facture.
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            )}

            {/* Status transition */}
            <PermissionGate permission="repair_order.transition">
              <Card>
                <CardContent sx={{ p: 2.5 }}>
                  <StatusTransitionPanel ro={ro} onTransitioned={() => refetch()} />
                </CardContent>
              </Card>
            </PermissionGate>

            {/* Mechanic assignment — only during the diagnosis step */}
            {ro.status === 'diagnosis' && (
              <PermissionGate permission="repair_order.transition">
                <Card>
                  <CardContent sx={{ p: 2.5 }}>
                    <MechanicPanel ro={ro} onUpdated={() => refetch()} />
                  </CardContent>
                </Card>
              </PermissionGate>
            )}

            {/* Create Devis (diagnosis only) */}
            {ro.status === 'diagnosis' && (
              <PermissionGate permission="quotation.create">
                <Card>
                  <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Actions
                    </Typography>
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<DescriptionRoundedIcon />}
                      disabled={createDevisMutation.isPending || !ro.diagnosis_completed_at}
                      onClick={() => createDevisMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {createDevisMutation.isPending ? 'Création…' : 'Créer un devis'}
                    </Button>
                    {!ro.diagnosis_completed_at && (
                      <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                        Terminez le diagnostic pour générer le devis.
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </PermissionGate>
            )}

            {/* Create Invoice / Delivery Note (finished or delivered) */}
            {(ro.status === 'finished' || ro.status === 'delivered') && (
              <PermissionGate permission="invoice.create">
                <Card>
                  <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Actions
                    </Typography>
                    <Stack spacing={1.5}>
                      {ro.linked_invoice ? (
                        <Alert
                          severity="info"
                          icon={<ReceiptRoundedIcon fontSize="inherit" />}
                          action={
                            <IconButton
                              size="small"
                              component={RouterLink}
                              to={`/invoices/${ro.linked_invoice.public_id}`}
                            >
                              <OpenInNewRoundedIcon fontSize="small" />
                            </IconButton>
                          }
                        >
                          Facture {ro.linked_invoice.doc_number ?? '(brouillon)'} créée le{' '}
                          {new Date(ro.linked_invoice.created_at).toLocaleDateString('fr-FR')}.
                        </Alert>
                      ) : (
                        <Button
                          variant="contained"
                          color="success"
                          fullWidth
                          startIcon={<ReceiptRoundedIcon />}
                          disabled={createInvoiceMutation.isPending}
                          onClick={() => createInvoiceMutation.mutate()}
                          sx={{ textTransform: 'none', fontWeight: 700 }}
                        >
                          {createInvoiceMutation.isPending ? 'Création…' : 'Créer une facture'}
                        </Button>
                      )}

                      {ro.linked_delivery_note ? (
                        <Alert
                          severity="info"
                          icon={<LocalShippingRoundedIcon fontSize="inherit" />}
                          action={
                            <IconButton
                              size="small"
                              component={RouterLink}
                              to={`/delivery-notes/${ro.linked_delivery_note.public_id}`}
                            >
                              <OpenInNewRoundedIcon fontSize="small" />
                            </IconButton>
                          }
                        >
                          BL {ro.linked_delivery_note.doc_number ?? '(brouillon)'} créé le{' '}
                          {new Date(ro.linked_delivery_note.created_at).toLocaleDateString('fr-FR')}.
                        </Alert>
                      ) : (
                        <Button
                          variant="contained"
                          fullWidth
                          startIcon={<LocalShippingRoundedIcon />}
                          disabled={createDeliveryNoteMutation.isPending}
                          onClick={() => createDeliveryNoteMutation.mutate()}
                          sx={{ textTransform: 'none', fontWeight: 700 }}
                        >
                          {createDeliveryNoteMutation.isPending ? 'Création…' : 'Créer un bon de livraison'}
                        </Button>
                      )}
                    </Stack>
                  </CardContent>
                </Card>
              </PermissionGate>
            )}

            {/* Record advance payment — available at any stage */}
            <PermissionGate permission="deposit.record">
              <Card>
                <CardContent sx={{ p: 2.5 }}>
                  <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Acompte
                  </Typography>
                  <Button
                    variant="outlined"
                    fullWidth
                    startIcon={<SavingsRoundedIcon />}
                    onClick={() => setAdvanceOpen(true)}
                    sx={{ textTransform: 'none', fontWeight: 700, borderColor: '#D97706', color: '#D97706', '&:hover': { borderColor: '#92400E', bgcolor: '#FFFBEB' } }}
                  >
                    Enregistrer un acompte
                  </Button>
                </CardContent>
              </Card>
            </PermissionGate>

            {/* Status timeline */}
            <Card>
              <CardContent sx={{ p: 2.5 }}>
                <Typography variant="caption" fontWeight={700} color="text.secondary" sx={SECTION_LABEL_SX}>
                  Historique des statuts
                </Typography>
                <StatusTimeline events={ro.status_events} />
              </CardContent>
            </Card>

          </Stack>
        </Grid>
      </Grid>

      {/* Advance payment creation dialog */}
      <Dialog open={advanceOpen} onClose={() => setAdvanceOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Enregistrer un acompte</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} pt={1}>
            <TextField
              label="Montant (€)"
              type="number"
              fullWidth
              value={advanceAmount}
              onChange={e => setAdvanceAmount(e.target.value)}
              inputProps={{ min: 0, step: '0.01' }}
              helperText="Ex: 50.00"
              autoFocus
            />
            <TextField
              label="Mode de paiement"
              select
              fullWidth
              value={advanceMethod}
              onChange={e => setAdvanceMethod(e.target.value as PaymentMethod)}
            >
              {(Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][]).map(([v, l]) => (
                <MenuItem key={v} value={v}>{l}</MenuItem>
              ))}
            </TextField>
            <TextField
              label="Référence (optionnel)"
              fullWidth
              value={advanceRef}
              onChange={e => setAdvanceRef(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setAdvanceOpen(false)}>Annuler</Button>
          <Button
            variant="contained"
            onClick={() => createAdvanceMutation.mutate()}
            disabled={
              createAdvanceMutation.isPending ||
              !advanceAmount ||
              parseFloat(advanceAmount) <= 0
            }
          >
            {createAdvanceMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        title="Supprimer l'ordre de réparation ?"
        message="L'ordre sera archivé et n'apparaîtra plus dans la liste principale."
        confirmLabel="Supprimer"
        dangerous
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />

      <Dialog open={editLaborLineId !== null} onClose={() => setEditLaborLineId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Modifier la ligne de main d'œuvre</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              size="small" label="Désignation" value={editLaborType}
              onChange={e => setEditLaborType(e.target.value)} fullWidth
            />
            <TextField
              size="small" label="Prix HT (€)" type="number" value={editLaborRate}
              onChange={e => setEditLaborRate(e.target.value)} inputProps={{ min: 0, step: 0.01 }} fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditLaborLineId(null)} sx={{ textTransform: 'none' }}>Annuler</Button>
          <Button
            variant="contained"
            disabled={updateLaborLineMutation.isPending || !editLaborType.trim() || !editLaborRate}
            onClick={() => updateLaborLineMutation.mutate()}
            sx={{ textTransform: 'none', fontWeight: 700 }}
          >
            {updateLaborLineMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deleteLaborLineId !== null}
        title="Supprimer cette ligne de main d'œuvre ?"
        message="Cette action est irréversible."
        confirmLabel="Supprimer"
        dangerous
        loading={removeLaborLineMutation.isPending}
        onConfirm={() => deleteLaborLineId !== null && removeLaborLineMutation.mutate(deleteLaborLineId)}
        onCancel={() => setDeleteLaborLineId(null)}
      />

      <Dialog open={editPartLineId !== null} onClose={() => setEditPartLineId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Modifier la pièce</DialogTitle>
        <DialogContent>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap">
            <TextField
              size="small" label="Quantité" type="number" value={editPartQty}
              onChange={e => setEditPartQty(e.target.value)} inputProps={{ min: 1, step: 1 }} sx={{ width: 110 }}
            />
            <TextField
              size="small" label="Prix unit. (€)" type="number" value={editPartUnitPrice}
              onChange={e => setEditPartUnitPrice(e.target.value)} inputProps={{ min: 0.01, step: 0.01 }} sx={{ width: 130 }}
            />
            <TextField
              size="small" label="Remise (%)" type="number" value={editPartRemise}
              onChange={e => setEditPartRemise(e.target.value)} inputProps={{ min: 0, max: 100, step: 1 }} sx={{ width: 110 }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditPartLineId(null)} sx={{ textTransform: 'none' }}>Annuler</Button>
          <Button
            variant="contained"
            disabled={
              updatePartLineMutation.isPending ||
              !editPartQty || !editPartUnitPrice ||
              parseInt(editPartQty, 10) < 1 ||
              parseFloat(editPartUnitPrice) <= 0
            }
            onClick={() => updatePartLineMutation.mutate()}
            sx={{ textTransform: 'none', fontWeight: 700 }}
          >
            {updatePartLineMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deletePartLineId !== null}
        title="Supprimer cette pièce ?"
        message="Le stock réservé pour cette pièce sera libéré."
        confirmLabel="Supprimer"
        dangerous
        loading={removePartLineMutation.isPending}
        onConfirm={() => deletePartLineId !== null && removePartLineMutation.mutate(deletePartLineId)}
        onCancel={() => setDeletePartLineId(null)}
      />
    </Box>
  )
}
