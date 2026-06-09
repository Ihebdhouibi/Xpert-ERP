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
  IconButton,
  Link,
  Paper,
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
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import RefreshIcon from '@mui/icons-material/Refresh'
import CropFreeIcon from '@mui/icons-material/CropFree'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
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
interface DrawRect {
  x1: number
  y1: number
  x2: number
  y2: number
}

function DocumentPreview({
  url,
  layout,
  highlight,
  drawMode,
  onRegionDrawn,
}: {
  url: string | null
  layout: Layout | null
  highlight: number[][]
  drawMode: boolean
  onRegionDrawn: (rect: DrawRect) => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [renderW, setRenderW] = useState(0)
  const [imgError, setImgError] = useState(false)
  const startRef = useRef<{ x: number; y: number } | null>(null)
  const [draw, setDraw] = useState<DrawRect | null>(null)

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

  const localPoint = (e: ReactMouseEvent) => {
    const r = wrapRef.current!.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const handleDown = (e: ReactMouseEvent) => {
    if (!drawMode) return
    e.preventDefault()
    const p = localPoint(e)
    startRef.current = p
    setDraw({ x1: p.x, y1: p.y, x2: p.x, y2: p.y })
  }
  const handleMove = (e: ReactMouseEvent) => {
    if (!startRef.current) return
    const p = localPoint(e)
    const s = startRef.current
    setDraw({ x1: s.x, y1: s.y, x2: p.x, y2: p.y })
  }
  const handleUp = (e: ReactMouseEvent) => {
    const s = startRef.current
    if (!s) return
    startRef.current = null
    const p = localPoint(e)
    setDraw(null)
    const rect: DrawRect = {
      x1: Math.min(s.x, p.x) / scale,
      y1: Math.min(s.y, p.y) / scale,
      x2: Math.max(s.x, p.x) / scale,
      y2: Math.max(s.y, p.y) / scale,
    }
    if (rect.x2 - rect.x1 > 2 && rect.y2 - rect.y1 > 2) onRegionDrawn(rect)
  }

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
        <Box
          ref={wrapRef}
          onMouseDown={handleDown}
          onMouseMove={handleMove}
          onMouseUp={handleUp}
          onMouseLeave={() => {
            startRef.current = null
            setDraw(null)
          }}
          sx={{
            position: 'relative',
            width: '100%',
            lineHeight: 0,
            cursor: drawMode ? 'crosshair' : 'default',
            userSelect: 'none',
          }}
        >
          <Box
            component="img"
            src={url}
            alt="Aperçu du document"
            draggable={false}
            onError={() => setImgError(true)}
            sx={{ width: '100%', display: 'block', borderRadius: 1, bgcolor: 'grey.100' }}
          />
          {draw && (
            <Box
              sx={{
                position: 'absolute',
                left: `${Math.min(draw.x1, draw.x2)}px`,
                top: `${Math.min(draw.y1, draw.y2)}px`,
                width: `${Math.abs(draw.x2 - draw.x1)}px`,
                height: `${Math.abs(draw.y2 - draw.y1)}px`,
                border: '2px dashed',
                borderColor: 'primary.main',
                bgcolor: 'rgba(25,118,210,0.12)',
                pointerEvents: 'none',
              }}
            />
          )}
          {layout &&
            highlight.map((b, i) => {
              const pad = 3 // px of breathing room around the recognised box
              return (
                <Box
                  key={i}
                  sx={{
                    position: 'absolute',
                    // Explicit px strings — numeric sx values for top/left get the
                    // 8px spacing multiplier applied, which would throw boxes off-screen.
                    left: `${b[0] * scale - pad}px`,
                    top: `${b[1] * scale - pad}px`,
                    width: `${(b[2] - b[0]) * scale + pad * 2}px`,
                    height: `${(b[3] - b[1]) * scale + pad * 2}px`,
                    border: '2px solid',
                    borderColor: 'warning.main',
                    bgcolor: 'rgba(255,193,7,0.25)',
                    borderRadius: 0.5,
                    pointerEvents: 'none',
                  }}
                />
              )
            })}
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
  const [activeField, setActiveField] = useState<string | null>(null)
  // When set, the next region drawn on the preview is OCR'd and written here.
  const [cropTarget, setCropTarget] = useState<string | null>(null)
  const [cropLoading, setCropLoading] = useState(false)
  // Field currently being auto-matched (AI) from the recognised text.
  const [suggesting, setSuggesting] = useState<string | null>(null)
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

  // Boxes for a field value: match it (normalised) against recognised lines.
  // Only lines that CONTAIN the value count — never the reverse, otherwise short
  // values (a single digit) would match every line that includes that digit.
  const boxesForValue = (value: string): number[][] => {
    if (!layout || !value) return []
    const nv = norm(value)
    if (nv.length < 3) return []
    const out: number[][] = []
    for (const [k, text] of rawLines) {
      const nt = norm(text as string)
      if (nt.includes(nv) && layout.boxes?.[k]) {
        out.push(layout.boxes[k])
      }
    }
    return out
  }

  // Manual assignment: text of the recognised lines whose centre falls inside a
  // drawn region, joined in reading order, written into the active field.
  const assignRegion = (rect: DrawRect) => {
    if (!layout || !activeField) return
    const picked: { key: string; box: number[] }[] = []
    for (const [k, b] of Object.entries(layout.boxes ?? {})) {
      const cx = (b[0] + b[2]) / 2
      const cy = (b[1] + b[3]) / 2
      if (cx >= rect.x1 && cx <= rect.x2 && cy >= rect.y1 && cy <= rect.y2) {
        picked.push({ key: k, box: b })
      }
    }
    picked.sort((a, b) => a.box[1] - b.box[1] || a.box[0] - b.box[0])
    const text = picked
      .map((p) => (fields[p.key] as string) ?? '')
      .join(' ')
      .trim()
    if (text) {
      setEdited((prev) => ({ ...prev, [activeField]: text }))
      setHighlight(picked.map((p) => p.box))
    }
  }

  // Dispatch a drawn region: crop-and-OCR if a crop target is armed, else
  // assign from the already-recognised lines within the region.
  const handleRegionDrawn = async (rect: DrawRect) => {
    if (!cropTarget) {
      assignRegion(rect)
      return
    }
    const target = cropTarget
    const box = {
      x1: Math.round(rect.x1),
      y1: Math.round(rect.y1),
      x2: Math.round(rect.x2),
      y2: Math.round(rect.y2),
    }
    setCropLoading(true)
    setError(null)
    try {
      const { text } = await ocrApi.ocrRegion(extractionId!, box)
      if (text) {
        setEdited((prev) => ({ ...prev, [target]: text }))
        setHighlight([[box.x1, box.y1, box.x2, box.y2]])
      } else {
        setError('Aucun texte reconnu dans la zone sélectionnée.')
      }
    } catch {
      setError('Échec de la reconnaissance de la zone.')
    } finally {
      setCropLoading(false)
      setCropTarget(null)
    }
  }

  // AI auto-match: fill the field with the best candidate from the whole text.
  const handleSuggest = async (key: string) => {
    if (!extractionId) return
    setSuggesting(key)
    setError(null)
    try {
      const { value } = await ocrApi.suggestField(extractionId, key)
      if (value) {
        setEdited((prev) => ({ ...prev, [key]: value }))
        setActiveField(key)
        if (canHighlight) setHighlight(boxesForValue(value))
      } else {
        setError('Aucune correspondance trouvée pour ce champ.')
      }
    } catch {
      setError('Échec de la correspondance automatique.')
    } finally {
      setSuggesting(null)
    }
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
          // The draft invoice was created server-side — go to the list.
          navigate('/invoices')
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

  async function handleReanalyze() {
    if (!extraction?.document_public_id) return
    setSaving(true)
    try {
      const fresh = await ocrApi.enqueue(extraction.document_public_id)
      navigate(`/ocr/${fresh.id}`)
    } catch {
      setError("Impossible de relancer l'analyse.")
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
        <Box flexGrow={1} />
        <Button
          size="small"
          startIcon={<RefreshIcon />}
          onClick={handleReanalyze}
          disabled={saving || isPending}
        >
          Ré-analyser
        </Button>
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
          {cropTarget && (
            <Alert severity="info" sx={{ mb: 1 }} icon={<CropFreeIcon fontSize="small" />}>
              {cropLoading
                ? 'Reconnaissance de la zone…'
                : 'Dessinez la zone à reconnaître sur le document.'}
            </Alert>
          )}
          <DocumentPreview
            url={previewUrl}
            layout={layout}
            highlight={highlight}
            drawMode={canHighlight && (activeField !== null || cropTarget !== null)}
            onRegionDrawn={handleRegionDrawn}
          />
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
              Sélectionnez un champ pour le localiser. Champ non détecté : cliquez
              dedans puis dessinez une zone sur le document pour le remplir.
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
                    <Stack direction="row" spacing={0.5} alignItems="flex-start">
                      <TextField
                        sx={{ flex: 1 }}
                        size="small"
                        label={FIELD_LABELS[key] ?? key}
                        value={edited[key] ?? ''}
                        multiline={key === 'lignes'}
                        placeholder="Non détecté — saisir manuellement"
                        onFocus={() => {
                          setActiveField(key)
                          setCropTarget(null)
                          if (canHighlight) setHighlight(boxesForValue(edited[key] ?? ''))
                        }}
                        onChange={(e) =>
                          setEdited((prev) => ({ ...prev, [key]: e.target.value }))
                        }
                      />
                      {canHighlight && (
                        <Tooltip title="Recadrer et reconnaître une zone du document">
                          <IconButton
                            size="small"
                            color={cropTarget === key ? 'primary' : 'default'}
                            disabled={cropLoading}
                            onClick={() => {
                              setActiveField(key)
                              setCropTarget((prev) => (prev === key ? null : key))
                            }}
                            sx={{ mt: 0.5 }}
                          >
                            <CropFreeIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                      <Tooltip title="Correspondance automatique (IA) depuis le texte reconnu">
                        <span>
                          <IconButton
                            size="small"
                            color="secondary"
                            disabled={suggesting !== null}
                            onClick={() => handleSuggest(key)}
                            sx={{ mt: 0.5 }}
                          >
                            {suggesting === key ? (
                              <CircularProgress size={16} />
                            ) : (
                              <AutoAwesomeIcon fontSize="small" />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
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
