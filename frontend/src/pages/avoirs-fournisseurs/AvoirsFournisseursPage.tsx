import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Box, Stack, Typography } from '@mui/material'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import {
  bonRetourApi,
  SUPPLIER_CREDIT_NOTE_STATUS_LABELS,
  type SupplierCreditNoteOut,
  type SupplierCreditNoteStatus,
} from '../../lib/bonRetourApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

const columns: Column<SupplierCreditNoteOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 200,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34, height: 34, borderRadius: '9px', bgcolor: '#F1F5F9',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <ReceiptRoundedIcon sx={{ color: '#334155', fontSize: 17 }} />
        </Box>
        <Stack spacing={0.25}>
          <Typography variant="body2" fontWeight={700} fontFamily="monospace">
            {row.doc_number ?? (
              <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
                Brouillon
              </Typography>
            )}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {new Date(row.created_at).toLocaleDateString('fr-FR')}
          </Typography>
        </Stack>
      </Stack>
    ),
  },
  {
    id: 'supplier',
    label: 'Fournisseur',
    render: row => (
      <Typography variant="body2" noWrap sx={{ maxWidth: 240 }}>
        {row.supplier_name ?? `Fournisseur #${row.supplier_id}`}
      </Typography>
    ),
  },
  {
    id: 'bon_de_retour',
    label: 'Bon de retour',
    width: 160,
    render: row =>
      row.bon_de_retour_public_id ? (
        <Typography variant="caption" fontFamily="monospace" color="text.secondary">
          {row.bon_de_retour_public_id.slice(0, 8).toUpperCase()}
        </Typography>
      ) : (
        <Typography variant="caption" color="text.disabled">—</Typography>
      ),
  },
  {
    id: 'amount',
    label: 'Montant TTC',
    align: 'right',
    width: 130,
    render: row => (
      <Typography variant="body2" fontWeight={700}>
        {formatMinor(row.total_ttc_minor, 'MAD')}
      </Typography>
    ),
  },
  {
    id: 'exported',
    label: 'Exporté',
    width: 90,
    render: row => (
      <Typography variant="caption" color={row.is_exported ? 'success.main' : 'text.disabled'} fontWeight={600}>
        {row.is_exported ? 'Oui' : 'Non'}
      </Typography>
    ),
  },
  {
    id: 'status',
    label: 'Statut',
    width: 110,
    render: row => (
      <StatusChip
        status={row.status}
        label={SUPPLIER_CREDIT_NOTE_STATUS_LABELS[row.status as SupplierCreditNoteStatus] ?? row.status}
      />
    ),
  },
]

export function AvoirsFournisseursPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['supplier-credit-notes', page],
    queryFn: () => bonRetourApi.listSupplierCreditNotes({ page: page + 1, page_size: 20 }),
  })

  return (
    <Box>
      <PageHeader
        title="Avoirs fournisseurs"
        subtitle="Avoirs émis suite à des retours de pièces fournisseurs"
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.public_id}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les avoirs fournisseurs."
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun avoir fournisseur"
        emptyDescription="Les avoirs fournisseurs sont créés depuis un bon de retour fournisseur confirmé."
        onRowClick={row =>
          row.bon_de_retour_public_id
            ? navigate(`/bon-retour/${row.bon_de_retour_public_id}`)
            : undefined
        }
      />
    </Box>
  )
}
