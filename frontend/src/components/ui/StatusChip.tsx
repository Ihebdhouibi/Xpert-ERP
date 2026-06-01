import { Chip, type ChipProps } from '@mui/material'

export type StatusKey =
  | 'active' | 'inactive' | 'blocked'
  | 'pending' | 'in_progress' | 'waiting_parts' | 'ready' | 'delivered' | 'cancelled'
  | 'draft' | 'sent' | 'partial' | 'received'
  | 'paid' | 'overdue' | 'credited'
  | 'matched' | 'posted' | 'disputed'
  | 'done' | 'approved' | 'rejected'
  | 'open' | 'closed' | 'processing'
  | 'confirmed' | 'invoiced'
  // Repair order statuses
  | 'created' | 'diagnosis' | 'in_repair' | 'finished'
  | 'paused_parts' | 'paused_approval'
  // Purchase order / inspection statuses
  | 'completed' | 'partially_received'

const labels: Record<StatusKey, string> = {
  active: 'Actif',
  inactive: 'Inactif',
  blocked: 'Bloqué',
  pending: 'En attente',
  in_progress: 'En cours',
  waiting_parts: 'Attente pièces',
  ready: 'Prêt',
  delivered: 'Livré',
  cancelled: 'Annulé',
  draft: 'Brouillon',
  sent: 'Envoyé',
  partial: 'Partiel',
  received: 'Reçu',
  paid: 'Payé',
  overdue: 'En retard',
  credited: 'Avoir',
  matched: 'Rapproché',
  posted: 'Comptabilisé',
  disputed: 'Contesté',
  done: 'Terminé',
  approved: 'Approuvé',
  rejected: 'Rejeté',
  open: 'Ouvert',
  closed: 'Clôturé',
  processing: 'En traitement',
  confirmed: 'Confirmé',
  invoiced: 'Facturé',
  created: 'Créé',
  diagnosis: 'Diagnostic',
  in_repair: 'En réparation',
  finished: 'Terminé',
  paused_parts: 'Attente pièces',
  paused_approval: 'Attente accord',
  completed: 'Complété',
  partially_received: 'Partiellement reçu',
}

type ChipColor = ChipProps['color']

const colorMap: Record<StatusKey, ChipColor> = {
  active: 'success',
  inactive: 'default',
  blocked: 'error',
  pending: 'warning',
  in_progress: 'info',
  waiting_parts: 'warning',
  ready: 'success',
  delivered: 'success',
  cancelled: 'error',
  draft: 'default',
  sent: 'info',
  partial: 'warning',
  received: 'success',
  paid: 'success',
  overdue: 'error',
  credited: 'default',
  matched: 'info',
  posted: 'success',
  disputed: 'error',
  done: 'success',
  approved: 'success',
  rejected: 'error',
  open: 'warning',
  closed: 'default',
  processing: 'info',
  confirmed: 'info',
  invoiced: 'success',
  created: 'default',
  diagnosis: 'info',
  in_repair: 'primary',
  finished: 'warning',
  paused_parts: 'warning',
  paused_approval: 'warning',
  completed: 'success',
  partially_received: 'warning',
}

interface StatusChipProps {
  status: string
  size?: 'small' | 'medium'
  label?: string
}

export function StatusChip({ status, size = 'small', label }: StatusChipProps) {
  const key = status as StatusKey
  const color: ChipColor = colorMap[key] ?? 'default'
  const displayLabel = label ?? labels[key] ?? status

  return (
    <Chip
      label={displayLabel}
      color={color}
      size={size}
      sx={{ fontWeight: 600 }}
    />
  )
}
