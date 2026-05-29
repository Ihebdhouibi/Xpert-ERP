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

export interface AnalyticsTrendPoint {
  date: string
  value: number
}

export interface MechanicProductivityEntry {
  name: string
  completed_count: number
  avg_duration_h: number | null
}

export interface AnalyticsResponse {
  from_date: string
  to_date: string
  revenue_trend: AnalyticsTrendPoint[]
  repair_count_trend: AnalyticsTrendPoint[]
  mechanic_productivity: MechanicProductivityEntry[]
}

export type ExportTable = 'top_customers' | 'top_suppliers' | 'low_stock_alerts'
export type ExportFormat = 'csv' | 'xlsx'

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

  getAnalytics: (from_date: string, to_date: string): Promise<AnalyticsResponse> =>
    apiClient
      .get('/kpi/analytics', { params: { from_date, to_date } })
      .then(r => r.data),

  getExportUrl: (table: ExportTable, format: ExportFormat): string => {
    const base = apiClient.defaults.baseURL ?? ''
    return `${base}/kpi/export?table=${table}&format=${format}`
  },

  downloadExport: async (table: ExportTable, format: ExportFormat): Promise<void> => {
    const token = localStorage.getItem('access_token')
    const response = await apiClient.get('/kpi/export', {
      params: { table, format },
      responseType: 'blob',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const filenames: Record<ExportTable, string> = {
      top_customers: 'top_clients',
      top_suppliers: 'top_fournisseurs',
      low_stock_alerts: 'alertes_stock',
    }
    const ext = format === 'xlsx' ? 'xlsx' : 'csv'
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `${filenames[table]}.${ext}`
    a.click()
    window.URL.revokeObjectURL(url)
  },
}
