import { Box, Stack, Typography } from '@mui/material'

export type StatusKey =
  | 'active' | 'inactive' | 'blocked'
  | 'pending' | 'in_progress' | 'waiting_parts' | 'ready' | 'delivered' | 'cancelled'
  | 'draft' | 'sent' | 'partial' | 'received'
  | 'paid' | 'overdue' | 'credited'
  | 'matched' | 'posted' | 'disputed'
  | 'done' | 'approved' | 'rejected'
  | 'open' | 'closed' | 'processing'
  | 'confirmed' | 'invoiced'
  | 'created' | 'diagnosis' | 'in_repair' | 'finished'
  | 'paused_parts'
  | 'completed' | 'partially_received'
  | 'issued' | 'expired' | 'converted' | 'scrapped'

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
  completed: 'Complété',
  partially_received: 'Part. reçu',
  issued: 'Émise',
  expired: 'Expiré',
  converted: 'Converti',
  scrapped: 'Épave',
}

// Dot color + text color + background — muted, not loud
// Inspired by Stripe's status badge palette
type StatusStyle = {
  dot: string
  text: string
  bg: string
}

const styleMap: Record<StatusKey, StatusStyle> = {
  // Green — positive / completed
  active:    { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  paid:      { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  ready:     { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  delivered: { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  done:      { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  approved:  { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  received:  { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  matched:   { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  posted:    { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  invoiced:  { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  completed: { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  confirmed: { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
  finished:  { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },

  // Red — error / blocked / rejected
  blocked:   { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  cancelled: { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  overdue:   { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  disputed:  { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  rejected:  { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  paused_parts:    { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
  scrapped:  { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },

  // Amber — in-progress / waiting / attention
  pending:       { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  in_progress:   { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  waiting_parts: { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  partial:       { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  open:          { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  processing:    { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  in_repair:     { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
  partially_received: { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },

  // Blue — informational / sent / active states
  sent:       { dot: '#2563EB', text: '#1D4ED8', bg: '#EFF6FF' },
  diagnosis:  { dot: '#2563EB', text: '#1D4ED8', bg: '#EFF6FF' },

  // Grey — neutral / default / closed
  inactive:  { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  draft:     { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  closed:    { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  credited:  { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  created:   { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  expired:   { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  converted: { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  issued:    { dot: '#2563EB', text: '#1D4ED8', bg: '#EFF6FF' },
}

const fallbackStyle: StatusStyle = { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' }

interface StatusChipProps {
  status: string
  size?: 'small' | 'medium'
  label?: string
}

export function StatusChip({ status, size = 'small', label }: StatusChipProps) {
  const key = status as StatusKey
  const style = styleMap[key] ?? fallbackStyle
  const displayLabel = label ?? labels[key] ?? status

  const dotSize = size === 'small' ? 6 : 8
  const fontSize = size === 'small' ? '0.6875rem' : '0.8125rem'
  const px = size === 'small' ? 1 : 1.5
  const py = size === 'small' ? 0.375 : 0.5

  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        px,
        py,
        borderRadius: '6px',
        bgcolor: style.bg,
        border: '1px solid',
        // Border tinted slightly with the dot color for cohesion
        borderColor: `${style.dot}28`, // 16% opacity
        flexShrink: 0,
        whiteSpace: 'nowrap',
      }}
    >
      <Stack direction="row" alignItems="center" spacing={0.625} component="span">
        {/* The dot — sole color carrier, everything else is muted */}
        <Box
          component="span"
          sx={{
            width: dotSize,
            height: dotSize,
            borderRadius: '50%',
            bgcolor: style.dot,
            flexShrink: 0,
          }}
        />
        <Typography
          component="span"
          sx={{
            fontSize,
            fontWeight: 500,
            color: style.text,
            lineHeight: 1,
            letterSpacing: '0.01em',
          }}
        >
          {displayLabel}
        </Typography>
      </Stack>
    </Box>
  )
}
