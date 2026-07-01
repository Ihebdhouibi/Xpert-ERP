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

// Normalise a supplier name for comparison: case/accents/spacing/punct-insensitive.
function normalizeName(s: string): string {
  return Array.from(s.normalize('NFD'))
    .filter((c) => {
      const n = c.charCodeAt(0)
      return n < 0x300 || n > 0x36f // drop combining accents
    })
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

// Sorensen-Dice bigram similarity in [0,1] — small and deterministic.
function diceSimilarity(a: string, b: string): number {
  if (a === b) return 1
  if (a.length < 2 || b.length < 2) return 0
  const bigrams = (s: string) => {
    const m = new Map<string, number>()
    for (let i = 0; i < s.length - 1; i++) {
      const g = s.slice(i, i + 2)
      m.set(g, (m.get(g) ?? 0) + 1)
    }
    return m
  }
  const ma = bigrams(a)
  const mb = bigrams(b)
  let total = 0
  ma.forEach((v) => (total += v))
  mb.forEach((v) => (total += v))
  let overlap = 0
  ma.forEach((v, g) => {
    const w = mb.get(g)
    if (w) overlap += Math.min(v, w)
  })
  return total ? (2 * overlap) / total : 0
}

// Return an existing supplier whose name closely matches `name` (to avoid
// creating a duplicate), or null.
async function findSimilarSupplier(name: string): Promise<Supplier | null> {
  const norm = normalizeName(name)
  if (!norm) return null
  try {
    const res = await supplierApi.list({ search: name, page_size: 25 })
    let best: { s: Supplier; score: number } | null = null
    for (const s of res.items) {
      const score =
        normalizeName(s.name) === norm ? 1 : diceSimilarity(normalizeName(s.name), norm)
      if (!best || score > best.score) best = { s, score }
    }
    return best && best.score >= 0.9 ? best.s : null
  } catch {
    return null
  }
}

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
      // Avoid duplicates: if a closely-matching supplier already exists, reuse
      // it instead of creating another (auto-assign).
      const existing = await findSimilarSupplier(name.trim())
      if (existing) {
        onCreated(existing)
        return
      }
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
