import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from '@mui/material'
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import { usersApi } from '../../lib/usersApi'
import { SYSTEM_ROLES } from './UsersPage'
import { PageHeader } from '../../components/ui/PageHeader'
import { EmptyState } from '../../components/ui/EmptyState'

// Permission descriptions per role — matches the backend RBAC design
const ROLE_PERMISSIONS: Record<string, string[]> = {
  super_admin: [
    'Accès complet à tous les modules',
    'Gestion multi-garage',
    'Modification des paramètres système',
    'Lecture des journaux d\'audit',
  ],
  admin: [
    'Gestion des utilisateurs et rôles',
    'Lecture/écriture sur tous les modules',
    'Configuration du garage',
    'Export comptable',
  ],
  receptionist: [
    'Clients & véhicules',
    'Ordres de réparation (création, lecture)',
    'Devis & factures (lecture)',
    'Sessions caisse',
  ],
  mechanic: [
    'Ordres de réparation (lecture, transition de statut)',
    'Pointage du temps',
    'Inspections (exécution)',
    'Pièces (lecture)',
  ],
  accountant: [
    'Factures & paiements',
    'Avoirs & avances',
    'Export comptable',
    'KPIs & rapports financiers',
  ],
  parts_manager: [
    'Catalogue pièces (CRUD)',
    'Gestion du stock',
    'Commandes fournisseurs',
    'Factures fournisseurs',
  ],
}

export function RolesPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['users', 'all-for-roles'],
    queryFn: () => usersApi.list({ page: 1, page_size: 100 }),
  })

  // Build role → users map from the actual user data
  const roleMap: Record<string, { fullName: string; email: string }[]> = {}
  for (const role of SYSTEM_ROLES) {
    roleMap[role.code] = []
  }
  for (const user of data?.items ?? []) {
    for (const roleCode of user.roles) {
      if (!roleMap[roleCode]) roleMap[roleCode] = []
      roleMap[roleCode].push({ fullName: user.full_name, email: user.email })
    }
  }

  return (
    <Box>
      <PageHeader
        title="Rôles & Permissions"
        subtitle="Distribution des rôles et référentiel des accès"
      />

      <Alert
        severity="info"
        icon={<InfoRoundedIcon />}
        sx={{ mb: 3, borderRadius: 2 }}
      >
        Les rôles sont des profils d'accès prédéfinis. Pour modifier les rôles d'un utilisateur, rendez-vous dans la page{' '}
        <strong>Utilisateurs</strong> et cliquez sur l'icône 🔑 sur la ligne de l'utilisateur.
      </Alert>

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Impossible de charger les données utilisateurs.
        </Alert>
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '1fr 1fr 1fr' },
          gap: 2.5,
        }}
      >
        {SYSTEM_ROLES.map(role => {
          const users = roleMap[role.code] ?? []
          const perms = ROLE_PERMISSIONS[role.code] ?? []

          return (
            <Card
              key={role.code}
              sx={{
                border: '1px solid #E2E8F0',
                transition: 'all 0.15s ease',
                '&:hover': { borderColor: role.color, boxShadow: `0 4px 16px ${role.color}20` },
              }}
            >
              <CardContent sx={{ p: 0 }}>
                {/* Header */}
                <Box
                  sx={{
                    px: 2.5,
                    py: 2,
                    borderBottom: '1px solid #F1F5F9',
                    borderTop: '3px solid',
                    borderTopColor: role.color,
                    borderRadius: '12px 12px 0 0',
                  }}
                >
                  <Stack direction="row" alignItems="center" justifyContent="space-between">
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <AdminPanelSettingsRoundedIcon sx={{ color: role.color, fontSize: 20 }} />
                      <Typography variant="subtitle2" fontWeight={700}>{role.label}</Typography>
                    </Stack>
                    <Box
                      sx={{
                        minWidth: 26, height: 26, borderRadius: '6px',
                        bgcolor: role.color + '18',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        px: 1,
                      }}
                    >
                      <Typography variant="caption" fontWeight={800} sx={{ color: role.color }}>
                        {isLoading ? '…' : users.length}
                      </Typography>
                    </Box>
                  </Stack>
                  <Typography variant="caption" color="text.disabled" fontFamily="monospace" mt={0.25} display="block">
                    {role.code}
                  </Typography>
                </Box>

                {/* Permissions */}
                <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid #F8FAFC' }}>
                  <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Accès
                  </Typography>
                  <Stack spacing={0.5}>
                    {perms.map(p => (
                      <Stack key={p} direction="row" alignItems="flex-start" spacing={0.75}>
                        <Box sx={{ width: 4, height: 4, borderRadius: '50%', bgcolor: role.color, mt: 0.75, flexShrink: 0 }} />
                        <Typography variant="caption" color="text.secondary">{p}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                </Box>

                {/* Users with this role */}
                <Box sx={{ px: 2.5, py: 2 }}>
                  <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Utilisateurs assignés
                  </Typography>
                  {isLoading ? (
                    <Typography variant="caption" color="text.disabled">Chargement…</Typography>
                  ) : users.length === 0 ? (
                    <EmptyState
                      icon={<PersonRoundedIcon sx={{ fontSize: 28, color: '#CBD5E1' }} />}
                      title="Aucun utilisateur"
                      description="Aucun compte n'a ce rôle"
                    />
                  ) : (
                    <Stack spacing={0.75}>
                      {users.map(u => (
                        <Stack key={u.email} direction="row" alignItems="center" spacing={1}>
                          <Box
                            sx={{
                              width: 28, height: 28, borderRadius: '7px',
                              bgcolor: role.color + '18',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              flexShrink: 0,
                            }}
                          >
                            <PersonRoundedIcon sx={{ color: role.color, fontSize: 14 }} />
                          </Box>
                          <Box>
                            <Typography variant="caption" fontWeight={600}>{u.fullName}</Typography>
                            <Typography variant="caption" color="text.disabled" display="block">{u.email}</Typography>
                          </Box>
                        </Stack>
                      ))}
                    </Stack>
                  )}
                </Box>
              </CardContent>
            </Card>
          )
        })}
      </Box>

      {/* Note about role listing */}
      <Box sx={{ mt: 4, p: 2.5, bgcolor: '#F8FAFC', borderRadius: 2, border: '1px solid #E2E8F0' }}>
        <Stack direction="row" spacing={1.5} alignItems="flex-start">
          <InfoRoundedIcon sx={{ color: '#94A3B8', fontSize: 18, mt: 0.25 }} />
          <Box>
            <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={0.5}>
              Gestion des rôles personnalisés
            </Typography>
            <Typography variant="caption" color="text.secondary">
              La création de rôles personnalisés et la modification de la matrice de permissions
              sont disponibles via l'API backend. Un éditeur visuel de permissions sera ajouté
              dans une prochaine version.
            </Typography>
          </Box>
        </Stack>
      </Box>
    </Box>
  )
}
