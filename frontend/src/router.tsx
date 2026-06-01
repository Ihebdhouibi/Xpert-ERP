import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/auth/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { CustomersListPage } from './pages/customers/CustomersListPage'
import { CustomerCreatePage } from './pages/customers/CustomerCreatePage'
import { CustomerEditPage } from './pages/customers/CustomerEditPage'
import { CustomerDetailPage } from './pages/customers/CustomerDetailPage'
import { RepairOrdersListPage } from './pages/repair-orders/RepairOrdersListPage'
import { RepairOrderCreatePage } from './pages/repair-orders/RepairOrderCreatePage'
import { RepairOrderDetailPage } from './pages/repair-orders/RepairOrderDetailPage'
import { WorkshopKanbanPage } from './pages/workshop/WorkshopKanbanPage'
import { TabletViewPage } from './pages/tablet/TabletViewPage'
import { PartsPage } from './pages/parts/PartsPage'
import { StockPage } from './pages/parts/StockPage'
import { SupplierPage } from './pages/suppliers/SupplierPage'
import { PurchaseOrderPage } from './pages/purchase-orders/PurchaseOrderPage'
import { SupplierInvoicePage } from './pages/supplier-invoices/SupplierInvoicePage'
import { TemplatesPage } from './pages/notifications/TemplatesPage'
import { InspectionTemplatesPage } from './pages/inspections/InspectionTemplatesPage'
import { InspectionsListPage } from './pages/inspections/InspectionsListPage'
import { InspectionExecutionPage } from './pages/inspections/InspectionExecutionPage'
import { InspectionApprovalPage } from './pages/inspections/InspectionApprovalPage'
import { KpiDashboardPage } from './pages/kpi/KpiDashboardPage'

export const router = createBrowserRouter([
  // Public routes — no shell
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/approve/:token',
    element: <InspectionApprovalPage />,
  },

  // Tablet view — full screen, no shell
  {
    path: '/tablet',
    element: (
      <ProtectedRoute>
        <TabletViewPage />
      </ProtectedRoute>
    ),
  },

  // Main app — protected layout with AppShell
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },

      // Customers
      { path: 'customers', element: <CustomersListPage /> },
      { path: 'customers/new', element: <CustomerCreatePage /> },
      { path: 'customers/:publicId', element: <CustomerDetailPage /> },
      { path: 'customers/:publicId/edit', element: <CustomerEditPage /> },

      // Repair orders
      { path: 'repair-orders', element: <RepairOrdersListPage /> },
      { path: 'repair-orders/new', element: <RepairOrderCreatePage /> },
      { path: 'repair-orders/:publicId', element: <RepairOrderDetailPage /> },

      // Workshop
      { path: 'workshop', element: <WorkshopKanbanPage /> },

      // Inspections
      { path: 'inspections', element: <InspectionsListPage /> },
      { path: 'inspections/:publicId', element: <InspectionExecutionPage /> },
      { path: 'inspection-templates', element: <InspectionTemplatesPage /> },

      // Parts & stock
      { path: 'parts', element: <PartsPage /> },
      { path: 'stock', element: <StockPage /> },

      // Purchasing
      { path: 'suppliers', element: <SupplierPage /> },
      { path: 'purchase-orders', element: <PurchaseOrderPage /> },
      { path: 'supplier-invoices', element: <SupplierInvoicePage /> },

      // Notifications
      { path: 'notification-templates', element: <TemplatesPage /> },

      // Analytics
      { path: 'kpi', element: <KpiDashboardPage /> },

      // Catch-all
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
