import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Pagination,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from '@mui/material'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { customerSubApi } from '../../lib/customerApi'
import { advancePaymentApi } from '../../lib/advancePaymentApi'
import { StatusChip } from '../ui/StatusChip'
import { formatMinor } from '../ui/CurrencyDisplay'
import type { StatusKey } from '../ui/StatusChip'
import { DELIVERY_NOTE_STATUS_LABELS } from '../../lib/deliveryNoteApi'
import { INVOICE_STATUS_LABELS } from '../../lib/invoiceApi'
import { QUOTATION_STATUS_LABELS } from '../../lib/quotationApi'
import { PermissionGate } from '../auth/PermissionGate'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

function EmptyState({ label }: { label: string }) {
  return (
    <Box sx={{ py: 4, textAlign: 'center', bgcolor: '#FAFAFA', borderRadius: 1.5 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
    </Box>
  )
}

function LoadingState() {
  return (
    <Box display="flex" justifyContent="center" py={3}>
      <CircularProgress size={24} />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// RO Tab
// ---------------------------------------------------------------------------

function RepairOrdersTab({
  customerPublicId,
  customerIntId,
}: {
  customerPublicId: string
  customerIntId: number
}) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['customer-ros', customerPublicId, page],
    queryFn: () => customerSubApi.getRepairOrders(customerPublicId, { page, page_size: 10 }),
    enabled: !!customerPublicId,
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 10)

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" mb={1.5}>
        <PermissionGate permission="repair_order.create">
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate(`/repair-orders/new?customerId=${customerIntId}`)}
          >
            Nouvel OdR
          </Button>
        </PermissionGate>
      </Stack>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState label="Aucun ordre de réparation pour ce client." />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Coût réel</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((ro: any) => (
                <TableRow
                  key={ro.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/repair-orders/${ro.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{fmt(ro.created_at)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 240 }}>
                      {ro.description}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={ro.status as StatusKey} />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {formatMinor(ro.actual_cost_minor, ro.estimated_cost_currency ?? 'EUR')}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <Stack alignItems="center" mt={1.5}>
              <Pagination count={totalPages} page={page} onChange={(_, v) => setPage(v)} size="small" />
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Quotations Tab
// ---------------------------------------------------------------------------

function QuotationsTab({ customerPublicId, customerIntId }: { customerPublicId: string; customerIntId: number }) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['customer-quotations', customerPublicId, page],
    queryFn: () => customerSubApi.getQuotations(customerPublicId, { page, page_size: 10 }),
    enabled: !!customerPublicId,
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 10)

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" mb={1.5}>
        <PermissionGate permission="quotation.create">
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate(`/quotations/new?customerId=${customerIntId}`)}
          >
            Nouveau devis
          </Button>
        </PermissionGate>
      </Stack>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState label="Aucun devis pour ce client." />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Référence</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Total TTC</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((q: any) => (
                <TableRow
                  key={q.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/quotations/${q.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{fmt(q.created_at)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {q.doc_number ?? `#${q.id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={q.status as StatusKey} />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {formatMinor(q.total_minor, q.currency)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <Stack alignItems="center" mt={1.5}>
              <Pagination count={totalPages} page={page} onChange={(_, v) => setPage(v)} size="small" />
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Invoices Tab
// ---------------------------------------------------------------------------

function InvoicesTab({ customerPublicId, customerIntId }: { customerPublicId: string; customerIntId: number }) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['customer-invoices', customerPublicId, page],
    queryFn: () => customerSubApi.getInvoices(customerPublicId, { page, page_size: 10 }),
    enabled: !!customerPublicId,
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 10)

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" mb={1.5}>
        <PermissionGate permission="invoice.create">
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate(`/invoices/new?customerId=${customerIntId}`)}
          >
            Nouvelle facture
          </Button>
        </PermissionGate>
      </Stack>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState label="Aucune facture pour ce client." />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Référence</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Total</TableCell>
                <TableCell align="right">Payé</TableCell>
                <TableCell align="right">Reste dû</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((inv: any) => (
                <TableRow
                  key={inv.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/invoices/${inv.id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{fmt(inv.created_at)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {inv.doc_number ?? `#${inv.id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={inv.status as StatusKey} />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontFamily="monospace">
                      {formatMinor(inv.total_minor, inv.currency)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontFamily="monospace" color="success.main">
                      {formatMinor(inv.paid_amount_minor, inv.currency)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      fontFamily="monospace"
                      fontWeight={600}
                      color={inv.outstanding_minor > 0 ? 'error.main' : 'text.secondary'}
                    >
                      {formatMinor(inv.outstanding_minor, inv.currency)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <Stack alignItems="center" mt={1.5}>
              <Pagination count={totalPages} page={page} onChange={(_, v) => setPage(v)} size="small" />
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Delivery Notes Tab
// ---------------------------------------------------------------------------

function DeliveryNotesTab({ customerPublicId, customerIntId }: { customerPublicId: string; customerIntId: number }) {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['customer-delivery-notes', customerPublicId, page],
    queryFn: () => customerSubApi.getDeliveryNotes(customerPublicId, { page, page_size: 10 }),
    enabled: !!customerPublicId,
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 10)

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" mb={1.5}>
        <PermissionGate permission="invoice.create">
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate(`/delivery-notes/new?customerId=${customerIntId}`)}
          >
            Nouveau BL
          </Button>
        </PermissionGate>
      </Stack>

      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState label="Aucun bon de livraison pour ce client." />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Référence</TableCell>
                <TableCell>Lignes</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Total TTC</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((dn: any) => (
                <TableRow
                  key={dn.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/delivery-notes/${dn.public_id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">{fmt(dn.created_at)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {dn.doc_number ?? `#${dn.id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={`${dn.lines?.length ?? 0} ligne(s)`}
                      size="small"
                      sx={{ fontSize: '0.65rem', height: 20 }}
                    />
                  </TableCell>
                  <TableCell>
                    <StatusChip status={dn.status as StatusKey} />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                      {formatMinor(dn.total_minor, dn.currency)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalPages > 1 && (
            <Stack alignItems="center" mt={1.5}>
              <Pagination count={totalPages} page={page} onChange={(_, v) => setPage(v)} size="small" />
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Advance Payments Tab
// ---------------------------------------------------------------------------

function AdvancePaymentsTab({ customerIntId }: { customerIntId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['customer-advances', customerIntId],
    queryFn: () => advancePaymentApi.listByCustomer(customerIntId),
    enabled: !!customerIntId,
  })

  const items = data?.items ?? []

  const PAYMENT_METHOD_LABELS: Record<string, string> = {
    cash: 'Espèces',
    card: 'Carte',
    bank_transfer: 'Virement',
    cheque: 'Chèque',
    other: 'Autre',
  }

  return (
    <Box>
      {isLoading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState label="Aucun acompte enregistré pour ce client." />
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Montant</TableCell>
              <TableCell>Méthode</TableCell>
              <TableCell>Référence</TableCell>
              <TableCell>Appliqué sur</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((adv: any) => (
              <TableRow key={adv.id}>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">{fmt(adv.paid_at)}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" fontFamily="monospace" fontWeight={600} color="primary.main">
                    {formatMinor(adv.amount_minor, 'TND')}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{PAYMENT_METHOD_LABELS[adv.payment_method] ?? adv.payment_method}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary" fontFamily="monospace">
                    {adv.reference ?? '—'}
                  </Typography>
                </TableCell>
                <TableCell>
                  {adv.applied_to_invoice_id ? (
                    <Chip
                      label={`Facture #${adv.applied_to_invoice_id}`}
                      size="small"
                      color="success"
                      sx={{ fontSize: '0.65rem', height: 20 }}
                    />
                  ) : (
                    <Chip
                      label="Non appliqué"
                      size="small"
                      sx={{ fontSize: '0.65rem', height: 20, bgcolor: '#FFF7ED', color: '#C2410C' }}
                    />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const TABS = [
  { key: 'repair-orders', label: 'Ordres de réparation' },
  { key: 'quotations', label: 'Devis' },
  { key: 'invoices', label: 'Factures' },
  { key: 'delivery-notes', label: 'Bons de livraison' },
  { key: 'advances', label: 'Acomptes' },
] as const

type TabKey = (typeof TABS)[number]['key']

interface Props {
  customerPublicId: string
  customerIntId: number
}

export function CustomerActivityPanel({ customerPublicId, customerIntId }: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>('repair-orders')

  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
          <Box sx={{ color: 'primary.main' }}>
            <HistoryRoundedIcon sx={{ fontSize: 20 }} />
          </Box>
          <Typography variant="subtitle1" fontWeight={700}>
            Historique &amp; Activité
          </Typography>
        </Stack>
        <Divider sx={{ mb: 0 }} />

        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v as TabKey)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}
        >
          {TABS.map((t) => (
            <Tab key={t.key} value={t.key} label={t.label} sx={{ fontSize: '0.8rem', minHeight: 44 }} />
          ))}
        </Tabs>

        {activeTab === 'repair-orders' && (
          <RepairOrdersTab customerPublicId={customerPublicId} customerIntId={customerIntId} />
        )}
        {activeTab === 'quotations' && (
          <QuotationsTab customerPublicId={customerPublicId} customerIntId={customerIntId} />
        )}
        {activeTab === 'invoices' && (
          <InvoicesTab customerPublicId={customerPublicId} customerIntId={customerIntId} />
        )}
        {activeTab === 'delivery-notes' && (
          <DeliveryNotesTab customerPublicId={customerPublicId} customerIntId={customerIntId} />
        )}
        {activeTab === 'advances' && (
          <AdvancePaymentsTab customerIntId={customerIntId} />
        )}
      </CardContent>
    </Card>
  )
}
