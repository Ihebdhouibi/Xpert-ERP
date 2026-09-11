import { Box, Stack, Typography, useTheme } from '@mui/material'

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

// Five semantic groups, one light/dark pair each — every status key below
// just points at a group name, so the two palettes can't drift out of sync
// with each other the way 30 fully-duplicated per-key entries would.
type StatusGroup = 'success' | 'error' | 'warning' | 'info' | 'neutral'

const GROUP_STYLES: Record<'light' | 'dark', Record<StatusGroup, StatusStyle>> = {
  light: {
    success: { dot: '#16A34A', text: '#15803D', bg: '#F0FDF4' },
    error:   { dot: '#DC2626', text: '#B91C1C', bg: '#FEF2F2' },
    warning: { dot: '#D97706', text: '#92400E', bg: '#FFFBEB' },
    info:    { dot: '#334155', text: '#1E293B', bg: '#E2E8F0' },
    neutral: { dot: '#94A3B8', text: '#64748B', bg: '#F8FAFC' },
  },
  dark: {
    success: { dot: '#34D399', text: '#6EE7B7', bg: 'rgba(16,185,129,0.14)' },
    error:   { dot: '#F87171', text: '#FCA5A5', bg: 'rgba(239,68,68,0.14)' },
    warning: { dot: '#FBBF24', text: '#FDE68A', bg: 'rgba(245,158,11,0.14)' },
    info:    { dot: '#94A3B8', text: '#CBD5E1', bg: 'rgba(148,163,184,0.14)' },
    neutral: { dot: '#64748B', text: '#94A3B8', bg: 'rgba(148,163,184,0.08)' },
  },
}

const GROUP_FOR_KEY: Record<StatusKey, StatusGroup> = {
  // Green — positive / completed
  active: 'success', paid: 'success', ready: 'success', delivered: 'success',
  done: 'success', approved: 'success', received: 'success', matched: 'success',
  posted: 'success', invoiced: 'success', completed: 'success', confirmed: 'success',
  finished: 'success',

  // Red — error / blocked / rejected
  blocked: 'error', cancelled: 'error', overdue: 'error', disputed: 'error',
  rejected: 'error', paused_parts: 'error', scrapped: 'error',

  // Amber — in-progress / waiting / attention
  pending: 'warning', in_progress: 'warning', waiting_parts: 'warning', partial: 'warning',
  open: 'warning', processing: 'warning', in_repair: 'warning', partially_received: 'warning',

  // Slate — informational / sent / active states
  sent: 'info', diagnosis: 'info', issued: 'info',

  // Grey — neutral / default / closed
  inactive: 'neutral', draft: 'neutral', closed: 'neutral', credited: 'neutral',
  created: 'neutral', expired: 'neutral', converted: 'neutral',
}

interface StatusChipProps {
  status: string
  size?: 'small' | 'medium'
  label?: string
}

export function StatusChip({ status, size = 'small', label }: StatusChipProps) {
  const mode = useTheme().palette.mode
  const key = status as StatusKey
  const group = GROUP_FOR_KEY[key] ?? 'neutral'
  const style = GROUP_STYLES[mode][group]
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
