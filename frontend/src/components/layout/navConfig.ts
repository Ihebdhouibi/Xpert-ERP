import type { SvgIconComponent } from '@mui/icons-material'
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import ViewKanbanRoundedIcon from '@mui/icons-material/ViewKanbanRounded'
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import PointOfSaleRoundedIcon from '@mui/icons-material/PointOfSaleRounded'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import ShoppingCartRoundedIcon from '@mui/icons-material/ShoppingCartRounded'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import AssignmentReturnRoundedIcon from '@mui/icons-material/AssignmentReturnRounded'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import WarehouseRoundedIcon from '@mui/icons-material/WarehouseRounded'
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded'
import GroupRoundedIcon from '@mui/icons-material/GroupRounded'
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded'
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import CreditScoreRoundedIcon from '@mui/icons-material/CreditScoreRounded'
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded'
import FolderRoundedIcon from '@mui/icons-material/FolderRounded'

export interface NavItem {
  label: string
  path: string
  icon: SvgIconComponent
  permission?: string
  /** Hide this item for users holding any of these roles (e.g. mechanic). */
  hideForRoles?: string[]
  exact?: boolean
}

export interface NavSection {
  label: string
  items: NavItem[]
}

export const navSections: NavSection[] = [
  {
    label: 'Atelier',
    items: [
      {
        label: 'Tableau de bord',
        path: '/',
        icon: DashboardRoundedIcon,
        exact: true,
      },
      {
        label: 'Ordres de réparation',
        path: '/repair-orders',
        icon: BuildRoundedIcon,
        permission: 'repair_order.read',
      },
      {
        label: 'Suivi Atelier',
        path: '/workshop',
        icon: ViewKanbanRoundedIcon,
        permission: 'repair_order.transition',
      },
      {
        label: 'Documents',
        path: '/documents',
        icon: FolderRoundedIcon,
        permission: 'document.read',
      },
    ],
  },
  {
    label: 'Commercial',
    items: [
      {
        label: 'Clients',
        path: '/customers',
        icon: PeopleRoundedIcon,
        permission: 'customer.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Véhicules',
        path: '/vehicles',
        icon: DirectionsCarRoundedIcon,
        permission: 'vehicle.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Devis',
        path: '/quotations',
        icon: DescriptionRoundedIcon,
        permission: 'quotation.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Bons de livraison',
        path: '/delivery-notes',
        icon: LocalShippingRoundedIcon,
        permission: 'invoice.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Factures',
        path: '/invoices',
        icon: ReceiptRoundedIcon,
        permission: 'invoice.read',
        hideForRoles: ['mechanic'],
      },
    ],
  },
  {
    label: 'Finance',
    items: [
      {
        label: 'Avances & Paiements',
        path: '/advance-payments',
        icon: PaymentsRoundedIcon,
        permission: 'payment.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Sessions caisse',
        path: '/cash-sessions',
        icon: PointOfSaleRoundedIcon,
        permission: 'cash_session.read',
      },
      {
        label: 'Avoirs',
        path: '/credit-notes',
        icon: AccountBalanceRoundedIcon,
        permission: 'credit_note.read',
      },
    ],
  },
  {
    label: 'Achats',
    items: [
      {
        label: 'Fournisseurs',
        path: '/suppliers',
        icon: LocalShippingRoundedIcon,
        permission: 'supplier.read',
      },
      {
        label: 'Bons de commande',
        path: '/purchase-orders',
        icon: ShoppingCartRoundedIcon,
        permission: 'purchase_order.read',
      },
      {
        label: 'Factures fournisseurs',
        path: '/supplier-invoices',
        icon: ReceiptLongRoundedIcon,
        permission: 'supplier_invoice.read',
      },
      {
        label: 'Bons de retour',
        path: '/bon-retour',
        icon: AssignmentReturnRoundedIcon,
        permission: 'bon_de_retour.read',
      },
      {
        label: 'Avoirs fournisseurs',
        path: '/avoirs-fournisseurs',
        icon: ReceiptRoundedIcon,
        permission: 'supplier_credit_note.read',
      },
      {
        label: 'Export comptable',
        path: '/accounting-export',
        icon: UploadFileRoundedIcon,
        permission: 'accounting_export.create',
      },
    ],
  },
  {
    label: 'Stock',
    items: [
      {
        label: 'Catalogue pièces',
        path: '/parts',
        icon: InventoryRoundedIcon,
        permission: 'part.read',
        hideForRoles: ['mechanic'],
      },
      {
        label: 'Gestion du stock',
        path: '/stock',
        icon: WarehouseRoundedIcon,
        permission: 'part.read',
        hideForRoles: ['mechanic'],
      },
    ],
  },
  {
    label: 'Analytique',
    items: [
      {
        label: 'KPIs & rapports',
        path: '/kpi',
        icon: BarChartRoundedIcon,
        permission: 'reporting.dashboard.read',
        hideForRoles: ['mechanic'],
      },
    ],
  },
  {
    label: 'Administration',
    items: [
      {
        label: 'Utilisateurs',
        path: '/users',
        icon: GroupRoundedIcon,
        permission: 'users.read',
      },
      {
        label: 'Rôles & permissions',
        path: '/roles',
        icon: AdminPanelSettingsRoundedIcon,
        permission: 'roles.read',
      },
      {
        label: 'Paramètres',
        path: '/settings',
        icon: SettingsRoundedIcon,
        permission: 'system.settings.read',
      },
      {
        label: 'Modèles notifications',
        path: '/notification-templates',
        icon: NotificationsRoundedIcon,
        permission: 'notification.template.manage',
      },
      {
        label: "Journal d'audit",
        path: '/audit-logs',
        icon: HistoryRoundedIcon,
        permission: 'audit.read',
      },
      {
        label: 'Dérogations de crédit',
        path: '/credit-override-requests',
        icon: CreditScoreRoundedIcon,
        permission: 'credit.override.manage',
      },
    ],
  },
]

export function getNavItemByPath(pathname: string): NavItem | undefined {
  for (const section of navSections) {
    for (const item of section.items) {
      if (item.exact ? pathname === item.path : pathname.startsWith(item.path) && item.path !== '/') {
        return item
      }
      if (item.exact && pathname === '/') return item
    }
  }
  return navSections[0].items[0]
}
