import { createBrowserRouter, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { LoginPage } from './pages/auth/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { CustomersListPage } from './pages/customers/CustomersListPage'
import { CustomerCreatePage } from './pages/customers/CustomerCreatePage'
import { CustomerEditPage } from './pages/customers/CustomerEditPage'
import { CustomerDetailPage } from './pages/customers/CustomerDetailPage'

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
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
