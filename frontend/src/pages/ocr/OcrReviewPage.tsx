/**
 * OCR Review Page — document preview + structured fields + ingestion.
 *
 * Route: /ocr/:extractionId
 *
 * Left  : preview of the source document (image or PDF). For images, selecting a
 *         field or a recognised line highlights its location on the image.
 * Right : full recognised text (collapsible) + the predefined schema fields for
 *         the category (editable), then a category-aware ingest action.
 */
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ocrApi, OcrExtractionOut } from '../../lib/ocrApi'
import { documentsApi } from '../../lib/documentsApi'

// ---------------------------------------------------------------------------
// Friendly labels for the structured field keys produced by the extractors
// ---------------------------------------------------------------------------
const FIELD_LABELS: Record<string, string> = {
  immatriculation: 'Immatriculation',
  vin: 'N° de châssis (VIN)',
  date_mise_en_circulation: 'Date de mise en circulation',
  marque: 'Marque',
  modele: 'Modèle',
  proprietaire: 'Propriétaire',
  numero_cin: 'N° CIN',
  nom: 'Nom',
  prenom: 'Prénom',
  date_naissance: 'Date de naissance',
  numero_facture: 'N° de facture',
  date_facture: 'Date de facture',
  date_echeance: "Date d'échéance",
  fournisseur: 'Fournisseur',
  client: 'Client',
  total_ht: 'Total HT',
  tva: 'TVA',
  total_ttc: 'Total TTC',
  lignes: 'Lignes détectées (brut)',
}

const INGEST_LABEL: Record<string, string> = {
  registration_card: 'Mettre à jour le véhicule',
  id_doc: 'Mettre à jour le client',
  supplier_invoice: 'Valider',
  invoice: 'Valider',
}

const CATEGORY_LABELS: Record<string, string> = {
  registration_card: 'Carte grise',
  id_doc: "Pièce d'identité",
  insurance: 'Assurance',
  accident_photo: 'Photo accident',
  repair_attachment: 'Annexe OR',
  invoice: 'Facture',
  supplier_invoice: 'Facture fournisseur',
  generic: 'Générique',
}

const CATEGORY_SCHEMA: Record<string, string[]> = {
  registration_card: [
    'immatriculation',
    'vin',
    'date_mise_en_circulation',
    'marque',
    'modele',
    'proprietaire',
  ],
  id_doc: ['numero_cin', 'nom', 'prenom', 'date_naissance'],
  supplier_invoice: [
    'numero_facture',
    'date_facture',
    'date_echeance',
    'fournisseur',
    'total_ht',
    'tva',
    'total_ttc',
    'lignes',
  ],
  invoice: [
    'numero_facture',
    'date_facture',
    'date_echeance',
    'client',
    'total_ht',
    'tva',
    'total_ttc',
    'lignes',
  ],
}

const LAYOUT_KEY = '__layout__'
const isRawKey = (key: string) => /^ligne_\d+$/.test(key)
const isReservedKey = (key: string) => key.startsWith('__')
const confPct = (v: number) => `${Math.round(v * 100)}%`
// Normalise text for fuzzy matching of a field value to a recognised line
const norm = (s: string) => (s || '').toLowerCase().replace(/[\s.,€%]/g, '')

interface Layout {
  width: number
  height: number
  boxes: Record<string, number[]>
}

// ---------------------------------------------------------------------------
// Document preview (image with highlight overlay, or PDF iframe)
// ---------------------------------------------------------------------------
function DocumentPreview({
  url,
  layout,
  highlight,
}: {
  url: string | null
  layout: Layout | null
  highlight: number[][]
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [renderW, setRenderW] = useState(0)
  const [imgError, setImgError] = useState(false)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const update = () => setRenderW(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [url])

  if (!url) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress size={28} />
      </Box>
    )
  }

  const isPdf = /\.pdf(\?|$)/i.test(url)
  const scale = layout && layout.width ? renderW / layout.width : 1

  return (
    <Box>
      {isPdf ? (
        <Box
          component="iframe"
          src={url}
          title="Aperçu du document"
          sx={{ width: '100%', height: '78vh', border: 0, borderRadius: 1 }}
        />
      ) : imgError ? (
        <Alert severity="warning">
          Aperçu indisponible. Utilisez le lien ci-dessous pour ouvrir le document.
        </Alert>
      ) : (
        <Box ref={wrapRef} sx={{ position: 'relative', width: '100%', lineHeight: 0 }}>
          <Box
            component="img"
            src={url}
            alt="Aperçu du document"
            onError={() => setImgError(true)}
            sx={{ width: '100%', display: 'block', borderRadius: 1, bgcolor: 'grey.100' }}
          />
          {layout &&
            highlight.map((b, i) => (
              <Box
                key={i}
                sx={{
                  position: 'absolute',
                  // Explicit px strings — numeric sx values for top/left get the
                  // 8px spacing multiplier applied, which would throw boxes off-screen.
                  left: `${b[0] * scale}px`,
                  top: `${b[1] * scale}px`,
                  width: `${(b[2] - b[0]) * scale}px`,
                  height: `${(b[3] - b[1]) * scale}px`,
                  border: '2px solid',
                  borderColor: 'warning.main',
                  bgcolor: 'rgba(255,193,7,0.25)',
                  borderRadius: 0.5,
                  pointerEvents: 'none',
                }}
              />
            ))}
        </Box>
      )}
      <Box sx={{ mt: 1, textAlign: 'right' }}>
        <Link href={url} target="_blank" rel="noopener" variant="caption">
          Ouvrir dans un nouvel onglet
        </Link>
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function OcrReviewPage() {
  const { extractionId } = useParams<{ extractionId: string }>()
  const navigate = useNavigate()

  const [extraction, setExtraction] = useState<OcrExtractionOut | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [edited, setEdited] = useState<Record<string, string>>({})
  const [showRaw, setShowRaw] = useState(false)
  const [highlight, setHighlight] = useState<number[][]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

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
          return
        }

        const semantic: Record<string, string> = {}
        for (const [k, v] of Object.entries(data.structured_fields ?? {})) {
          if (!isRawKey(k) && !isReservedKey(k)) semantic[k] = v as string
        }
        setEdited(semantic)

        if (data.document_public_id) {
          try {
            const res = await documentsApi.getSignedUrl(data.document_public_id)
            if (!cancelled) setPreviewUrl(res.url)
          } catch {
            /* preview is best-effort */
          }
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

  const fields = useMemo(
    () => extraction?.structured_fields ?? {},
    [extraction],
  )
  const layout = (fields[LAYOUT_KEY] as unknown as Layout | undefined) ?? null

  const rawLines = useMemo(
    () => Object.entries(fields).filter(([k]) => isRawKey(k)),
    [fields],
  )
  const semanticKeys = useMemo(
    () => Object.keys(fields).filter((k) => !isRawKey(k) && !isReservedKey(k)),
    [fields],
  )

  // Boxes for a recognised line key
  const boxFor = (lineKey: string): number[][] => {
    const b = layout?.boxes?.[lineKey]
    return b ? [b] : []
  }

  // Boxes for a field value: match it (normalised) against recognised lines
  const boxesForValue = (value: string): number[][] => {
    if (!layout || !value || value.length < 2) return []
    const nv = norm(value)
    if (!nv) return []
    const out: number[][] = []
    for (const [k, text] of rawLines) {
      const nt = norm(text as string)
      if (nt && (nt.includes(nv) || nv.includes(nt)) && layout.boxes?.[k]) {
        out.push(layout.boxes[k])
      }
    }
    return out
  }

  async function handleIngest() {
    if (!extractionId || !extraction) return
    setSaving(true)
    setError(null)
    try {
      const result = await ocrApi.ingest(extractionId, { confirmed_fields: edited })
      switch (result.target) {
        case 'supplier_invoice':
          // The supplier invoice draft was created server-side — go to the list.
          navigate('/supplier-invoices')
          return
        case 'invoice':
          navigate('/invoices/new', { state: { ocrPrefill: result.prefill } })
          return
        case 'vehicle':
          setSuccess('Champs validés — véhicule mis à jour.')
          break
        case 'customer':
          setSuccess('Champs validés — client mis à jour.')
          break
        default:
          setSuccess('Extraction validée.')
      }
      const refreshed = await ocrApi.get(extractionId)
      setExtraction(refreshed)
    } catch {
      setError("Échec de l'enregistrement. Veuillez réessayer.")
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
  const isReviewed = extraction.reviewed_at !== null
  const category = extraction.document_category ?? ''
  const ingestLabel = INGEST_LABEL[category] ?? 'Valider'
  const categoryLabel = CATEGORY_LABELS[category] ?? category
  const schemaFields = CATEGORY_SCHEMA[category] ?? []
  const fieldsToShow = [
    ...schemaFields,
    ...semanticKeys.filter((k) => !schemaFields.includes(k)),
  ]
  const canHighlight = Boolean(layout && layout.boxes)

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" alignItems="center" spacing={2} mb={2}>
        <Typography variant="h5">Vérification OCR</Typography>
        {category && <Chip size="small" label={categoryLabel} variant="outlined" />}
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
      {isPending && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Traitement OCR en cours…
          <CircularProgress size={16} sx={{ ml: 1 }} />
        </Alert>
      )}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={3} alignItems="flex-start">
        {/* ---- Left: document preview ---- */}
        <Paper sx={{ flex: 1, p: 2, position: { md: 'sticky' }, top: 16, width: '100%' }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1">Aperçu du document</Typography>
            {highlight.length > 0 && (
              <Link
                component="button"
                variant="caption"
                onClick={() => setHighlight([])}
              >
                Effacer la sélection
              </Link>
            )}
          </Stack>
          <DocumentPreview url={previewUrl} layout={layout} highlight={highlight} />
        </Paper>

        {/* ---- Right: full text + schema matches ---- */}
        <Paper sx={{ flex: 1, p: 2, width: '100%' }}>
          {/* 1. Full recognised text — collapsible, scrollable, plain confidence */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1">
              Texte reconnu ({rawLines.length} lignes)
            </Typography>
            <Button
              size="small"
              onClick={() => setShowRaw((s) => !s)}
              endIcon={showRaw ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            >
              {showRaw ? 'Masquer' : 'Afficher'}
            </Button>
          </Stack>

          {rawLines.length === 0 && !isPending && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              Aucun texte reconnu. Vérifiez la qualité / la lisibilité du document.
            </Alert>
          )}

          <Collapse in={showRaw}>
            <Box sx={{ maxHeight: 320, overflow: 'auto', mt: 1 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 36 }}>#</TableCell>
                    <TableCell>Texte reconnu</TableCell>
                    <TableCell sx={{ width: 70 }} align="right">
                      Conf.
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rawLines.map(([key, value]) => (
                    <TableRow
                      key={key}
                      hover
                      onClick={() => canHighlight && setHighlight(boxFor(key))}
                      sx={{ cursor: canHighlight ? 'pointer' : 'default' }}
                    >
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {key.replace('ligne_', '')}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{value as string}</Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="caption" color="text.secondary">
                          {confPct(extraction.confidence_scores?.[key] ?? 0)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </Collapse>

          <Divider sx={{ my: 2 }} />

          {/* 2. Schema fields for the category */}
          <Typography variant="subtitle1" gutterBottom>
            Champs détectés{categoryLabel ? ` — ${categoryLabel}` : ''}
          </Typography>
          {canHighlight && (
            <Typography variant="caption" color="text.secondary">
              Sélectionnez un champ pour le localiser sur le document.
            </Typography>
          )}

          {fieldsToShow.length === 0 ? (
            <Alert severity="info" sx={{ mb: 2, mt: 1 }}>
              Aucun schéma de champs pour cette catégorie. Utilisez le texte reconnu
              ci-dessus.
            </Alert>
          ) : (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              {fieldsToShow.map((key) => {
                const detected = fields[key] !== undefined
                const conf = extraction.confidence_scores?.[key]
                return (
                  <Box key={key}>
                    <TextField
                      fullWidth
                      size="small"
                      label={FIELD_LABELS[key] ?? key}
                      value={edited[key] ?? ''}
                      multiline={key === 'lignes'}
                      placeholder="Non détecté — saisir manuellement"
                      onFocus={() =>
                        canHighlight && setHighlight(boxesForValue(edited[key] ?? ''))
                      }
                      onChange={(e) =>
                        setEdited((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ ml: 0.5 }}
                    >
                      {detected && conf != null
                        ? `Confiance : ${confPct(conf)}`
                        : 'Non détecté'}
                    </Typography>
                  </Box>
                )
              })}
            </Stack>
          )}

          <Divider sx={{ my: 2 }} />

          {isReviewed ? (
            <Alert severity="success">
              Extraction validée le{' '}
              {new Date(extraction.reviewed_at!).toLocaleString('fr-FR')}.
            </Alert>
          ) : (
            !isPending && (
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
                  onClick={handleIngest}
                  disabled={saving}
                >
                  {saving ? <CircularProgress size={20} /> : ingestLabel}
                </Button>
              </Stack>
            )
          )}
        </Paper>
      </Stack>
    </Box>
  )
}
