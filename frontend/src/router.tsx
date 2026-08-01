import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/auth/LoginPage'
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage'
import { DashboardPage } from './pages/DashboardPage'
import { CustomersListPage } from './pages/customers/CustomersListPage'
import { CustomerCreatePage } from './pages/customers/CustomerCreatePage'
import { CustomerEditPage } from './pages/customers/CustomerEditPage'
import { CustomerDetailPage } from './pages/customers/CustomerDetailPage'
import { RepairOrdersListPage } from './pages/repair-orders/RepairOrdersListPage'
import { RepairOrderCreatePage } from './pages/repair-orders/RepairOrderCreatePage'
import { RepairOrderDetailPage } from './pages/repair-orders/RepairOrderDetailPage'
import { RepairOrderEditPage } from './pages/repair-orders/RepairOrderEditPage'
import { WorkshopKanbanPage } from './pages/workshop/WorkshopKanbanPage'
import { PartsPage } from './pages/parts/PartsPage'
import { StockPage } from './pages/parts/StockPage'
import { SupplierPage } from './pages/suppliers/SupplierPage'
import { PurchaseOrderPage } from './pages/purchase-orders/PurchaseOrderPage'
import { SupplierInvoicePage } from './pages/supplier-invoices/SupplierInvoicePage'
import { ServicesExternesPage } from './pages/supplier-invoices/ServicesExternesPage'
import { TemplatesPage } from './pages/notifications/TemplatesPage'
import { InspectionTemplatesPage } from './pages/inspections/InspectionTemplatesPage'
import { InspectionsListPage } from './pages/inspections/InspectionsListPage'
import { InspectionExecutionPage } from './pages/inspections/InspectionExecutionPage'
import { InspectionApprovalPage } from './pages/inspections/InspectionApprovalPage'
import { KpiDashboardPage } from './pages/kpi/KpiDashboardPage'
import { VehiclesPage } from './pages/vehicles/VehiclesPage'
import { VehicleDetailPage } from './pages/vehicles/VehicleDetailPage'
import { VehicleCreatePage } from './pages/vehicles/VehicleCreatePage'
import { VehicleEditPage } from './pages/vehicles/VehicleEditPage'
import { QuotationsPage } from './pages/quotations/QuotationsPage'
import { QuotationDetailPage } from './pages/quotations/QuotationDetailPage'
import { QuotationCreatePage } from './pages/quotations/QuotationCreatePage'
import { InvoicesPage } from './pages/invoices/InvoicesPage'
import { InvoiceDetailPage } from './pages/invoices/InvoiceDetailPage'
import { AdvancePaymentsPage } from './pages/payments/AdvancePaymentsPage'
import { CashSessionsPage } from './pages/cash-sessions/CashSessionsPage'
import { CashSessionDetailPage } from './pages/cash-sessions/CashSessionDetailPage'
import { CreditNotesPage } from './pages/credit-notes/CreditNotesPage'
import { CreditNoteDetailPage } from './pages/credit-notes/CreditNoteDetailPage'
import { AccountingExportPage } from './pages/accounting/AccountingExportPage'
import { UsersPage } from './pages/admin/UsersPage'
import { RolesPage } from './pages/admin/RolesPage'
import { SettingsPage } from './pages/admin/SettingsPage'
import { AuditLogsPage } from './pages/admin/AuditLogsPage'
import { DocumentsPage } from './pages/documents/DocumentsPage'
import { OcrReviewPage } from './pages/ocr/OcrReviewPage'
import { DeliveryNoteCreatePage } from './pages/delivery-notes/DeliveryNoteCreatePage'
import { DeliveryNoteDetailPage } from './pages/delivery-notes/DeliveryNoteDetailPage'
import { DeliveryNotesListPage } from './pages/delivery-notes/DeliveryNotesListPage'
import { BonRetourListPage } from './pages/bon-retour/BonRetourListPage'
import { BonRetourCreatePage } from './pages/bon-retour/BonRetourCreatePage'
import { BonRetourDetailPage } from './pages/bon-retour/BonRetourDetailPage'
import { AvoirsFournisseursPage } from './pages/avoirs-fournisseurs/AvoirsFournisseursPage'
import { CreditOverrideRequestsPage } from './pages/credit-overrides/CreditOverrideRequestsPage'
import { CreditLimitChangeRequestsPage } from './pages/credit-overrides/CreditLimitChangeRequestsPage'
import { NotificationsPage } from './pages/notifications/NotificationsPage'

export const router = createBrowserRouter(
  [
  // Public routes — no shell
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/forgot-password',
    element: <ForgotPasswordPage />,
  },
  {
    path: '/reset-password',
    element: <ResetPasswordPage />,
  },
  {
    path: '/approve/:token',
    element: <InspectionApprovalPage />,
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
      { path: 'repair-orders/:publicId/edit', element: <RepairOrderEditPage /> },

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
      { path: 'supplier-services', element: <ServicesExternesPage /> },
      { path: 'bon-retour', element: <BonRetourListPage /> },
      { path: 'bon-retour/new', element: <BonRetourCreatePage /> },
      { path: 'bon-retour/:publicId', element: <BonRetourDetailPage /> },
      { path: 'avoirs-fournisseurs', element: <AvoirsFournisseursPage /> },

      // Notifications
      { path: 'notification-templates', element: <TemplatesPage /> },

      // Vehicles
      { path: 'vehicles', element: <VehiclesPage /> },
      { path: 'vehicles/new', element: <VehicleCreatePage /> },
      { path: 'vehicles/:id', element: <VehicleDetailPage /> },
      { path: 'vehicles/:id/edit', element: <VehicleEditPage /> },

      // Billing — quotations & invoices
      { path: 'quotations', element: <QuotationsPage /> },
      { path: 'quotations/new', element: <QuotationCreatePage /> },
      { path: 'quotations/:publicId', element: <QuotationDetailPage /> },
      { path: 'invoices', element: <InvoicesPage /> },
      { path: 'invoices/:publicId', element: <InvoiceDetailPage /> },

      // Delivery notes
      { path: 'delivery-notes', element: <DeliveryNotesListPage /> },
      { path: 'delivery-notes/new', element: <DeliveryNoteCreatePage /> },
      { path: 'delivery-notes/:publicId', element: <DeliveryNoteDetailPage /> },

      // Finance utilities
      { path: 'advance-payments', element: <AdvancePaymentsPage /> },
      { path: 'cash-sessions', element: <CashSessionsPage /> },
      { path: 'cash-sessions/:id', element: <CashSessionDetailPage /> },
      { path: 'credit-notes', element: <CreditNotesPage /> },
      { path: 'credit-notes/:id', element: <CreditNoteDetailPage /> },
      { path: 'accounting-export', element: <AccountingExportPage /> },

      // Analytics
      {
        path: 'kpi',
        element: (
          <ProtectedRoute requiredPermission="reporting.dashboard.read" deniedRoles={['mechanic']}>
            <KpiDashboardPage />
          </ProtectedRoute>
        ),
      },

      // Administration
      { path: 'users', element: <UsersPage /> },
      { path: 'roles', element: <RolesPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'audit-logs', element: <AuditLogsPage /> },
      { path: 'credit-override-requests', element: <CreditOverrideRequestsPage /> },
      { path: 'credit-override-requests/:id', element: <CreditOverrideRequestsPage /> },
      { path: 'credit-limit-requests', element: <CreditLimitChangeRequestsPage /> },
      { path: 'credit-limit-requests/:id', element: <CreditLimitChangeRequestsPage /> },
      { path: 'notifications', element: <NotificationsPage /> },

      // Documents & OCR
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'ocr/:extractionId', element: <OcrReviewPage /> },

      // Catch-all
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
  ]
)
