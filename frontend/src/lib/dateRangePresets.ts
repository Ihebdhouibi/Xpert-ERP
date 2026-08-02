import { startOfDay, startOfWeek, startOfMonth } from 'date-fns'

export type DateRangePeriod = 'day' | 'week' | 'month'

export const DATE_RANGE_PERIOD_LABELS: Record<DateRangePeriod, string> = {
  day: "Aujourd'hui",
  week: 'Cette semaine',
  month: 'Ce mois',
}

/** date_from/date_to (ISO strings) for a quick period filter, ending now. */
export function getPeriodRange(period: DateRangePeriod): { date_from: string; date_to: string } {
  const now = new Date()
  const starts: Record<DateRangePeriod, Date> = {
    day: startOfDay(now),
    week: startOfWeek(now, { weekStartsOn: 1 }),
    month: startOfMonth(now),
  }
  return { date_from: starts[period].toISOString(), date_to: now.toISOString() }
}
