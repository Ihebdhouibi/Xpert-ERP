import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import DownloadRoundedIcon from '@mui/icons-material/DownloadRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import { accountingExportApi, type AccountingExportOut } from '../../lib/accountingExportApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { useToast } from '../../contexts/ToastContext'

const FORMAT_OPTIONS = [
  { value: 'sage', label: 'Sage' },
  { value: 'cegid', label: 'Cegid' },
  { value: 'ebp', label: 'EBP' },
  { value: 'generic_csv', label: 'CSV générique' },
]

function todayStr() { return new Date().toISOString().slice(0, 10) }
function monthStartStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

const columns: Column<AccountingExportOut>[] = [
  {
    id: 'period',
    label: 'Période',
    render: row => (
      <Typography variant="body2" fontWeight={600}>
        {new Date(row.period_start).toLocaleDateString('fr-FR')} →{' '}
        {new Date(row.period_end).toLocaleDateString('fr-FR')}
      </Typography>
    ),
  },
  {
    id: 'format',
    label: 'Format',
    width: 120,
    render: row => (
      <Chip
        label={row.format.toUpperCase()}
        size="small"
        sx={{ fontWeight: 700, bgcolor: '#F1F5F9', fontSize: '0.6875rem' }}
      />
    ),
  },
  {
    id: 'counts',
    label: 'Documents',
    render: row =>
      row.record_counts ? (
        <Stack direction="row" spacing={1} flexWrap="wrap">
          {Object.entries(row.record_counts).map(([k, v]) => (
            <Typography key={k} variant="caption" color="text.secondary">
              {k}: <strong>{v}</strong>
            </Typography>
          ))}
        </Stack>
      ) : <Typography variant="caption" color="text.disabled">—</Typography>,
  },
  {
    id: 'status',
    label: 'Statut',
    width: 120,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={0.75}>
        {row.status === 'done' ? (
          <CheckCircleRoundedIcon sx={{ color: '#16A34A', fontSize: 16 }} />
        ) : row.status === 'error' ? (
          <WarningAmberRoundedIcon sx={{ color: '#EF4444', fontSize: 16 }} />
        ) : null}
        <Typography
          variant="caption"
          fontWeight={600}
          color={row.status === 'done' ? 'success.main' : row.status === 'error' ? 'error.main' : 'text.secondary'}
        >
          {row.status === 'done' ? 'Terminé' : row.status === 'error' ? 'Erreur' : 'En cours'}
        </Typography>
      </Stack>
    ),
  },
  {
    id: 'date',
    label: 'Exporté le',
    width: 130,
    render: row => (
      <Typography variant="caption" color="text.secondary">
        {row.exported_at ? new Date(row.exported_at).toLocaleString('fr-FR', {
          day: '2-digit', month: '2-digit', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        }) : '—'}
      </Typography>
    ),
  },
  {
    id: 'download',
    label: '',
    width: 60,
    align: 'right',
    render: row =>
      row.status === 'done' && row.file_storage_key ? (
        <Button
          size="small"
          variant="outlined"
          startIcon={<DownloadRoundedIcon />}
          onClick={async e => {
            e.stopPropagation()
            const { url } = await accountingExportApi.getDownloadUrl(row.public_id)
            window.open(url, '_blank')
          }}
          sx={{ fontSize: '0.75rem' }}
        >
          ZIP
        </Button>
      ) : null,
  },
]

export function AccountingExportPage() {
  const qc = useQueryClient()
  const { success, error } = useToast()
  const [page, setPage] = useState(0)
  const [periodStart, setPeriodStart] = useState(monthStartStr)
  const [periodEnd, setPeriodEnd] = useState(todayStr)
  const [format, setFormat] = useState('generic_csv')

  const { data: preview, isLoading: previewLoading } = useQuery({
    queryKey: ['accounting-preview', periodStart, periodEnd],
    queryFn: () => accountingExportApi.preview(periodStart, periodEnd),
    enabled: !!(periodStart && periodEnd),
    staleTime: 30_000,
  })

  const { data, isLoading, isError } = useQuery({
    queryKey: ['accounting-exports', page],
    queryFn: () => accountingExportApi.list({ page: page + 1, page_size: 20 }),
  })

  const createMutation = useMutation({
    mutationFn: () => accountingExportApi.create({ period_start: periodStart, period_end: periodEnd, format }),
    onSuccess: () => {
      success('Export lancé. Le fichier sera disponible dans quelques instants.')
      void qc.invalidateQueries({ queryKey: ['accounting-exports'] })
    },
    onError: () => error('Erreur lors du lancement de l\'export.'),
  })

  const hasPending = preview
    ? preview.pending_invoices + preview.pending_payments + preview.pending_supplier_invoices > 0
    : false

  return (
    <Box>
      <PageHeader
        title="Export comptable"
        subtitle="Exportez vos données vers votre logiciel de comptabilité"
      />

      {/* Export configuration */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="subtitle1" fontWeight={700} mb={2}>
            Nouvel export
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} mb={2.5} flexWrap="wrap">
            <TextField
              label="Période du"
              type="date"
              value={periodStart}
              onChange={e => setPeriodStart(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <TextField
              label="Au"
              type="date"
              value={periodEnd}
              onChange={e => setPeriodEnd(e.target.value)}
              InputLabelProps={{ shrink: true }}
              sx={{ width: 180 }}
            />
            <TextField
              label="Format"
              select
              value={format}
              onChange={e => setFormat(e.target.value)}
              sx={{ width: 180 }}
            >
              {FORMAT_OPTIONS.map(o => (
                <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
              ))}
            </TextField>
          </Stack>

          {/* Preview */}
          {preview && !previewLoading && (
            <Card variant="outlined" sx={{ bgcolor: '#F8FAFC', mb: 2.5 }}>
              <CardContent sx={{ p: 2 }}>
                <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5}>
                  APERÇU DE LA PÉRIODE
                </Typography>
                <Stack direction="row" spacing={3} flexWrap="wrap">
                  <Box>
                    <Typography variant="h6" fontWeight={700}>{preview.pending_invoices}</Typography>
                    <Typography variant="caption" color="text.secondary">Factures à exporter</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h6" fontWeight={700}>{preview.pending_payments}</Typography>
                    <Typography variant="caption" color="text.secondary">Paiements à exporter</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h6" fontWeight={700}>{preview.pending_supplier_invoices}</Typography>
                    <Typography variant="caption" color="text.secondary">Fournisseurs à exporter</Typography>
                  </Box>
                </Stack>
                {(preview.already_exported_invoices > 0 || preview.already_exported_payments > 0) && (
                  <>
                    <Divider sx={{ my: 1.5 }} />
                    <Typography variant="caption" color="text.secondary">
                      Déjà exportés sur cette période : {preview.already_exported_invoices} factures,{' '}
                      {preview.already_exported_payments} paiements
                    </Typography>
                  </>
                )}
                {preview.warning && (
                  <Alert severity="warning" sx={{ mt: 1.5, py: 0.5 }}>{preview.warning}</Alert>
                )}
              </CardContent>
            </Card>
          )}

          <Button
            variant="contained"
            startIcon={<UploadFileRoundedIcon />}
            onClick={() => createMutation.mutate()}
            disabled={!hasPending || createMutation.isPending}
            size="large"
          >
            {createMutation.isPending ? 'Export en cours…' : `Lancer l'export ${format.toUpperCase()}`}
          </Button>
          {!hasPending && preview && (
            <Typography variant="caption" color="text.secondary" ml={2}>
              Aucun document en attente pour cette période.
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* History */}
      <Typography variant="h6" fontWeight={700} mb={2}>Historique des exports</Typography>
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.public_id}
        loading={isLoading}
        error={isError}
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun export"
        emptyDescription="Lancez votre premier export comptable ci-dessus."
      />
    </Box>
  )
}
