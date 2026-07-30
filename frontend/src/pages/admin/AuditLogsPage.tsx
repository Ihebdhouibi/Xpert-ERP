import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import HistoryRoundedIcon from '@mui/icons-material/HistoryRounded'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import { PageHeader } from '../../components/ui/PageHeader'

const TRACKED_COMPONENTS = [
  {
    component: 'auth',
    label: 'Authentification',
    icon: <LockRoundedIcon sx={{ fontSize: 16, color: '#7C3AED' }} />,
    color: '#7C3AED',
    actions: ['login', 'logout', 'password_reset', 'account_locked', 'account_unlocked'],
  },
  {
    component: 'rbac',
    label: 'Utilisateurs & Rôles',
    icon: <PersonRoundedIcon sx={{ fontSize: 16, color: '#334155' }} />,
    color: '#334155',
    actions: ['create', 'update', 'deactivate', 'roles_assigned'],
  },
  {
    component: 'repair_order',
    label: 'Ordres de réparation',
    icon: <BuildRoundedIcon sx={{ fontSize: 16, color: '#D97706' }} />,
    color: '#D97706',
    actions: ['create', 'update', 'status_transition', 'delete'],
  },
  {
    component: 'invoice',
    label: 'Facturation',
    icon: <PaymentsRoundedIcon sx={{ fontSize: 16, color: '#16A34A' }} />,
    color: '#16A34A',
    actions: ['create', 'issue', 'cancel', 'payment_registered', 'exported'],
  },
  {
    component: 'supplier_invoice',
    label: 'Factures fournisseurs',
    icon: <InventoryRoundedIcon sx={{ fontSize: 16, color: '#EA580C' }} />,
    color: '#EA580C',
    actions: ['create', 'post', 'approve', 'mark_paid', 'override_with_reason'],
  },
  {
    component: 'config',
    label: 'Paramètres système',
    icon: <InfoRoundedIcon sx={{ fontSize: 16, color: '#0891B2' }} />,
    color: '#0891B2',
    actions: ['setting_upserted', 'setting_deleted'],
  },
]

const AUDIT_LOG_FIELDS = [
  { field: 'id', type: 'bigint', description: 'Identifiant unique de l\'entrée' },
  { field: 'garage_id', type: 'bigint', description: 'Isolation multi-tenant' },
  { field: 'user_id', type: 'bigint | null', description: 'Utilisateur ayant effectué l\'action (null = système)' },
  { field: 'timestamp', type: 'datetime', description: 'Horodatage serveur UTC' },
  { field: 'component', type: 'string', description: 'Module source (auth, repair_order, invoice…)' },
  { field: 'action', type: 'string', description: 'Verbe (create, update, delete, login…)' },
  { field: 'entity_type', type: 'string | null', description: 'Type d\'objet modifié (app_user, invoice…)' },
  { field: 'entity_id', type: 'bigint | null', description: 'Identifiant de l\'objet modifié' },
  { field: 'old_value', type: 'jsonb | null', description: 'Snapshot avant modification (champs sensibles masqués)' },
  { field: 'new_value', type: 'jsonb | null', description: 'Snapshot après modification (champs sensibles masqués)' },
  { field: 'reason', type: 'string | null', description: 'Motif fourni par l\'acteur (ex: acceptation d\'écart)' },
  { field: 'request_id', type: 'string | null', description: 'Identifiant de corrélation X-Request-ID' },
  { field: 'ip_address', type: 'string | null', description: 'Adresse IP du client' },
  { field: 'duration_ms', type: 'int | null', description: 'Durée de l\'opération en millisecondes' },
]

export function AuditLogsPage() {
  return (
    <Box>
      <PageHeader
        title="Journal d'audit"
        subtitle="Traçabilité complète des actions utilisateurs et système"
      />

      <Alert
        severity="warning"
        icon={<HistoryRoundedIcon />}
        sx={{ mb: 3, borderRadius: 2 }}
      >
        <Typography variant="body2" fontWeight={600} mb={0.5}>
          Endpoint de consultation non encore exposé
        </Typography>
        <Typography variant="body2">
          Le journal d'audit est <strong>écrit en base de données</strong> par tous les modules du backend.
          Un endpoint REST de consultation (<code>GET /api/v1/audit-logs</code>) sera exposé dans le prochain sprint.
          Cette page affiche la structure du journal et les événements tracés.
        </Typography>
      </Alert>

      {/* What's tracked */}
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 0 }}>
          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ px: 3, py: 2, borderBottom: '1px solid #F1F5F9' }}>
            <Box
              sx={{
                width: 36, height: 36, borderRadius: '10px', bgcolor: '#F1F5F9',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <HistoryRoundedIcon sx={{ color: '#334155', fontSize: 18 }} />
            </Box>
            <Box>
              <Typography variant="subtitle2" fontWeight={700}>Événements tracés</Typography>
              <Typography variant="caption" color="text.secondary">Tous ces événements sont enregistrés automatiquement</Typography>
            </Box>
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', lg: '1fr 1fr 1fr' },
              gap: 0,
            }}
          >
            {TRACKED_COMPONENTS.map((comp, i) => (
              <Box
                key={comp.component}
                sx={{
                  p: 2.5,
                  borderRight: { sm: i % 2 === 0 ? '1px solid #F1F5F9' : 'none', lg: i % 3 !== 2 ? '1px solid #F1F5F9' : 'none' },
                  borderBottom: '1px solid #F8FAFC',
                }}
              >
                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                  <Box
                    sx={{
                      width: 28, height: 28, borderRadius: '7px',
                      bgcolor: comp.color + '18',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    {comp.icon}
                  </Box>
                  <Typography variant="body2" fontWeight={700}>{comp.label}</Typography>
                </Stack>
                <Stack direction="row" flexWrap="wrap" gap={0.5}>
                  {comp.actions.map(action => (
                    <Chip
                      key={action}
                      label={action}
                      size="small"
                      sx={{
                        fontSize: '0.6875rem',
                        fontFamily: 'monospace',
                        bgcolor: comp.color + '12',
                        color: comp.color,
                        fontWeight: 600,
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* Schema documentation */}
      <Card>
        <CardContent sx={{ p: 0 }}>
          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ px: 3, py: 2, borderBottom: '1px solid #F1F5F9' }}>
            <Typography variant="subtitle2" fontWeight={700}>Structure du journal d'audit</Typography>
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Champ</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Description</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {AUDIT_LOG_FIELDS.map(f => (
                <TableRow key={f.field}>
                  <TableCell>
                    <Typography variant="caption" fontFamily="monospace" fontWeight={700} color="primary.main">
                      {f.field}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" fontFamily="monospace" color="text.secondary">
                      {f.type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">{f.description}</Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <Divider />
          <Box sx={{ px: 3, py: 2 }}>
            <Typography variant="caption" color="text.secondary">
              <strong>Sécurité :</strong> Les champs sensibles (<code>password</code>, <code>token</code>, <code>secret</code>)
              sont automatiquement masqués (<code>[REDACTED]</code>) dans les snapshots avant/après.
              Les logs sont isolés par <code>garage_id</code> et ne sont jamais exposés entre garages.
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
