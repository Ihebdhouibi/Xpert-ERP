import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Stack,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import { creditNoteApi, CREDIT_NOTE_STATUS_LABELS, type CreditNoteOut } from '../../lib/creditNoteApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'

const columns: Column<CreditNoteOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 150,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: '#FFF7ED',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 17 }} />
        </Box>
        <Typography variant="body2" fontWeight={700} fontFamily="monospace">
          {row.doc_number ?? (
            <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
              Brouillon
            </Typography>
          )}
        </Typography>
      </Stack>
    ),
  },
  {
    id: 'invoice',
    label: 'Facture liée',
    width: 120,
    render: row => (
      <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
        Facture #{row.invoice_id}
      </Typography>
    ),
  },
  {
    id: 'amount',
    label: 'Montant',
    align: 'right',
    width: 120,
    render: row => (
      <Typography variant="body2" fontWeight={700} color="error.main">
        -{formatMinor(row.total_minor)}
      </Typography>
    ),
  },
  {
    id: 'reason',
    label: 'Motif',
    render: row => (
      <Typography variant="body2" color="text.secondary" noWrap sx={{ maxWidth: 280 }}>
        {row.reason ?? '—'}
      </Typography>
    ),
  },
  {
    id: 'status',
    label: 'Statut',
    width: 110,
    render: row => <StatusChip status={row.status} label={CREDIT_NOTE_STATUS_LABELS[row.status]} />,
  },
  {
    id: 'date',
    label: 'Créé le',
    width: 110,
    render: row => (
      <Typography variant="caption" color="text.secondary">
        {new Date(row.created_at).toLocaleDateString('fr-FR')}
      </Typography>
    ),
  },
]

export function CreditNotesPage() {
  const qc = useQueryClient()
  const { success, error } = useToast()
  const [page, setPage] = useState(0)
  const [voidTarget, setVoidTarget] = useState<CreditNoteOut | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['credit-notes', page],
    queryFn: () => creditNoteApi.list({ page: page + 1, page_size: 20 }),
  })

  const voidMutation = useMutation({
    mutationFn: (id: number) => creditNoteApi.void(id),
    onSuccess: () => {
      success('Avoir annulé.')
      setVoidTarget(null)
      void qc.invalidateQueries({ queryKey: ['credit-notes'] })
    },
    onError: () => error('Impossible d\'annuler cet avoir.'),
  })

  return (
    <Box>
      <PageHeader
        title="Avoirs"
        subtitle="Notes de crédit et remboursements clients"
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} disabled>
            Nouvel avoir
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => String(r.id)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les avoirs."
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun avoir"
        emptyDescription="Les avoirs sont créés à partir d'une facture existante."
      />

      <ConfirmDialog
        open={voidTarget !== null}
        title="Annuler l'avoir"
        message={`Voulez-vous annuler l'avoir ${voidTarget?.doc_number ?? `#${voidTarget?.id}`} ? Cette action est irréversible.`}
        confirmLabel="Annuler l'avoir"
        dangerous
        loading={voidMutation.isPending}
        onConfirm={() => voidTarget && voidMutation.mutate(voidTarget.id)}
        onCancel={() => setVoidTarget(null)}
      />
    </Box>
  )
}
