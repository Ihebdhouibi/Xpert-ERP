import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { supplierApi, Supplier, SupplierCreatePayload } from '../../lib/supplierApi'

interface SupplierQuickCreateDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (supplier: Supplier) => void
  /** Pre-fill the name (e.g. the supplier read from an OCR'd document). */
  defaultName?: string
}

/**
 * Lightweight "create a supplier on the fly" dialog. Only the name is required
 * (so a provisional name is allowed), but the record is still validated and can
 * be completed later from the Fournisseurs page. Reused by the PO create dialog
 * and the BL supplier-HITL flow.
 */
export function SupplierQuickCreateDialog({
  open,
  onClose,
  onCreated,
  defaultName,
}: SupplierQuickCreateDialogProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [address, setAddress] = useState('')
  const [paymentTerms, setPaymentTerms] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setName(defaultName ?? '')
      setEmail('')
      setPhone('')
      setAddress('')
      setPaymentTerms('')
      setError('')
    }
  }, [open, defaultName])

  const handleSubmit = async () => {
    setError('')
    if (!name.trim()) {
      setError('Le nom du fournisseur est obligatoire.')
      return
    }
    setSaving(true)
    try {
      const payload: SupplierCreatePayload = {
        name: name.trim(),
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        address: address.trim() || undefined,
        payment_terms_days: paymentTerms ? Number(paymentTerms) : undefined,
      }
      const supplier = await supplierApi.create(payload)
      onCreated(supplier)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail
      setError(
        typeof detail === 'string' ? detail : 'Erreur lors de la création du fournisseur.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Nouveau fournisseur</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Nom du fournisseur *"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />
          <TextField label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <TextField
            label="Téléphone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <TextField
            label="Adresse"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            multiline
            rows={2}
          />
          <TextField
            label="Délai de paiement (jours)"
            type="number"
            value={paymentTerms}
            onChange={(e) => setPaymentTerms(e.target.value)}
            inputProps={{ min: 0 }}
          />
          <Typography variant="caption" color="text.secondary">
            Un nom provisoire est accepté ; la fiche pourra être complétée plus tard dans
            Fournisseurs.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={saving || !name.trim()}
        >
          {saving ? <CircularProgress size={20} /> : 'Créer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
