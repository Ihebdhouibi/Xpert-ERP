/**
 * Small, deterministic supplier-name matching (no LLM, no external deps).
 * Used to reuse an existing supplier instead of creating a duplicate, and to
 * auto-resolve the supplier read from an OCR'd document against the DB.
 */
import { Supplier } from './supplierApi'

/** Normalise a name: strip accents (code-point filter), case/space/punct-insensitive. */
export function normalizeName(s: string): string {
  return Array.from((s ?? '').normalize('NFD'))
    .filter((c) => {
      const n = c.charCodeAt(0)
      return n < 0x300 || n > 0x36f // drop combining accents
    })
    .join('')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

/** Sorensen-Dice bigram similarity in [0,1]. */
export function diceSimilarity(a: string, b: string): number {
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

/**
 * Best supplier whose name matches any candidate text (e.g. the OCR-extracted
 * supplier plus the recognised lines), or null if nothing clears `threshold`.
 */
export function findBestSupplierMatch(
  candidates: string[],
  suppliers: Supplier[],
  threshold = 0.85,
): { supplier: Supplier; score: number } | null {
  let best: { supplier: Supplier; score: number } | null = null
  for (const raw of candidates) {
    const norm = normalizeName(raw)
    if (norm.length < 3) continue
    for (const s of suppliers) {
      const sn = normalizeName(s.name)
      if (!sn) continue
      const score = sn === norm ? 1 : diceSimilarity(sn, norm)
      if (!best || score > best.score) best = { supplier: s, score }
    }
  }
  return best && best.score >= threshold ? best : null
}
