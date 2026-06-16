import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Typography,
} from '@mui/material'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import { creditNoteApi, CREDIT_NOTE_STATUS_LABELS } from '../../lib/creditNoteApi'
import { formatMinor } from '../ui/CurrencyDisplay'

interface Props {
  invoiceId: number
}

export function CreditNotesPanel({ invoiceId }: Props) {
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['credit-notes-for-invoice', invoiceId],
    queryFn: () => creditNoteApi.list({ invoice_id: invoiceId, page_size: 50 }),
  })

  const items = data?.items ?? []

  if (isLoading || items.length === 0) return null

  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
          <Box sx={{ color: '#EA580C' }}>
            <AccountBalanceRoundedIcon sx={{ fontSize: 20 }} />
          </Box>
          <Typography variant="subtitle1" fontWeight={700}>
            Avoirs liés
          </Typography>
          <Chip
            label={items.length}
            size="small"
            sx={{ bgcolor: '#FFF7ED', color: '#EA580C', fontWeight: 600 }}
          />
        </Stack>
        <Divider sx={{ mb: 0 }} />
        <Stack divider={<Divider />}>
          {items.map(avoir => (
            <Stack
              key={avoir.id}
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              py={1.25}
              sx={{ cursor: 'pointer', '&:hover': { bgcolor: '#FAFAFA' }, mx: -1, px: 1, borderRadius: 1 }}
              onClick={() => navigate(`/credit-notes/${avoir.id}`)}
            >
              <Stack direction="row" alignItems="center" spacing={1.5}>
                <Typography variant="body2" fontWeight={700} fontFamily="monospace">
                  {avoir.doc_number ?? (
                    <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
                      Brouillon
                    </Typography>
                  )}
                </Typography>
                {avoir.reason && (
                  <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 200 }}>
                    {avoir.reason}
                  </Typography>
                )}
              </Stack>
              <Stack direction="row" alignItems="center" spacing={1.5}>
                <Typography variant="body2" fontWeight={700} color="error.main">
                  -{formatMinor(avoir.total_minor)}
                </Typography>
                <Chip
                  label={CREDIT_NOTE_STATUS_LABELS[avoir.status]}
                  size="small"
                  sx={{
                    fontWeight: 600,
                    fontSize: '0.6875rem',
                    bgcolor: avoir.status === 'issued' ? '#F0FDF4' : avoir.status === 'void' ? '#FEF2F2' : '#F1F5F9',
                    color: avoir.status === 'issued' ? '#16A34A' : avoir.status === 'void' ? '#DC2626' : '#64748B',
                  }}
                />
              </Stack>
            </Stack>
          ))}
        </Stack>
      </CardContent>
    </Card>
  )
}
