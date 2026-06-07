import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import { useQuery } from '@tanstack/react-query'
import { paymentApi, PAYMENT_METHOD_LABELS } from '../../lib/paymentApi'
import { formatMinor } from '../ui/CurrencyDisplay'

const METHOD_COLORS: Record<string, { bg: string; color: string }> = {
  cash: { bg: '#F0FDF4', color: '#16A34A' },
  card: { bg: '#EFF6FF', color: '#2563EB' },
  bank_transfer: { bg: '#F5F3FF', color: '#7C3AED' },
  cheque: { bg: '#FFFBEB', color: '#D97706' },
  other: { bg: '#F1F5F9', color: '#64748B' },
}

interface Props {
  invoiceId: number
  currency: string
}

export function PaymentHistoryPanel({ invoiceId, currency }: Props) {
  const { data: payments, isLoading } = useQuery({
    queryKey: ['payment-history', invoiceId],
    queryFn: () => paymentApi.listByInvoice(invoiceId),
    enabled: invoiceId > 0,
  })

  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
          <Box sx={{ color: 'primary.main' }}>
            <HistoryRoundedIcon sx={{ fontSize: 20 }} />
          </Box>
          <Typography variant="subtitle1" fontWeight={700}>
            Historique des paiements
          </Typography>
          {!isLoading && payments && payments.length > 0 && (
            <Chip
              label={payments.length}
              size="small"
              sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600, ml: 'auto !important' }}
            />
          )}
        </Stack>
        <Divider sx={{ mb: 0 }} />

        {isLoading ? (
          <Stack spacing={1.5} pt={2}>
            {[1, 2].map(i => <Skeleton key={i} variant="rectangular" height={40} sx={{ borderRadius: 1 }} />)}
          </Stack>
        ) : !payments || payments.length === 0 ? (
          <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
            Aucun paiement enregistré pour cette facture.
          </Typography>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small" sx={{ minWidth: 480 }}>
              <TableHead>
                <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                  {['Date', 'Moyen', 'Référence', 'Montant'].map((h, i) => (
                    <TableCell
                      key={h}
                      align={i === 3 ? 'right' : 'left'}
                      sx={{ fontSize: '0.6875rem', fontWeight: 600, color: 'text.secondary', py: 1.25 }}
                    >
                      {h}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {payments.map(p => {
                  const methodCfg = METHOD_COLORS[p.payment_method] ?? METHOD_COLORS.other
                  const dateStr = new Date(p.paid_at).toLocaleDateString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                  })
                  return (
                    <TableRow key={p.id} sx={{ '&:hover': { bgcolor: '#F9FAFB' } }}>
                      <TableCell sx={{ py: 1.5 }}>
                        <Typography variant="body2" fontFamily="monospace" color="text.secondary">
                          {dateStr}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ py: 1.5 }}>
                        <Chip
                          label={PAYMENT_METHOD_LABELS[p.payment_method]}
                          size="small"
                          sx={{
                            bgcolor: methodCfg.bg,
                            color: methodCfg.color,
                            fontWeight: 600,
                            fontSize: '0.6875rem',
                            height: 22,
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ py: 1.5, maxWidth: 160 }}>
                        {p.reference ? (
                          <Typography variant="body2" color="text.secondary" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {p.reference}
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.disabled">—</Typography>
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ py: 1.5 }}>
                        <Typography variant="body2" fontWeight={700} fontFamily="monospace" color="success.dark">
                          {formatMinor(p.amount_minor, currency)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
