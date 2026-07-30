import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import axios from 'axios'
import {
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import {
  deliveryNoteApi,
  DELIVERY_NOTE_LINE_KIND_LABELS,
  type DeliveryNoteLineKind,
  type DeliveryNoteLineOut,
} from '../../lib/deliveryNoteApi'
import { partsApi, UNCATEGORIZED_CATEGORY, type PartCategory, type PartSummary } from '../../lib/partsApi'
import { parseCreditLimitError, type CreditLimitExceededDetail } from '../../lib/creditOverrideApi'
import { CreditLimitExceededDialog } from '../../components/credit/CreditLimitExceededDialog'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'
import { PermissionGate } from '../../components/auth/PermissionGate'
import type { StatusKey } from '../../components/ui/StatusChip'

const LINE_KINDS: DeliveryNoteLineKind[] = ['part', 'service', 'other']

export function DeliveryNoteDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()

  const [confirmCancel, setConfirmCancel] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [creditLimitDetail, setCreditLimitDetail] = useState<CreditLimitExceededDetail | null>(null)

  // Add-line form state
  const [showAddLine, setShowAddLine] = useState(false)
  const [lineKind, setLineKind] = useState<DeliveryNoteLineKind>('part')
  const [lineDesc, setLineDesc] = useState('')
  const [lineQty, setLineQty] = useState('1')
  const [linePrice, setLinePrice] = useState('')
  const [linePartInput, setLinePartInput] = useState('')
  const [lineSelectedPart, setLineSelectedPart] = useState<PartSummary | null>(null)
  const [lineSelectedCategory, setLineSelectedCategory] = useState<PartCategory | null>(null)
  const [linePartDebounced, setLinePartDebounced] = useState('')
  const partDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Edit/delete line state
  const [editLine, setEditLine] = useState<DeliveryNoteLineOut | null>(null)
  const [editDesc, setEditDesc] = useState('')
  const [editQty, setEditQty] = useState('1')
  const [editPrice, setEditPrice] = useState('')
  const [deleteLineId, setDeleteLineId] = useState<number | null>(null)

  const { data: dn, isLoading, isError } = useQuery({
    queryKey: ['delivery-note', publicId],
    queryFn: () => deliveryNoteApi.get(publicId),
    enabled: !!publicId,
  })

  const { data: partCategories = [] } = useQuery({
    queryKey: ['part-categories', 'for-delivery-note'],
    queryFn: () => partsApi.listCategories({ flat: true }),
    staleTime: 5 * 60 * 1000,
  })

  const { data: partsData, isFetching: partsLoading } = useQuery({
    queryKey: ['parts', 'for-delivery-note-line', lineSelectedCategory?.id, linePartDebounced],
    queryFn: () => partsApi.list({
      search: linePartDebounced || undefined,
      ...(lineSelectedCategory?.id === UNCATEGORIZED_CATEGORY.id
        ? { uncategorized: true }
        : { category_id: lineSelectedCategory?.id }),
      page_size: 50,
    }),
    enabled: lineKind === 'part' && !!lineSelectedCategory,
    placeholderData: (prev) => prev,
  })
  const availableParts = partsData?.items ?? []

  const handlePartInputChange = (v: string) => {
    setLinePartInput(v)
    if (partDebounceRef.current) clearTimeout(partDebounceRef.current)
    partDebounceRef.current = setTimeout(() => setLinePartDebounced(v), 300)
  }

  const resetAddLineForm = () => {
    setLineDesc('')
    setLineQty('1')
    setLinePrice('')
    setLinePartInput('')
    setLinePartDebounced('')
    setLineSelectedPart(null)
    setLineSelectedCategory(null)
    setLineKind('part')
  }

  const addLineMutation = useMutation({
    mutationFn: () => {
      const desc = lineKind === 'part'
        ? (lineSelectedPart?.name ?? linePartInput)
        : lineDesc
      return deliveryNoteApi.addLine(publicId, {
        kind: lineKind,
        part_id: lineKind === 'part' ? lineSelectedPart?.int_id : undefined,
        description: desc,
        quantity: parseInt(lineQty, 10) || 1,
        unit_price_minor: Math.round(parseFloat(linePrice) * 100),
      })
    },
    onSuccess: (updated) => {
      success('Ligne ajoutée')
      setShowAddLine(false)
      resetAddLineForm()
      queryClient.setQueryData(['delivery-note', publicId], updated)
    },
    onError: () => toastError("Impossible d'ajouter la ligne."),
  })

  function openEditLine(line: DeliveryNoteLineOut) {
    setEditLine(line)
    setEditDesc(line.description)
    setEditQty(line.quantity)
    setEditPrice(String(line.unit_price_minor / 100))
  }

  const updateLineMutation = useMutation({
    mutationFn: () => deliveryNoteApi.updateLine(publicId, editLine!.id, {
      description: editDesc,
      quantity: parseFloat(editQty) || 1,
      unit_price_minor: Math.round(parseFloat(editPrice) * 100),
    }),
    onSuccess: (updated) => {
      success('Ligne modifiée')
      setEditLine(null)
      queryClient.setQueryData(['delivery-note', publicId], updated)
    },
    onError: () => toastError('Impossible de modifier la ligne.'),
  })

  const removeLineMutation = useMutation({
    mutationFn: (lineId: number) => deliveryNoteApi.removeLine(publicId, lineId),
    onSuccess: (updated) => {
      success('Ligne supprimée')
      setDeleteLineId(null)
      queryClient.setQueryData(['delivery-note', publicId], updated)
    },
    onError: () => { toastError('Impossible de supprimer la ligne.'); setDeleteLineId(null) },
  })

  const handleIssue = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.issue(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison émis')
    } catch (err) {
      const creditError = parseCreditLimitError(err)
      if (creditError) {
        setCreditLimitDetail(creditError)
      } else {
        toastError('Erreur lors de l\'émission.')
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleMarkDelivered = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.markDelivered(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison marqué livré')
    } catch { toastError('Erreur lors de la mise à jour.') }
    finally { setActionLoading(false) }
  }

  const handleConvertToInvoice = async () => {
    setActionLoading(true)
    try {
      const updated = await deliveryNoteApi.convertToInvoice(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Facture créée depuis ce BL')
      if (updated.invoice_public_id) {
        navigate(`/invoices/${updated.invoice_public_id}`)
      }
    } catch { toastError('Erreur lors de la conversion.') }
    finally { setActionLoading(false) }
  }

  const handleCancel = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.cancel(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison annulé')
      setConfirmCancel(false)
    } catch { toastError('Erreur lors de l\'annulation.') }
    finally { setActionLoading(false) }
  }

  const handlePdfPreview = async () => {
    if (!dn) return
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.get(
        `/api/v1/pdf/delivery-notes/${dn.id}`,
        {
          responseType: 'blob',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      toastError('Impossible de générer le PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !dn) return <Typography color="error">Impossible de charger ce bon de livraison.</Typography>

  const isDraft = dn.status === 'draft'
  const isIssued = dn.status === 'issued'
  const isDelivered = dn.status === 'delivered'
  const canConvert = (isIssued || isDelivered) && !dn.invoice_id

  return (
    <Box>
      <PageHeader
        title={dn.doc_number ?? `BL #${dn.id}`}
        subtitle="Bon de livraison"
        breadcrumbs={[
          { label: 'Facturation', href: '/invoices' },
          { label: dn.doc_number ?? `BL #${dn.id}` },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <StatusChip status={dn.status as StatusKey} />
            {dn.status !== 'draft' && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<PictureAsPdfRoundedIcon />}
                onClick={handlePdfPreview}
                disabled={pdfLoading}
              >
                {pdfLoading ? 'Génération…' : 'Aperçu PDF'}
              </Button>
            )}
            <PermissionGate permission="invoice.issue">
              {isDraft && (
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleIssue}
                  disabled={actionLoading}
                >
                  Émettre
                </Button>
              )}
              {isIssued && (
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<LocalShippingRoundedIcon />}
                  onClick={handleMarkDelivered}
                  disabled={actionLoading}
                >
                  Marquer livré
                </Button>
              )}
            </PermissionGate>
            <PermissionGate permission="invoice.create">
              {canConvert && (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<SwapHorizRoundedIcon />}
                  onClick={handleConvertToInvoice}
                  disabled={actionLoading}
                >
                  Convertir en facture
                </Button>
              )}
            </PermissionGate>
            <PermissionGate permission="invoice.cancel">
              {(isDraft || isIssued) && (
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<CancelRoundedIcon />}
                  onClick={() => setConfirmCancel(true)}
                  disabled={actionLoading}
                >
                  Annuler
                </Button>
              )}
            </PermissionGate>
          </Stack>
        }
      />

      <Stack spacing={3}>
        {/* Header info */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
              <Box sx={{ color: 'primary.main' }}>
                <ReceiptLongRoundedIcon sx={{ fontSize: 20 }} />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>Détails</Typography>
            </Stack>
            <Divider sx={{ mb: 2 }} />
            <Stack spacing={1}>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Référence</Typography>
                <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                  {dn.doc_number ?? '—'}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Statut</Typography>
                <StatusChip status={dn.status as StatusKey} />
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Devise</Typography>
                <Typography variant="body2">{dn.currency}</Typography>
              </Stack>
              {dn.issued_at && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Date d'émission</Typography>
                  <Typography variant="body2">
                    {new Date(dn.issued_at).toLocaleDateString('fr-FR')}
                  </Typography>
                </Stack>
              )}
              {dn.delivered_at && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Date de livraison</Typography>
                  <Typography variant="body2">
                    {new Date(dn.delivered_at).toLocaleDateString('fr-FR')}
                  </Typography>
                </Stack>
              )}
              {dn.invoice_id && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Facture associée</Typography>
                  <Button
                    size="small"
                    variant="text"
                    sx={{ p: 0, minWidth: 0 }}
                    onClick={() => navigate(`/invoices/${dn.invoice_public_id ?? dn.invoice_id}`)}
                  >
                    Facture #{dn.invoice_id}
                  </Button>
                </Stack>
              )}
              {dn.notes && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Notes</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ maxWidth: '60%', textAlign: 'right' }}>
                    {dn.notes}
                  </Typography>
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>

        {/* Lines */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
              <Box sx={{ color: 'primary.main' }}>
                <LocalShippingRoundedIcon sx={{ fontSize: 20 }} />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>Lignes</Typography>
              {isDraft && (
                <Box ml="auto !important">
                  <PermissionGate permission="invoice.update">
                    <Button size="small" variant="outlined" startIcon={<AddRoundedIcon />}
                      onClick={() => { setShowAddLine(v => !v); if (showAddLine) resetAddLineForm() }}
                      sx={{ textTransform: 'none', fontWeight: 600 }}>
                      Ajouter une ligne
                    </Button>
                  </PermissionGate>
                </Box>
              )}
            </Stack>
            <Divider sx={{ mb: showAddLine && isDraft ? 0 : 2 }} />

            {showAddLine && isDraft && (
              <Box sx={{ py: 2, px: 0.5, borderBottom: '1px solid #E2E8F0', mb: 2 }}>
                <Stack spacing={1.5}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                    <TextField
                      select size="small" label="Type" value={lineKind}
                      onChange={e => {
                        setLineKind(e.target.value as DeliveryNoteLineKind)
                        setLineDesc('')
                        setLinePartInput('')
                        setLinePartDebounced('')
                        setLineSelectedPart(null)
                        setLineSelectedCategory(null)
                      }}
                      sx={{ minWidth: 140 }}
                    >
                      {LINE_KINDS.map(k => <MenuItem key={k} value={k}>{DELIVERY_NOTE_LINE_KIND_LABELS[k]}</MenuItem>)}
                    </TextField>
                    {lineKind !== 'part' && (
                      <TextField size="small" label="Description" value={lineDesc}
                        onChange={e => setLineDesc(e.target.value)} sx={{ flex: 1 }} required />
                    )}
                  </Stack>

                  {lineKind === 'part' && (
                    <>
                      <Autocomplete
                        options={[...partCategories, UNCATEGORIZED_CATEGORY]}
                        value={lineSelectedCategory}
                        onChange={(_e, v) => {
                          setLineSelectedCategory(v)
                          setLineSelectedPart(null)
                          setLinePartInput('')
                          setLinePartDebounced('')
                          setLinePrice('')
                        }}
                        getOptionLabel={(c) => c.name}
                        isOptionEqualToValue={(a, b) => a.id === b.id}
                        noOptionsText="Aucune catégorie"
                        renderInput={(params) => (
                          <TextField {...params} label="Catégorie *" size="small" fullWidth />
                        )}
                      />
                      {lineSelectedCategory && (
                        <Autocomplete
                          options={availableParts}
                          loading={partsLoading}
                          value={lineSelectedPart}
                          onChange={(_e, v) => {
                            setLineSelectedPart(v)
                            if (v) {
                              setLinePartInput(`${v.sku_code} — ${v.name}`)
                              setLinePrice(String(v.selling_price_minor / 100))
                            } else {
                              setLinePartInput('')
                              setLinePartDebounced('')
                              setLinePrice('')
                            }
                          }}
                          inputValue={linePartInput}
                          onInputChange={(_e, v, reason) => {
                            if (reason === 'input' || reason === 'clear') handlePartInputChange(v)
                          }}
                          filterOptions={(x) => x}
                          getOptionLabel={(p) => `${p.sku_code} — ${p.name}`}
                          isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                          getOptionDisabled={(p) => p.stock_on_hand === 0}
                          noOptionsText={linePartDebounced ? 'Aucune pièce trouvée' : 'Tapez pour rechercher…'}
                          renderOption={(props, p) => (
                            <Box component="li" {...props} key={p.int_id}>
                              <Stack direction="row" justifyContent="space-between" alignItems="center" width="100%">
                                <Stack>
                                  <Typography variant="body2" fontWeight={600}>{p.name}</Typography>
                                  <Typography variant="caption" color="text.secondary" fontFamily="monospace">{p.sku_code}</Typography>
                                </Stack>
                                <Chip
                                  label={p.stock_on_hand === 0 ? 'Rupture' : `${p.stock_on_hand} en stock`}
                                  size="small"
                                  sx={{
                                    ml: 2,
                                    bgcolor: p.stock_on_hand === 0 ? '#FEE2E2' : '#DCFCE7',
                                    color: p.stock_on_hand === 0 ? '#DC2626' : '#16A34A',
                                    fontWeight: 600,
                                    fontSize: '0.7rem',
                                    flexShrink: 0,
                                  }}
                                />
                              </Stack>
                            </Box>
                          )}
                          renderInput={(params) => (
                            <TextField
                              {...params}
                              label="Pièce *"
                              size="small"
                              fullWidth
                              InputProps={{
                                ...params.InputProps,
                                endAdornment: (
                                  <>
                                    {partsLoading && <CircularProgress size={16} />}
                                    {params.InputProps.endAdornment}
                                  </>
                                ),
                              }}
                            />
                          )}
                        />
                      )}
                    </>
                  )}

                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                    <TextField size="small" label="Quantité" type="number" value={lineQty}
                      onChange={e => setLineQty(e.target.value)}
                      sx={{ width: 100 }} inputProps={{ min: 1, step: 1 }} />
                    <TextField size="small" label="Prix" type="number" value={linePrice}
                      onChange={e => setLinePrice(e.target.value)}
                      sx={{ flex: 1 }} inputProps={{ min: 0, step: 1 }}
                      InputProps={{ endAdornment: <Typography variant="caption" color="text.secondary">{dn.currency}</Typography> }}
                      required />
                  </Stack>

                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    <Button size="small" onClick={() => { setShowAddLine(false); resetAddLineForm() }} sx={{ textTransform: 'none' }}>
                      Annuler
                    </Button>
                    <Button size="small" variant="contained"
                      disabled={
                        addLineMutation.isPending || !linePrice ||
                        (lineKind === 'part' ? !lineSelectedPart : !lineDesc.trim())
                      }
                      onClick={() => addLineMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}>
                      {addLineMutation.isPending ? 'Ajout…' : 'Ajouter'}
                    </Button>
                  </Stack>
                </Stack>
              </Box>
            )}

            {dn.lines.length === 0 ? (
              <Typography variant="body2" color="text.disabled" py={1}>
                Aucune ligne.{isDraft && ' Cliquez sur "Ajouter une ligne" pour commencer.'}
              </Typography>
            ) : (
              <>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell align="right">Qté</TableCell>
                      <TableCell align="right">P.U.</TableCell>
                      <TableCell align="right">TVA %</TableCell>
                      <TableCell align="right">Total TTC</TableCell>
                      {isDraft && <TableCell align="right">Actions</TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dn.lines.map((line) => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Chip
                            label={DELIVERY_NOTE_LINE_KIND_LABELS[line.kind] ?? line.kind}
                            size="small"
                            sx={{ fontSize: '0.65rem', height: 20 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{line.description}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">{line.quantity}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">
                            {formatMinor(line.unit_price_minor, dn.currency)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">{line.vat_rate}%</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                            {formatMinor(
                              line.line_total_minor + Math.round(line.line_total_minor * parseFloat(String(line.vat_rate)) / 100),
                              dn.currency,
                            )}
                          </Typography>
                        </TableCell>
                        {isDraft && (
                          <TableCell align="right">
                            <PermissionGate permission="invoice.update">
                              <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                <Tooltip title="Modifier">
                                  <IconButton size="small" onClick={() => openEditLine(line)}>
                                    <EditRoundedIcon sx={{ fontSize: 15 }} />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Supprimer">
                                  <IconButton size="small" onClick={() => setDeleteLineId(line.id)}>
                                    <DeleteRoundedIcon sx={{ fontSize: 15 }} />
                                  </IconButton>
                                </Tooltip>
                              </Stack>
                            </PermissionGate>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <Stack alignItems="flex-end" mt={2} spacing={0.5}>
                  <Stack direction="row" spacing={4}>
                    <Typography variant="body2" color="text.secondary">Sous-total HT</Typography>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatMinor(dn.subtotal_minor, dn.currency)}
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={4}>
                    <Typography variant="body2" color="text.secondary">TVA</Typography>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatMinor(dn.vat_minor, dn.currency)}
                    </Typography>
                  </Stack>
                  <Divider sx={{ width: 200 }} />
                  <Stack direction="row" spacing={4}>
                    <Typography variant="subtitle2" fontWeight={700}>Total TTC</Typography>
                    <Typography variant="subtitle2" fontFamily="monospace" fontWeight={700}>
                      {formatMinor(dn.total_minor, dn.currency)}
                    </Typography>
                  </Stack>
                </Stack>
              </>
            )}
          </CardContent>
        </Card>
      </Stack>

      <ConfirmDialog
        open={confirmCancel}
        title="Annuler ce bon de livraison ?"
        message="Cette action est irréversible."
        confirmLabel="Annuler le BL"
        dangerous
        loading={actionLoading}
        onConfirm={handleCancel}
        onCancel={() => setConfirmCancel(false)}
      />

      <CreditLimitExceededDialog
        open={creditLimitDetail !== null}
        detail={creditLimitDetail}
        documentPublicId={publicId}
        onClose={() => setCreditLimitDetail(null)}
      />

      <Dialog open={editLine !== null} onClose={() => setEditLine(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Modifier la ligne</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              size="small" label="Description" value={editDesc}
              onChange={e => setEditDesc(e.target.value)} fullWidth required
            />
            <Stack direction="row" spacing={1.5}>
              <TextField size="small" label="Quantité" type="number" value={editQty}
                onChange={e => setEditQty(e.target.value)}
                sx={{ width: 100 }} inputProps={{ min: 1, step: 1 }} />
              <TextField size="small" label="Prix" type="number" value={editPrice}
                onChange={e => setEditPrice(e.target.value)}
                sx={{ flex: 1 }} inputProps={{ min: 0, step: 1 }}
                InputProps={{ endAdornment: <Typography variant="caption" color="text.secondary">{dn.currency}</Typography> }}
                required />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setEditLine(null)} disabled={updateLineMutation.isPending} sx={{ textTransform: 'none' }}>
            Annuler
          </Button>
          <Button variant="contained"
            disabled={updateLineMutation.isPending || !editDesc.trim() || !editPrice}
            onClick={() => updateLineMutation.mutate()}
            sx={{ textTransform: 'none', fontWeight: 700 }}>
            {updateLineMutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deleteLineId !== null}
        title="Supprimer cette ligne ?"
        message="Cette action est irréversible."
        confirmLabel="Supprimer"
        dangerous
        loading={removeLineMutation.isPending}
        onConfirm={() => deleteLineId !== null && removeLineMutation.mutate(deleteLineId)}
        onCancel={() => setDeleteLineId(null)}
      />
    </Box>
  )
}
