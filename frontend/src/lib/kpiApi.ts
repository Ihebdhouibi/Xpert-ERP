import { apiClient } from './apiClient'

export interface KpiValue {
  value: number | null
  meta?: unknown
}

export interface KpiLiveResponse {
  garage_id: number
  computed_at: string
  refresh_interval_seconds: number
  kpis: Record<string, KpiValue>
}

export interface KpiSnapshotPoint {
  id: number
  garage_id: number
  snapshot_date: string
  kpi_code: string
  value: number | null
  meta: unknown
  computed_at: string
}

export interface KpiTrendResponse {
  kpi_code: string
  from_date: string
  to_date: string
  points: KpiSnapshotPoint[]
}

export interface TopCustomerEntry {
  rank: number
  customer_id: string
  name: string
  revenue_minor: number
}

export interface TopSupplierEntry {
  rank: number
  supplier_id: string
  name: string
  spend_minor: number
}

export const kpiApi = {
  getLive: (): Promise<KpiLiveResponse> =>
    apiClient.get('/kpi/live').then(r => r.data),

  getTrend: (
    kpi_code: string,
    from_date: string,
    to_date: string,
  ): Promise<KpiTrendResponse> =>
    apiClient
      .get('/kpi/snapshots', { params: { kpi_code, from_date, to_date } })
      .then(r => r.data),
}
