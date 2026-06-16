import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Box, Button, Stack, Tab, Tabs, Typography } from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import AssignmentReturnRoundedIcon from '@mui/icons-material/AssignmentReturnRounded'
import {
  bonRetourApi,
  BON_RETOUR_STATUS_LABELS,
  type BonRetourOut,
  type BonRetourPartyType,
} from '../../lib/bonRetourApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

const columns: Column<BonRetourOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 190,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34, height: 34, borderRadius: '9px', bgcolor: '#FFF7ED',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}
        >
          <AssignmentReturnRoundedIcon sx={{ color: '#EA580C', fontSize: 17 }} />
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
    id: 'party',
    label: 'Tiers',
    render: row => (
      <Typography variant="body2" noWrap sx={{ maxWidth: 240 }}>
        {row.party_type === 'supplier'
          ? row.supplier_name ?? `Fournisseur #${row.supplier_id}`
          : row.customer_name ?? `Client #${row.customer_id}`}
      </Typography>
    ),
  },
  {
    id: 'amount',
    label: 'Montant TTC',
    align: 'right',
    width: 130,
    render: row => (
      <Typography variant="body2" fontWeight={700}>
        {formatMinor(row.total_minor, row.currency)}
      </Typography>
    ),
  },
  {
    id: 'avoir',
    label: 'Avoir',
    width: 130,
    render: row => {
      const doc = row.credit_note_doc_number ?? row.supplier_credit_note_doc_number
      return doc ? (
        <Typography variant="caption" color="success.main" fontWeight={600} fontFamily="monospace">
          {doc}
        </Typography>
      ) : (
        <Typography variant="caption" color="text.disabled">—</Typography>
      )
    },
  },
  {
    id: 'status',
    label: 'Statut',
    width: 120,
    render: row => <StatusChip status={row.status} label={BON_RETOUR_STATUS_LABELS[row.status]} />,
  },
]

export function BonRetourListPage() {
  const navigate = useNavigate()
  const [party, setParty] = useState<BonRetourPartyType>('supplier')
  const [page, setPage] = useState(0)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['bon-de-retour', party, page],
    queryFn: () => bonRetourApi.list({ party_type: party, page: page + 1, page_size: 20 }),
  })

  const handleParty = (_: unknown, value: BonRetourPartyType | null) => {
    if (value) {
      setParty(value)
      setPage(0)
    }
  }

  return (
    <Box>
      <PageHeader
        title="Bons de retour"
        subtitle="Retours physiques de pièces — réintégration ou sortie de stock"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate(`/bon-retour/new?party=${party}`)}
            sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
          >
            Nouveau bon de retour
          </Button>
        }
      />

      <Tabs value={party} onChange={handleParty} sx={{ mb: 2 }}>
        <Tab label="Fournisseurs" value="supplier" />
        <Tab label="Clients" value="client" />
      </Tabs>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.public_id}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les bons de retour."
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun bon de retour"
        emptyDescription={
          party === 'supplier'
            ? 'Enregistrez le retour de pièces défectueuses à un fournisseur.'
            : "Enregistrez le retour d'une pièce par un client."
        }
        onRowClick={row => navigate(`/bon-retour/${row.public_id}`)}
      />
    </Box>
  )
}
