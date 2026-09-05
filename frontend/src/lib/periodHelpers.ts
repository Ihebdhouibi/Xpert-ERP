// ─── Date period helpers ───────────────────────────────────────────────────
// Shared between the KPI dashboard (/kpi) and the landing Dashboard's
// period-scoped revenue card, so "Cette semaine" / "Ce mois" / etc. mean
// exactly the same date range everywhere in the app.

export type Period = 'today' | 'week' | 'month' | 'quarter' | 'year' | 'custom'

// Format a Date as YYYY-MM-DD using its LOCAL calendar date — never
// toISOString().slice(0, 10), which converts to UTC first and can land on
// the wrong day for part of the day in any timezone ahead/behind UTC (e.g.
// ~1–2am in France). Every date derived from "now" in this file must agree
// on the same calendar day, or "today" and "start of month" can disagree
// right around UTC midnight — in the worst case producing from > to, which
// the backend rejects.
export function toLocalDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayStr(): string {
  return toLocalDateStr(new Date())
}

export function periodDates(
  period: Period,
  custom: { from: string; to: string },
): { from: string; to: string } {
  const now = new Date()
  const to = todayStr()
  if (period === 'today') return { from: to, to }
  if (period === 'week') {
    const d = new Date(now)
    const day = d.getDay() === 0 ? 6 : d.getDay() - 1 // Monday = 0
    d.setDate(d.getDate() - day)
    return { from: toLocalDateStr(d), to }
  }
  if (period === 'month') {
    return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`, to }
  }
  if (period === 'quarter') {
    const q = Math.floor(now.getMonth() / 3)
    const fromMonth = String(q * 3 + 1).padStart(2, '0')
    return { from: `${now.getFullYear()}-${fromMonth}-01`, to }
  }
  if (period === 'year') {
    return { from: `${now.getFullYear()}-01-01`, to }
  }
  return custom
}

export const PERIOD_LABELS: Record<Period, string> = {
  today: "Aujourd'hui",
  week: 'Cette semaine',
  month: 'Ce mois',
  quarter: 'Ce trimestre',
  year: 'Cette année',
  custom: 'Personnalisé',
}

// ─── "As of" date helpers ───────────────────────────────────────────────────
// For stock/balance metrics (e.g. encours clients) rather than flow metrics
// (e.g. chiffre d'affaires) — a balance is a snapshot at one point in time,
// not a sum over a range, so this is a single date, not a {from, to} pair.

export type AsOfPreset = 'today' | 'last_month_end' | 'year_start' | 'custom'

export function asOfDate(preset: AsOfPreset, customDate: string): string {
  const now = new Date()
  if (preset === 'today') return todayStr()
  if (preset === 'last_month_end') {
    // Day 0 of the current month == the last day of the previous month.
    const d = new Date(now.getFullYear(), now.getMonth(), 0)
    return toLocalDateStr(d)
  }
  if (preset === 'year_start') {
    return `${now.getFullYear()}-01-01`
  }
  return customDate
}

export const AS_OF_LABELS: Record<AsOfPreset, string> = {
  today: "Aujourd'hui",
  last_month_end: 'Fin du mois dernier',
  year_start: "Début d'année",
  custom: 'Personnalisé',
}
