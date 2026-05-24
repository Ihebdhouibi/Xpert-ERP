import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
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

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <DashboardPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/customers',
    element: (
      <ProtectedRoute>
        <CustomersListPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/customers/new',
    element: (
      <ProtectedRoute>
        <CustomerCreatePage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/customers/:publicId',
    element: (
      <ProtectedRoute>
        <CustomerDetailPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/customers/:publicId/edit',
    element: (
      <ProtectedRoute>
        <CustomerEditPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/repair-orders',
    element: (
      <ProtectedRoute>
        <RepairOrdersListPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/repair-orders/new',
    element: (
      <ProtectedRoute>
        <RepairOrderCreatePage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/repair-orders/:publicId',
    element: (
      <ProtectedRoute>
        <RepairOrderDetailPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/workshop',
    element: (
      <ProtectedRoute>
        <WorkshopKanbanPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/tablet',
    element: (
      <ProtectedRoute>
        <TabletViewPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/parts',
    element: (
      <ProtectedRoute>
        <PartsPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/stock',
    element: (
      <ProtectedRoute>
        <StockPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
