import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Pagination,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { deliveryNoteApi } from '../../lib/deliveryNoteApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { PermissionGate } from '../../components/auth/PermissionGate'
import type { StatusKey } from '../../components/ui/StatusChip'

export function DeliveryNotesListPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['delivery-notes', page],
    queryFn: () => deliveryNoteApi.list({ page, page_size: 25 }),
  })

  const items = data?.items ?? []
  const totalPages = Math.ceil((data?.total ?? 0) / 25)

  return (
    <Box>
      <PageHeader
        title="Bons de livraison"
        breadcrumbs={[{ label: 'Facturation' }, { label: 'Bons de livraison' }]}
        actions={
          <PermissionGate permission="invoice.create">
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/delivery-notes/new')}
            >
              Nouveau BL
            </Button>
          </PermissionGate>
        }
      />

      {isLoading ? (
        <Typography color="text.secondary" py={4} textAlign="center">Chargement…</Typography>
      ) : items.length === 0 ? (
        <Typography color="text.secondary" py={4} textAlign="center">Aucun bon de livraison.</Typography>
      ) : (
        <>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Référence</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Total TTC</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((dn) => (
                <TableRow
                  key={dn.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/delivery-notes/${dn.public_id}`)}
                >
                  <TableCell>
                    {new Date(dn.created_at).toLocaleDateString('fr-FR')}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                      {dn.doc_number ?? `#${dn.id}`}
                    </Typography>
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
            <Stack alignItems="center" mt={2}>
              <Pagination count={totalPages} page={page} onChange={(_, v) => setPage(v)} />
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}
