import { apiClient } from './apiClient'

export type StockMovementType = 'in' | 'out' | 'adjustment' | 'reservation' | 'release'
export type LowStockAlertStatus = 'open' | 'acknowledged' | 'resolved'

export interface StockLevel {
  part_id: number
  part_public_id: string | null
  part_name: string | null
  sku_code: string | null
  garage_id: number
  on_hand: number
  reserved: number
  available: number
  avg_cost_minor: number
  updated_at: string
}

export interface StockMovement {
  id: number
  part_id: number
  garage_id: number
  type: StockMovementType
  quantity: number
  unit_cost_minor: number | null
  ref_type: string | null
  ref_id: string | null
  reason: string | null
  created_by_user_id: number | null
  created_at: string
}

export interface LowStockAlert {
  id: number
  part_id: number
  garage_id: number
  on_hand: number
  threshold: number
  suggested_supplier_id: number | null
  suggested_reorder_quantity: number | null
  status: LowStockAlertStatus
  created_at: string
}

export interface ValuationItem {
  part_id: number
  on_hand: number
  avg_cost_minor: number
  total_value_minor: number
}

export interface ValuationReport {
  items: ValuationItem[]
  total_inventory_value_minor: number
}

export const MOVEMENT_LABELS: Record<StockMovementType, string> = {
  in: 'Entrée',
  out: 'Sortie',
  adjustment: 'Ajustement',
  reservation: 'Réservation',
  release: 'Libération',
}

export const ALERT_STATUS_LABELS: Record<LowStockAlertStatus, string> = {
  open: 'Ouvert',
  acknowledged: 'Pris en compte',
  resolved: 'Résolu',
}

export const stockApi = {
  getLevel(partPublicId: string): Promise<StockLevel> {
    return apiClient.get(`/parts/${partPublicId}/stock`).then((r) => r.data)
  },

  listMovements(partPublicId: string, params?: { limit?: number; offset?: number }): Promise<StockMovement[]> {
    return apiClient.get(`/parts/${partPublicId}/stock/movements`, { params }).then((r) => r.data)
  },

  createMovement(
    partPublicId: string,
    body: {
      type: StockMovementType
      quantity: number
      unit_cost_minor?: number
      ref_type?: string
      ref_id?: string
      reason?: string
    }
  ): Promise<StockMovement> {
    return apiClient.post(`/parts/${partPublicId}/stock/movements`, body).then((r) => r.data)
  },

  reserve(partPublicId: string, body: { quantity: number; ref_type: string; ref_id: string; reason?: string }): Promise<StockMovement> {
    return apiClient.post(`/parts/${partPublicId}/stock/reserve`, body).then((r) => r.data)
  },

  release(partPublicId: string, body: { quantity: number; ref_type: string; ref_id: string; reason?: string }): Promise<StockMovement> {
    return apiClient.post(`/parts/${partPublicId}/stock/release`, body).then((r) => r.data)
  },

  listAllLevels(): Promise<StockLevel[]> {
    return apiClient.get('/stock/levels').then((r) => r.data)
  },

  listAllMovements(params?: { ref_type?: string; ref_id?: string; limit?: number; offset?: number }): Promise<StockMovement[]> {
    return apiClient.get('/stock/movements', { params }).then((r) => r.data)
  },

  listAlerts(params?: { status?: LowStockAlertStatus; include_resolved?: boolean }): Promise<LowStockAlert[]> {
    return apiClient.get('/stock/alerts', { params }).then((r) => r.data)
  },

  acknowledgeAlert(alertId: number): Promise<LowStockAlert> {
    return apiClient.post(`/stock/alerts/${alertId}/acknowledge`).then((r) => r.data)
  },

  resolveAlert(alertId: number): Promise<LowStockAlert> {
    return apiClient.post(`/stock/alerts/${alertId}/resolve`).then((r) => r.data)
  },

  getValuation(): Promise<ValuationReport> {
    return apiClient.get('/stock/valuation').then((r) => r.data)
  },
}
