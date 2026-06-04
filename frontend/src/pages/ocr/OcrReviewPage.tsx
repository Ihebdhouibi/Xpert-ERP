/**
 * OCR Review Page — document preview + full raw OCR output.
 *
 * Route: /ocr/:extractionId
 *
 * Shows every recognised text line from PaddleOCR with its confidence score.
 * The operator can reject the extraction or validate it (confirm all lines as-is).
 */
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ocrApi, OcrExtractionOut } from '../../lib/ocrApi'

// ---------------------------------------------------------------------------
// Confidence bar — green ≥ 75 %, orange 50-74 %, red < 50 %
// ---------------------------------------------------------------------------
function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? 'success' : pct >= 50 ? 'warning' : 'error'
  return (
    <Tooltip title={`Confiance : ${pct}%`}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
        <LinearProgress
          variant="determinate"
          value={pct}
          color={color}
          sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
        />
        <Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>
          {pct}%
        </Typography>
      </Box>
    </Tooltip>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function OcrReviewPage() {
  const { extractionId } = useParams<{ extractionId: string }>()
  const navigate = useNavigate()

  const [extraction, setExtraction] = useState<OcrExtractionOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Poll while pending/processing
  useEffect(() => {
    if (!extractionId) return

    let cancelled = false
    let pollTimer: ReturnType<typeof setTimeout>

    async function load() {
      try {
        const data = await ocrApi.get(extractionId!)
        if (cancelled) return
        setExtraction(data)

        if (data.status === 'pending' || data.status === 'processing') {
          pollTimer = setTimeout(load, 2000)
        }
      } catch {
        if (!cancelled) setError("Impossible de charger l'extraction OCR.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
      clearTimeout(pollTimer)
    }
  }, [extractionId])

  async function handleConfirm() {
    if (!extractionId || !extraction) return
    setSaving(true)
    setError(null)
    try {
      // Confirm all lines as-is (structured_fields already holds the raw lines)
      const updated = await ocrApi.confirm(extractionId, {
        confirmed_fields: extraction.structured_fields ?? {},
      })
      setExtraction(updated)
      setSuccess('Extraction confirmée avec succès.')
    } catch {
      setError('Echec de la confirmation. Veuillez réessayer.')
    } finally {
      setSaving(false)
    }
  }

  async function handleReject() {
    if (!extractionId) return
    setSaving(true)
    setError(null)
    try {
      await ocrApi.reject(extractionId)
      setSuccess('Extraction rejetée.')
      navigate('/documents')
    } catch {
      setError('Échec du rejet. Veuillez réessayer.')
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!extraction) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Extraction OCR introuvable.</Alert>
      </Box>
    )
  }

  const isPending =
    extraction.status === 'pending' || extraction.status === 'processing'
  const isReviewed =
    extraction.status === 'completed' && extraction.reviewed_at !== null
  const lines = Object.entries(extraction.structured_fields ?? {})

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Verification OCR
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {isPending && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Traitement OCR en cours...
          <CircularProgress size={16} sx={{ ml: 1 }} />
        </Alert>
      )}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
        {/* ---- Left: document info ---- */}
        <Paper sx={{ flex: '0 0 280px', p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Document
          </Typography>
          <Typography variant="body2" color="text.secondary">
            ID document : {extraction.document_id}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Moteur : {extraction.engine_version}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Statut : {extraction.status}
          </Typography>
          {extraction.processed_at && (
            <Typography variant="body2" color="text.secondary">
              Traite le : {new Date(extraction.processed_at).toLocaleString('fr-FR')}
            </Typography>
          )}
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Texte brut
            </Typography>
            <Box
              component="pre"
              sx={{
                mt: 0.5,
                p: 1,
                bgcolor: 'grey.100',
                borderRadius: 1,
                fontSize: '0.7rem',
                maxHeight: 300,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {extraction.raw_text || '—'}
            </Box>
          </Box>
        </Paper>

        {/* ---- Right: OCR lines table ---- */}
        <Paper sx={{ flex: 1, p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Lignes extraites ({lines.length})
          </Typography>

          {lines.length === 0 && !isPending && (
            <Alert severity="warning">
              Aucune ligne extraite. Verifiez la qualite du document.
            </Alert>
          )}

          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 50 }}>#</TableCell>
                <TableCell>Texte reconnu</TableCell>
                <TableCell sx={{ width: 140 }}>Confiance</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map(([key, value]) => {
                const conf = extraction.confidence_scores?.[key] ?? 0
                const lineNum = key.replace('ligne_', '')
                return (
                  <TableRow key={key} hover>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {lineNum}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{value as string}</Typography>
                    </TableCell>
                    <TableCell>
                      <ConfidenceBar value={conf} />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>

          <Divider sx={{ my: 2 }} />

          {!isReviewed && !isPending && (
            <Stack direction="row" spacing={2} justifyContent="flex-end">
              <Button
                variant="outlined"
                color="error"
                startIcon={<CancelOutlinedIcon />}
                onClick={handleReject}
                disabled={saving}
              >
                Rejeter
              </Button>
              <Button
                variant="contained"
                color="primary"
                startIcon={<CheckCircleOutlineIcon />}
                onClick={handleConfirm}
                disabled={saving || lines.length === 0}
              >
                {saving ? <CircularProgress size={20} /> : 'Valider'}
              </Button>
            </Stack>
          )}

          {isReviewed && (
            <Alert severity="success">
              Extraction validee le{' '}
              {new Date(extraction.reviewed_at!).toLocaleString('fr-FR')}.
            </Alert>
          )}
        </Paper>
      </Stack>
    </Box>
  )
}
