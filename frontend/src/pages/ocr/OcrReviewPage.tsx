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
import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'
import NavigateNextIcon from '@mui/icons-material/NavigateNext'
import ZoomInIcon from '@mui/icons-material/ZoomIn'
import ZoomOutIcon from '@mui/icons-material/ZoomOut'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ocrApi, OcrExtractionOut } from '../../lib/ocrApi'
import { supplierDeliveryNoteApi } from '../../lib/supplierDeliveryNoteApi'
import { BonLivraisonReceptionDialog } from '../../components/supplier-delivery-note/BonLivraisonReceptionDialog'

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
  numero_bl: 'N° de bon de livraison',
  date_bl: 'Date de livraison',
  reference_commande: 'Référence commande',
  email: 'Email fournisseur',
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
  supplier_delivery_note: 'Bon de livraison',
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
    // 'lignes' intentionally omitted — the dedicated grid below replaces the raw blob.
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
  supplier_delivery_note: [
    // Reference first — it is auto-filled from the linked PO (authoritative).
    'reference_commande',
    'numero_bl',
    'date_bl',
    'fournisseur',
    'email',
    'immatriculation',
    'total_ht',
    'tva',
    'total_ttc',
    // 'lignes' is intentionally omitted — the editable per-line grid below
    // replaces the raw blob (it still seeds from edited.lignes).
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
// Per-line "Bon de livraison" capture grid
// ---------------------------------------------------------------------------
interface BlLine {
  code: string
  designation: string
  quantite: string
  pu_brut: string
  pu_net: string
  montant: string
}

type BlLineField = keyof BlLine

const BL_LINE_COLUMNS: { field: BlLineField; label: string }[] = [
  { field: 'code', label: 'Code' },
  { field: 'designation', label: 'Désignation' },
  { field: 'quantite', label: 'Qté' },
  { field: 'pu_brut', label: 'PU Brut' },
  { field: 'pu_net', label: 'PU Net' },
  { field: 'montant', label: 'Montant' },
]

const emptyBlLine = (): BlLine => ({
  code: '',
  designation: '',
  quantite: '',
  pu_brut: '',
  pu_net: '',
  montant: '',
})

// Prefix used to arm a crop targeting a single grid cell: `bl-line:${i}:${field}`.
const BL_CROP_PREFIX = 'bl-line:'

// Build the initial grid by parsing the raw `lignes` JSON string the extractor
// produced. Each item ~ { description, quantity, unit_price, line_total }.
function seedBlLinesFromRaw(rawLignes: string | undefined): BlLine[] {
  if (!rawLignes) return [emptyBlLine()]
  try {
    const parsed = JSON.parse(rawLignes)
    if (!Array.isArray(parsed) || parsed.length === 0) return [emptyBlLine()]
    const toStr = (v: unknown) =>
      v === null || v === undefined ? '' : String(v)
    return parsed.map((item) => {
      const obj = (item ?? {}) as Record<string, unknown>
      return {
        code: '',
        designation: toStr(obj.description),
        quantite: toStr(obj.quantity),
        pu_brut: '',
        pu_net: toStr(obj.unit_price),
        montant: toStr(obj.line_total),
      }
    })
  } catch {
    return [emptyBlLine()]
  }
}

// ---------------------------------------------------------------------------
// Client-side reconstruction of the BL line table from the OCR cell boxes.
//
// PaddleOCR emits each *cell* of the table as a separate detection (columns are
// far apart), so the flat line extractor can't rebuild rows. But within a single
// column the rows are cleanly separated vertically, and money cells carry a
// decimal ("8,33") while quantities / the trailing "T" column don't. So we type
// each cell by content, cluster the money/text cells into columns by x, then
// align rows by each column's own top-to-bottom order. Deterministic, no LLM.
// ---------------------------------------------------------------------------
const RE_MONEY = /^\d{1,4}[.,]\d{2}$/
const RE_INT = /^\d{1,3}$/
const hasAlpha = (s: string) => /[a-zA-Z]/.test(s)

interface DocCell {
  text: string
  cx: number
  cy: number
}

// Group cells into columns: split wherever the x-gap to the next cell exceeds `gap`.
function clusterByX(items: DocCell[], gap = 80): DocCell[][] {
  const sorted = [...items].sort((a, b) => a.cx - b.cx)
  const clusters: DocCell[][] = []
  let cur: DocCell[] = []
  for (const c of sorted) {
    if (cur.length && c.cx - cur[cur.length - 1].cx > gap) {
      clusters.push(cur)
      cur = []
    }
    cur.push(c)
  }
  if (cur.length) clusters.push(cur)
  return clusters
}

const meanCx = (cl: DocCell[]) => cl.reduce((s, c) => s + c.cx, 0) / cl.length
const sortByCy = (cl: DocCell[]) => [...cl].sort((a, b) => a.cy - b.cy)

function reconstructBlRows(
  rawLines: [string, unknown][],
  boxes: Record<string, number[]>,
): BlLine[] {
  const cells: DocCell[] = []
  for (const [k, t] of rawLines) {
    const b = boxes[k]
    if (!b) continue
    cells.push({ text: String(t).trim(), cx: (b[0] + b[2]) / 2, cy: (b[1] + b[3]) / 2 })
  }
  if (!cells.length) return []

  // Vertical band of the line-item table: below the "Code" header, above the
  // totals block (Montant H.T. / Total H.T. / T.V.A. / T.T.C.).
  const codeHdr = cells.find((c) => c.text.toLowerCase() === 'code')
  const headerY = codeHdr ? codeHdr.cy : 0
  const totRe = /montant\s*h|total\s*h|t\.?t\.?c|t\.?v\.?a/i
  const totYs = cells
    .filter((c) => totRe.test(c.text) && c.cy > headerY + 100)
    .map((c) => c.cy)
  const totalsY = totYs.length ? Math.min(...totYs) : Infinity

  const band = cells.filter((c) => c.cy > headerY && c.cy < totalsY - 5)
  const money = band.filter((c) => RE_MONEY.test(c.text))
  const ints = band.filter((c) => RE_INT.test(c.text))
  const letters = band.filter((c) => hasAlpha(c.text))

  // Money columns: cluster by x, then assign from the RIGHT (Montant is always
  // rightmost, then PU Net, then PU Brut) so a plain BL missing a column degrades
  // gracefully. The trailing "T" column is a bare "0" (no decimal) → excluded.
  const moneyCols = clusterByX(money).sort((a, b) => meanCx(a) - meanCx(b)).map(sortByCy)
  const mont = moneyCols[moneyCols.length - 1] ?? []
  const net = moneyCols[moneyCols.length - 2] ?? []
  const brut = moneyCols[moneyCols.length - 3] ?? []

  // Text columns: leftmost = code, next = désignation.
  const letterCols = clusterByX(letters).sort((a, b) => meanCx(a) - meanCx(b))
  const codeCol = letterCols[0] ? sortByCy(letterCols[0]) : []
  const desCol = letterCols[1] ? sortByCy(letterCols[1]) : []

  // Quantity is a bare integer; OCR often misses it. Attach the nearest one (by y)
  // to a row's désignation, if close enough.
  const nearestQte = (cy: number): string => {
    let best = ''
    let bestDist = 20
    for (const c of ints) {
      const d = Math.abs(c.cy - cy)
      if (d < bestDist) {
        bestDist = d
        best = c.text
      }
    }
    return best
  }

  const at = (col: DocCell[], i: number) => (i < col.length ? col[i].text : '')
  const n = Math.max(codeCol.length, desCol.length, brut.length, net.length, mont.length)
  const rows: BlLine[] = []
  for (let i = 0; i < n; i++) {
    const des = desCol[i]
    rows.push({
      code: at(codeCol, i),
      designation: at(desCol, i),
      quantite: des ? nearestQte(des.cy) : '',
      pu_brut: at(brut, i),
      pu_net: at(net, i),
      montant: at(mont, i),
    })
  }
  return rows
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
  zoom = 1,
}: {
  url: string | null
  layout: Layout | null
  highlight: number[][]
  drawMode: boolean
  onRegionDrawn: (rect: DrawRect) => void
  zoom?: number
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [renderW, setRenderW] = useState(0)
  // Natural width of the displayed page image — drives the display→image scale so
  // cropping works on ANY page (PDFs render every page at the same DPI), not just
  // page 1 where the OCR layout is known.
  const [imgNaturalW, setImgNaturalW] = useState(0)
  const [imgError, setImgError] = useState(false)
  const startRef = useRef<{ x: number; y: number } | null>(null)
  const [draw, setDraw] = useState<DrawRect | null>(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    setImgNaturalW(0) // reset until the new page image reports its natural size
    // Guard against the ResizeObserver feedback loop: a synchronous setState in
    // the observer can re-trigger layout (e.g. when a scrollbar toggles), which
    // makes the preview jitter. Debounce via rAF and skip no-op width changes.
    let raf = 0
    let last = -1
    const update = () => {
      const w = el.clientWidth
      if (w !== last) {
        last = w
        setRenderW(w)
      }
    }
    update()
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(update)
    })
    ro.observe(el)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [url])

  if (!url) {
    // Reserve height so the placeholder doesn't collapse and toggle the page
    // scrollbar (which causes a visible layout "bounce") before the image loads.
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
        }}
      >
        <CircularProgress size={28} />
      </Box>
    )
  }

  const isPdf = /\.pdf(\?|$)/i.test(url)
  // Prefer the actual image natural width (works on every page); fall back to the
  // OCR layout width (page 1) so highlight overlays keep aligning.
  const baseW = imgNaturalW || (layout && layout.width ? layout.width : 0)
  // renderW is tracked by ResizeObserver on wrapRef — the zoomed inner div.
  // Since wrapRef has width = zoom × containerWidth, renderW already bakes in
  // the zoom factor.  No need to multiply by zoom again here; doing so would
  // square it and map crop boxes to the wrong image region.
  const scale = baseW ? renderW / baseW : 1

  const localPoint = (e: ReactMouseEvent) => {
    const r = wrapRef.current!.getBoundingClientRect()
    // getBoundingClientRect() returns viewport-relative coords, which already
    // account for all ancestor scroll offsets.  No manual scrollLeft correction.
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
        // Scrollable container so the zoomed image can be panned horizontally.
        <Box sx={{ overflowX: 'auto', overflowY: 'hidden' }}>
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
              width: `${zoom * 100}%`,
              minWidth: '100%',
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
              onLoad={(e) =>
                setImgNaturalW((e.currentTarget as HTMLImageElement).naturalWidth)
              }
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
  // Multi-page preview: total pages reported by the backend + current page,
  // with a per-page object-URL cache so navigation doesn't re-fetch.
  const [totalPages, setTotalPages] = useState(1)
  const [pageIndex, setPageIndex] = useState(0)
  const pageCacheRef = useRef<Map<number, string>>(new Map())
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
  const [blDialogOpen, setBlDialogOpen] = useState(false)
  // Zoom level for the document preview (1 = 100%, range 0.5–3).
  const [zoom, setZoom] = useState(1)
  const zoomIn = () => setZoom((z) => Math.min(3, Math.round((z + 0.25) * 4) / 4))
  const zoomOut = () => setZoom((z) => Math.max(0.5, Math.round((z - 0.25) * 4) / 4))
  // Per-line BL capture grid (supplier_delivery_note only). Pre-seeded once from
  // the raw `lignes` field; not overwritten after the user starts editing.
  const [blLines, setBlLines] = useState<BlLine[]>([])
  const blSeededRef = useRef(false)
  // The BL supplier is authoritative from the linked PO (resolved once).
  const supplierResolvedRef = useRef(false)

  useEffect(() => {
    if (!extractionId) return
    let cancelled = false
    let pollTimer: ReturnType<typeof setTimeout>
    const cache = pageCacheRef.current

    async function load() {
      try {
        const data = await ocrApi.get(extractionId!)
        if (cancelled) return
        setExtraction(data)

        // Fetch the document preview as soon as the extraction exists — the
        // rasterised page image is independent of OCR completion. Showing it
        // during processing keeps the left panel at full height and avoids the
        // scrollbar-toggle "bounce" of the short spinner placeholder. Fetched
        // once (page 1); further pages load on demand.
        if (!cache.has(0)) {
          try {
            const { blob, totalPages: tp } = await ocrApi.getPageImage(extractionId!, 0)
            if (!cancelled) {
              const url = URL.createObjectURL(blob)
              cache.set(0, url)
              setPreviewUrl(url)
              setTotalPages(tp)
              setPageIndex(0)
            }
          } catch {
            /* preview is best-effort */
          }
        }

        if (data.status === 'pending' || data.status === 'processing') {
          pollTimer = setTimeout(load, 2000)
          return
        }

        const semantic: Record<string, string> = {}
        for (const [k, v] of Object.entries(data.structured_fields ?? {})) {
          if (!isRawKey(k) && !isReservedKey(k)) semantic[k] = v as string
        }
        setEdited(semantic)
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
      cache.forEach((u) => URL.revokeObjectURL(u))
      cache.clear()
    }
  }, [extractionId])

  const updateBlLine = (i: number, field: BlLineField, value: string) =>
    setBlLines((prev) =>
      prev.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)),
    )

  const addBlLine = () => setBlLines((prev) => [...prev, emptyBlLine()])

  const removeBlLine = (i: number) =>
    setBlLines((prev) => prev.filter((_, idx) => idx !== i))

  // AI auto-match for one BL line: reconstruct the document's line table from the
  // OCR boxes and fill this row. If the row already has a code/désignation, use
  // the matching reconstructed row; otherwise fall back to the row at this index.
  // Detected values fill empty cells but never clobber what the user already typed.
  const suggestBlLine = (i: number) => {
    const rows = reconstructBlRows(rawLines, layout?.boxes ?? {})
    if (!rows.length) {
      setError('Aucune ligne détectée automatiquement sur le document.')
      return
    }
    setError(null)
    const cur = blLines[i]
    const anchor = norm(cur.designation || cur.code)
    let pick = -1
    if (anchor.length >= 3) {
      pick = rows.findIndex((r) => {
        const d = norm(r.designation)
        const c = norm(r.code)
        return (
          (d && (d.includes(anchor) || anchor.includes(d))) ||
          (c && (c.includes(anchor) || anchor.includes(c)))
        )
      })
    }
    if (pick < 0) pick = Math.min(i, rows.length - 1)
    const r = rows[pick]
    setBlLines((prev) =>
      prev.map((row, idx) =>
        idx === i
          ? {
              code: cur.code || r.code,
              designation: cur.designation || r.designation,
              quantite: cur.quantite || r.quantite,
              pu_brut: cur.pu_brut || r.pu_brut,
              pu_net: cur.pu_net || r.pu_net,
              montant: cur.montant || r.montant,
            }
          : row,
      ),
    )
  }

  // Navigate the multi-page preview (PDFs). Field localisation / cropping is
  // page-1 only, so any active field/crop/highlight is cleared when leaving it.
  const goToPage = async (idx: number) => {
    if (idx < 0 || idx >= totalPages || idx === pageIndex) return
    setActiveField(null)
    setCropTarget(null)
    setHighlight([])
    const cached = pageCacheRef.current.get(idx)
    if (cached) {
      setPreviewUrl(cached)
      setPageIndex(idx)
      return
    }
    try {
      const { blob } = await ocrApi.getPageImage(extractionId!, idx)
      const url = URL.createObjectURL(blob)
      pageCacheRef.current.set(idx, url)
      setPreviewUrl(url)
      setPageIndex(idx)
    } catch {
      setError('Impossible de charger cette page.')
    }
  }

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

  // Pre-seed the per-line capture grid once, after extraction is loaded.
  // For supplier_delivery_note: reconstruct rows from OCR cell boxes.
  // For supplier_invoice: seed from the `lignes` JSON blob (OCR line extractor).
  useEffect(() => {
    if (blSeededRef.current) return
    const cat = extraction?.document_category
    if (cat !== 'supplier_delivery_note' && cat !== 'supplier_invoice') return
    if (extraction?.status === 'pending' || extraction?.status === 'processing') return
    blSeededRef.current = true
    if (cat === 'supplier_delivery_note') {
      const reconstructed = reconstructBlRows(rawLines, layout?.boxes ?? {})
      setBlLines(
        reconstructed.length ? reconstructed : seedBlLinesFromRaw(edited.lignes),
      )
    } else {
      // supplier_invoice: document layouts vary too much for automatic reconstruction.
      // Start with one empty row; the user crops each cell manually.
      setBlLines([emptyBlLine()])
    }
  }, [extraction, edited.lignes, rawLines, layout])

  // Supplier and order reference are authoritative from the linked PO (not OCR).
  // Fill both the Fournisseur and Référence commande fields from the PO once the
  // extraction is ready. Works for both supplier_delivery_note and supplier_invoice
  // documents that are filed under a purchase order.
  useEffect(() => {
    if (supplierResolvedRef.current) return
    if (!extractionId) return
    const cat = extraction?.document_category
    if (cat !== 'supplier_delivery_note' && cat !== 'supplier_invoice') return
    if (extraction?.status === 'pending' || extraction?.status === 'processing') return
    supplierResolvedRef.current = true
    let cancelled = false
    supplierDeliveryNoteApi
      .poForExtraction(extractionId)
      .then((r) => {
        if (cancelled) return
        setEdited((prev) => {
          const next = { ...prev }
          if (r.supplier_name && !prev.fournisseur) next.fournisseur = r.supplier_name
          if (r.purchase_order_number) next.reference_commande = r.purchase_order_number
          return next
        })
      })
      .catch(() => {
        // Document not filed under a PO — supplier stays as OCR extracted or blank.
      })
    return () => {
      cancelled = true
    }
  }, [extraction, extractionId])

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
      const { text } = await ocrApi.ocrRegion(extractionId!, box, pageIndex)
      if (text) {
        if (target.startsWith(BL_CROP_PREFIX)) {
          // Convention: `bl-line:${i}:${field}` — write into the capture grid.
          const [, idxStr, field] = target.split(':')
          const i = Number(idxStr)
          if (!Number.isNaN(i) && field) {
            updateBlLine(i, field as BlLineField, text)
          }
        } else {
          setEdited((prev) => ({ ...prev, [target]: text }))
        }
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
      // For supplier invoices with OCR-captured part lines, serialize them into
      // confirmed_fields.lignes so the backend can persist them on the invoice.
      const fieldsToSend: Record<string, string> = { ...edited }
      if (isSupplierInvoice && blLines.length > 0 && blLines.some((l) => l.designation || l.montant)) {
        fieldsToSend.lignes = JSON.stringify(
          blLines.map((l) => ({
            description: l.designation || null,
            quantity: l.quantite || null,
            unit_price: l.pu_net || l.pu_brut || null,
            line_total: l.montant || null,
          }))
        )
      }
      const result = await ocrApi.ingest(extractionId, { confirmed_fields: fieldsToSend })
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
  // supplier_delivery_note uses a dedicated BL reception dialog.
  const isDeliveryNote = category === 'supplier_delivery_note'
  // supplier_invoice may also contain part lines (it can act as a BL itself).
  const isSupplierInvoice = category === 'supplier_invoice'
  // Show the per-line capture grid for both BL and supplier invoice.
  const showLineGrid = isDeliveryNote || isSupplierInvoice
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
        <Typography variant="h5">Extraction automatique</Typography>
        {category && <Chip size="small" label={categoryLabel} variant="outlined" />}
        {/* Progress lives in the fixed-height header row, so it appears and
            disappears without changing the content layout (no "bounce"). */}
        {isPending && (
          <Stack direction="row" alignItems="center" spacing={1}>
            <CircularProgress size={18} thickness={5} />
            <Typography variant="body2" color="text.secondary">
              Extraction en cours…
            </Typography>
          </Stack>
        )}
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

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={3} alignItems="flex-start">
        {/* ---- Left: document preview ---- */}
        <Paper sx={{ flex: 1, p: 2, position: { md: 'sticky' }, top: 16, width: '100%' }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1">Aperçu du document</Typography>
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <Tooltip title="Zoom arrière">
                <span>
                  <IconButton size="small" onClick={zoomOut} disabled={zoom <= 0.5}>
                    <ZoomOutIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              <Typography
                variant="caption"
                sx={{ minWidth: 36, textAlign: 'center', cursor: 'pointer' }}
                onClick={() => setZoom(1)}
              >
                {Math.round(zoom * 100)}%
              </Typography>
              <Tooltip title="Zoom avant">
                <span>
                  <IconButton size="small" onClick={zoomIn} disabled={zoom >= 3}>
                    <ZoomInIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              {highlight.length > 0 && (
                <Link
                  component="button"
                  variant="caption"
                  onClick={() => setHighlight([])}
                  sx={{ ml: 1 }}
                >
                  Effacer la sélection
                </Link>
              )}
            </Stack>
          </Stack>
          {cropTarget && (
            <Alert severity="info" sx={{ mb: 1 }} icon={<CropFreeIcon fontSize="small" />}>
              {cropLoading
                ? 'Reconnaissance de la zone…'
                : 'Dessinez la zone à reconnaître sur le document.'}
            </Alert>
          )}
          {totalPages > 1 && (
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="center"
              spacing={2}
              sx={{ my: 1 }}
            >
              <Button
                size="small"
                startIcon={<NavigateBeforeIcon />}
                disabled={pageIndex === 0}
                onClick={() => goToPage(pageIndex - 1)}
              >
                Précédent
              </Button>
              <Typography variant="body2">
                Page {pageIndex + 1} / {totalPages}
              </Typography>
              <Button
                size="small"
                endIcon={<NavigateNextIcon />}
                disabled={pageIndex >= totalPages - 1}
                onClick={() => goToPage(pageIndex + 1)}
              >
                Suivant
              </Button>
            </Stack>
          )}
          {totalPages > 1 && pageIndex > 0 && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', textAlign: 'center', mb: 1 }}
            >
              Localisation et recadrage des champs disponibles sur la page 1.
            </Typography>
          )}
          <DocumentPreview
            url={previewUrl}
            layout={pageIndex === 0 ? layout : null}
            highlight={pageIndex === 0 ? highlight : []}
            drawMode={
              // Crop-to-OCR works on every page; assign-from-layout is page-1 only.
              cropTarget !== null ||
              (pageIndex === 0 && canHighlight && activeField !== null)
            }
            onRegionDrawn={handleRegionDrawn}
            zoom={zoom}
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

          {showLineGrid && (
            <>
              <Divider sx={{ my: 2 }} />
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                sx={{ mb: 1 }}
              >
                <Typography variant="subtitle1">
                  {isDeliveryNote ? 'Lignes du bon de livraison' : 'Lignes de la facture fournisseur'}
                </Typography>
                <Button size="small" startIcon={<AddIcon />} onClick={addBlLine}>
                  Ajouter une ligne
                </Button>
              </Stack>
              {canHighlight && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 1 }}
                >
                  Pour chaque cellule, cliquez sur l'icône de recadrage puis dessinez
                  la zone correspondante sur le document.
                </Typography>
              )}
              <Box sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {BL_LINE_COLUMNS.map((col) => (
                        <TableCell key={col.field}>{col.label}</TableCell>
                      ))}
                      <TableCell sx={{ width: 88 }} />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {blLines.map((row, i) => (
                      <TableRow key={i}>
                        {BL_LINE_COLUMNS.map((col) => {
                          const cropKey = `${BL_CROP_PREFIX}${i}:${col.field}`
                          return (
                            <TableCell key={col.field} sx={{ p: 0.5 }}>
                              <Stack direction="row" spacing={0.25} alignItems="center">
                                <TextField
                                  size="small"
                                  fullWidth
                                  variant="standard"
                                  value={row[col.field]}
                                  onChange={(e) =>
                                    updateBlLine(i, col.field, e.target.value)
                                  }
                                  sx={{ minWidth: col.field === 'designation' ? 140 : 60 }}
                                />
                                {canHighlight && (
                                  <Tooltip title="Recadrer et reconnaître cette cellule">
                                    <IconButton
                                      size="small"
                                      color={cropTarget === cropKey ? 'primary' : 'default'}
                                      disabled={cropLoading}
                                      onClick={() => {
                                        setActiveField(null)
                                        setCropTarget((prev) =>
                                          prev === cropKey ? null : cropKey,
                                        )
                                      }}
                                    >
                                      <CropFreeIcon fontSize="inherit" />
                                    </IconButton>
                                  </Tooltip>
                                )}
                              </Stack>
                            </TableCell>
                          )
                        })}
                        <TableCell sx={{ p: 0.5 }}>
                          <Stack direction="row" spacing={0} alignItems="center">
                            {canHighlight && (
                              <Tooltip title="Remplir automatiquement cette ligne (IA) depuis le document">
                                <IconButton
                                  size="small"
                                  color="secondary"
                                  onClick={() => suggestBlLine(i)}
                                >
                                  <AutoAwesomeIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            <Tooltip title="Supprimer la ligne">
                              <span>
                                <IconButton
                                  size="small"
                                  color="error"
                                  disabled={blLines.length <= 1}
                                  onClick={() => removeBlLine(i)}
                                >
                                  <DeleteOutlineIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </>
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
                  startIcon={
                    saving ? (
                      <CircularProgress size={16} color="inherit" />
                    ) : (
                      <CheckCircleOutlineIcon />
                    )
                  }
                  onClick={isDeliveryNote ? () => setBlDialogOpen(true) : handleIngest}
                  disabled={saving}
                >
                  {isDeliveryNote ? 'Réceptionner' : ingestLabel}
                </Button>
              </Stack>
            )
          )}
        </Paper>
      </Stack>

      {isDeliveryNote && extractionId && (
        <BonLivraisonReceptionDialog
          open={blDialogOpen}
          onClose={() => setBlDialogOpen(false)}
          extractionId={extractionId}
          defaultBlNumber={edited.numero_bl}
          defaultBlDate={edited.date_bl}
          defaultEmail={edited.email}
          blLines={blLines}
          onConfirmed={() => {
            setBlDialogOpen(false)
            navigate('/purchase-orders')
          }}
        />
      )}
    </Box>
  )
}
