import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import { partsApi, type PartSummary, type PartCategory } from '../../lib/partsApi'
import { invoiceApi, type InvoiceLineOut, type InvoiceOut } from '../../lib/invoiceApi'
import { formatMinor } from '../ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

interface Props {
  open: boolean
  onClose: () => void
  invoicePublicId: string
  invoiceVersion: number
  editLine?: InvoiceLineOut | null
  onSaved: (updated: InvoiceOut) => void
}

export function AddInvoiceLineDialog({
  open,
  onClose,
  invoicePublicId,
  invoiceVersion,
  editLine,
  onSaved,
}: Props) {
  const { error: toastError } = useToast()
  const isEdit = !!editLine

  const [mode, setMode] = useState<'part' | 'prestation'>('part')

  // Part mode state
  const [selectedCategory, setSelectedCategory] = useState<PartCategory | null>(null)
  const [selectedPart, setSelectedPart] = useState<PartSummary | null>(null)
  const [partSearch, setPartSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [partDiscount, setPartDiscount] = useState('0')

  // Prestation mode state
  const [description, setDescription] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [prestDiscount, setPrestDiscount] = useState('0')

  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Initialize from editLine when dialog opens
  useEffect(() => {
    if (!open) return
    if (editLine) {
      if (editLine.kind === 'part') {
        setMode('part')
        // Synthetic part so submit logic has all values without an extra API call
        setSelectedPart({
          id: '',
          int_id: editLine.part_id!,
          sku_code: '',
          name: editLine.description,
          description: null,
          category_id: null,
          unit_of_measure: '',
          purchase_price_minor: 0,
          selling_price_minor: editLine.unit_price_minor,
          supplier_hint_id: null,
          reorder_threshold: null,
          reorder_quantity: null,
          status: 'active',
          stock_on_hand: 1, // synthetic — just needs to be > 0 so submit isn't blocked
          version: 0,
          created_at: '',
          updated_at: '',
        })
        setQuantity(editLine.quantity)
        setPartDiscount(parseFloat(editLine.discount_percent).toString())
      } else {
        setMode('prestation')
        setDescription(editLine.description)
        setUnitPrice((editLine.unit_price_minor / 100).toFixed(2))
        setPrestDiscount(parseFloat(editLine.discount_percent).toString())
      }
    } else {
      setMode('part')
      setSelectedCategory(null)
      setSelectedPart(null)
      setPartSearch('')
      setDebouncedSearch('')
      setQuantity('1')
      setPartDiscount('0')
      setDescription('')
      setUnitPrice('')
      setPrestDiscount('0')
    }
  }, [open, editLine])

  // Debounce search
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => setDebouncedSearch(partSearch), 300)
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  }, [partSearch])

  // Categories — only needed for add mode
  const { data: categories = [] } = useQuery({
    queryKey: ['part-categories'],
    queryFn: () => partsApi.listCategories({ flat: true }),
    enabled: open && mode === 'part' && !isEdit,
    staleTime: 5 * 60_000,
  })

  // Parts — only after a category is selected
  const { data: partsData, isFetching: partsLoading } = useQuery({
    queryKey: ['parts-by-category', selectedCategory?.id, debouncedSearch],
    queryFn: () =>
      partsApi.list({
        category_id: selectedCategory!.id,
        search: debouncedSearch || undefined,
        page_size: 500,
      }),
    enabled: open && mode === 'part' && !isEdit && selectedCategory !== null,
    staleTime: 30_000,
  })

  const parts = partsData?.items ?? []

  const mutation = useMutation({
    mutationFn: (payload: Parameters<typeof invoiceApi.addLine>[2]) => {
      if (isEdit) {
        return invoiceApi.updateLine(invoicePublicId, editLine!.id, invoiceVersion, payload)
      }
      return invoiceApi.addLine(invoicePublicId, invoiceVersion, payload)
    },
    onSuccess: (updated) => {
      onSaved(updated)
      onClose()
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : "Impossible d'enregistrer la ligne.")
    },
  })

  function handleSubmit() {
    if (mode === 'part') {
      if (!selectedPart) return
      mutation.mutate({
        kind: 'part',
        part_id: selectedPart.int_id,
        description: selectedPart.name,
        quantity: parseFloat(quantity) || 1,
        unit_price_minor: selectedPart.selling_price_minor,
        discount_percent: parseFloat(partDiscount) || 0,
        vat_rate: 20,
      })
    } else {
      if (!description.trim()) return
      mutation.mutate({
        kind: 'service',
        description: description.trim(),
        quantity: 1,
        unit_price_minor: Math.round((parseFloat(unitPrice) || 0) * 100),
        discount_percent: parseFloat(prestDiscount) || 0,
        vat_rate: 20,
      })
    }
  }

  const canSubmit =
    !mutation.isPending &&
    (mode === 'part'
      ? !!selectedPart && selectedPart.stock_on_hand > 0 && parseFloat(quantity) > 0
      : description.trim().length > 0 && parseFloat(unitPrice) >= 0)

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        {isEdit ? 'Modifier la ligne' : 'Ajouter une ligne'}
      </DialogTitle>

      <DialogContent sx={{ pt: 1 }}>
        <Stack spacing={2.5} mt={1}>

          {/* Mode toggle — hidden in edit (kind is fixed) */}
          {isEdit ? (
            <Chip
              label={mode === 'part' ? 'Pièce du catalogue' : 'Prestation'}
              size="small"
              icon={mode === 'part' ? <InventoryRoundedIcon /> : <BuildRoundedIcon />}
              sx={{ alignSelf: 'flex-start' }}
            />
          ) : (
            <ToggleButtonGroup
              value={mode}
              exclusive
              onChange={(_, val) => {
                if (val) {
                  setMode(val)
                  setSelectedCategory(null)
                  setSelectedPart(null)
                  setPartSearch('')
                }
              }}
              size="small"
              fullWidth
            >
              <ToggleButton value="part" sx={{ gap: 0.75 }}>
                <InventoryRoundedIcon sx={{ fontSize: 16 }} />
                Pièce du catalogue
              </ToggleButton>
              <ToggleButton value="prestation" sx={{ gap: 0.75 }}>
                <BuildRoundedIcon sx={{ fontSize: 16 }} />
                Prestation
              </ToggleButton>
            </ToggleButtonGroup>
          )}

          {/* ── PART MODE ── */}
          {mode === 'part' && (
            <>
              {isEdit ? (
                /* Edit: part is locked — only qty/discount are editable */
                <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, p: 2 }}>
                  <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
                    <LockRoundedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                    <Typography variant="caption" color="text.disabled" fontWeight={600} letterSpacing={0.4}>
                      PIÈCE (NON MODIFIABLE)
                    </Typography>
                  </Stack>
                  <Typography variant="body2" fontWeight={600}>{editLine!.description}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatMinor(editLine!.unit_price_minor, 'EUR')} HT · TVA 20 %
                  </Typography>
                  <Typography variant="caption" color="text.disabled" display="block" mt={0.5}>
                    Pour changer la pièce, supprimez cette ligne et recréez-en une.
                  </Typography>
                </Box>
              ) : (
                <>
                  {/* Step 1 — Category */}
                  <FormControl size="small" fullWidth>
                    <InputLabel>Catégorie</InputLabel>
                    <Select
                      value={selectedCategory?.id ?? ''}
                      label="Catégorie"
                      onChange={(e) => {
                        const cat = categories.find((c) => c.id === Number(e.target.value)) ?? null
                        setSelectedCategory(cat)
                        setSelectedPart(null)
                        setPartSearch('')
                        setDebouncedSearch('')
                      }}
                    >
                      {categories.map((cat) => (
                        <MenuItem key={cat.id} value={cat.id}>
                          {cat.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  {/* Step 2 — Part search within category */}
                  <Autocomplete
                    disabled={!selectedCategory}
                    options={parts}
                    value={selectedPart}
                    getOptionLabel={(p) => p.name}
                    getOptionDisabled={(p) => p.stock_on_hand === 0}
                    isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                    inputValue={partSearch}
                    onInputChange={(_, val, reason) => {
                      if (reason !== 'reset') setPartSearch(val)
                      if (reason === 'clear') {
                        setSelectedPart(null)
                        setPartSearch('')
                      }
                    }}
                    onChange={(_, val) => {
                      setSelectedPart(val)
                      if (val) setPartSearch(val.name)
                    }}
                    loading={partsLoading}
                    noOptionsText={
                      selectedCategory
                        ? 'Aucune pièce trouvée dans cette catégorie'
                        : 'Sélectionnez une catégorie d\'abord'
                    }
                    renderOption={(props, part) => (
                      <Box
                        component="li"
                        {...props}
                        key={part.int_id}
                        sx={{ opacity: part.stock_on_hand === 0 ? 0.45 : 1 }}
                      >
                        <Stack sx={{ width: '100%' }} spacing={0.25}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center">
                            <Typography variant="body2" fontWeight={600}>{part.name}</Typography>
                            <Typography variant="body2" fontWeight={700} fontFamily="monospace">
                              {formatMinor(part.selling_price_minor, 'EUR')}
                            </Typography>
                          </Stack>
                          <Stack direction="row" justifyContent="space-between">
                            <Typography variant="caption" color="text.secondary">{part.sku_code}</Typography>
                            <Typography
                              variant="caption"
                              fontWeight={600}
                              color={part.stock_on_hand > 0 ? 'success.main' : 'error.main'}
                            >
                              {part.stock_on_hand > 0 ? `Stock : ${part.stock_on_hand}` : 'Rupture de stock'}
                            </Typography>
                          </Stack>
                        </Stack>
                      </Box>
                    )}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label={selectedCategory ? 'Rechercher une pièce' : 'Sélectionnez une catégorie d\'abord'}
                        size="small"
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {partsLoading && <CircularProgress size={14} sx={{ mr: 1 }} />}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                  />
                </>
              )}

              {/* Selected part info card */}
              {selectedPart && !isEdit && (
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2 }}>
                  <Stack direction="row" justifyContent="space-between" mb={0.5}>
                    <Typography variant="caption" color="text.secondary">Prix unitaire HT</Typography>
                    <Typography variant="body2" fontWeight={700} fontFamily="monospace">
                      {formatMinor(selectedPart.selling_price_minor, 'EUR')}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between" mb={0.5}>
                    <Typography variant="caption" color="text.secondary">Stock disponible</Typography>
                    <Typography variant="body2" fontWeight={600} color="success.main">
                      {selectedPart.stock_on_hand}
                      {selectedPart.unit_of_measure ? ` ${selectedPart.unit_of_measure}` : ''}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">TVA</Typography>
                    <Typography variant="body2" color="text.secondary">20 % (fixe)</Typography>
                  </Stack>
                </Box>
              )}

              {/* Qty + discount */}
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Quantité"
                  type="number"
                  size="small"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  inputProps={{ min: 1, step: 1 }}
                  sx={{ width: 110 }}
                />
                <TextField
                  label="Remise"
                  type="number"
                  size="small"
                  value={partDiscount}
                  onChange={(e) => setPartDiscount(e.target.value)}
                  inputProps={{ min: 0, max: 100, step: 0.5 }}
                  InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                  sx={{ width: 130 }}
                />
                <TextField
                  label="TVA"
                  size="small"
                  value="20 %"
                  disabled
                  sx={{ width: 90 }}
                />
              </Stack>
            </>
          )}

          {/* ── PRESTATION MODE ── */}
          {mode === 'prestation' && (
            <>
              <TextField
                label="Description de la prestation"
                size="small"
                fullWidth
                multiline
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ex : Vidange complète, diagnostic électronique…"
              />
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Prix unitaire HT"
                  type="number"
                  size="small"
                  value={unitPrice}
                  onChange={(e) => setUnitPrice(e.target.value)}
                  inputProps={{ min: 0, step: 0.01 }}
                  InputProps={{ endAdornment: <InputAdornment position="end">€</InputAdornment> }}
                  sx={{ flex: 1 }}
                />
                <TextField
                  label="Remise"
                  type="number"
                  size="small"
                  value={prestDiscount}
                  onChange={(e) => setPrestDiscount(e.target.value)}
                  inputProps={{ min: 0, max: 100, step: 0.5 }}
                  InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                  sx={{ width: 130 }}
                />
                <TextField
                  label="TVA"
                  size="small"
                  value="20 %"
                  disabled
                  sx={{ width: 90 }}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                Quantité : 1 (fixe pour les prestations)
              </Typography>
            </>
          )}

        </Stack>
      </DialogContent>

      <Divider />
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} disabled={mutation.isPending} color="inherit">
          Annuler
        </Button>
        <Button variant="contained" onClick={handleSubmit} disabled={!canSubmit}>
          {mutation.isPending
            ? isEdit ? 'Enregistrement…' : 'Ajout…'
            : isEdit ? 'Enregistrer' : 'Ajouter'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
