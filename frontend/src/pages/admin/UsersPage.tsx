import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  FormGroup,
  IconButton,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import KeyRoundedIcon from '@mui/icons-material/KeyRounded'
import PersonOffRoundedIcon from '@mui/icons-material/PersonOffRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import VisibilityOffRoundedIcon from '@mui/icons-material/VisibilityOffRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import { usersApi, type UserSummary } from '../../lib/usersApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'
import { useAuth } from '../../contexts/AuthContext'

// ─── Role catalog ────────────────────────────────────────────────────────────

// eslint-disable-next-line react-refresh/only-export-components
export const SYSTEM_ROLES: { code: string; label: string; color: string }[] = [
  { code: 'super_admin', label: 'Super Admin', color: '#7C3AED' },
  { code: 'admin', label: 'Admin', color: '#334155' },
  { code: 'receptionist', label: 'Réceptionniste', color: '#0891B2' },
  { code: 'mechanic', label: 'Mécanicien', color: '#D97706' },
  { code: 'accountant', label: 'Comptable', color: '#16A34A' },
  { code: 'parts_manager', label: 'Gestionnaire stock', color: '#EA580C' },
]

// eslint-disable-next-line react-refresh/only-export-components
export function roleLabelFor(code: string) {
  return SYSTEM_ROLES.find(r => r.code === code)?.label ?? code
}

function RoleChips({ roles }: { roles: string[] }) {
  if (roles.length === 0) {
    return <Typography variant="caption" color="text.disabled">Aucun rôle</Typography>
  }
  return (
    <Stack direction="row" spacing={0.5} flexWrap="wrap">
      {roles.map(code => {
        const def = SYSTEM_ROLES.find(r => r.code === code)
        return (
          <Chip
            key={code}
            label={def?.label ?? code}
            size="small"
            sx={{
              fontWeight: 600,
              fontSize: '0.6875rem',
              bgcolor: (def?.color ?? '#64748B') + '18',
              color: def?.color ?? '#64748B',
              border: 'none',
            }}
          />
        )
      })}
    </Stack>
  )
}

// ─── Create dialog ────────────────────────────────────────────────────────────

function CreateUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [selectedRoles, setSelectedRoles] = useState<string[]>([])
  const [formError, setFormError] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      usersApi.create({ email, full_name: fullName, password, role_codes: selectedRoles }),
    onSuccess: () => {
      success('Utilisateur créé avec succès.')
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
      setEmail(''); setFullName(''); setPassword(''); setSelectedRoles([]); setFormError('')
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (detail?.includes('already exists')) {
        setFormError('Cet email est déjà utilisé.')
      } else {
        toastError('Erreur lors de la création.')
      }
    },
  })

  const handleSubmit = () => {
    setFormError('')
    if (!email.trim()) { setFormError('Email requis.'); return }
    if (!fullName.trim()) { setFormError('Nom requis.'); return }
    if (password.length < 12) { setFormError('Mot de passe minimum 12 caractères.'); return }
    if (!/[A-Z]/.test(password)) { setFormError('Le mot de passe doit contenir au moins une majuscule.'); return }
    if (!/[a-z]/.test(password)) { setFormError('Le mot de passe doit contenir au moins une minuscule.'); return }
    if (!/\d/.test(password)) { setFormError('Le mot de passe doit contenir au moins un chiffre.'); return }
    mutation.mutate()
  }

  const toggleRole = (code: string) =>
    setSelectedRoles(prev => prev.includes(code) ? prev.filter(r => r !== code) : [...prev, code])

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Nouvel utilisateur</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} pt={1}>
          {formError && <Alert severity="error" sx={{ py: 0.5 }}>{formError}</Alert>}
          <TextField
            label="Email"
            type="email"
            fullWidth
            value={email}
            onChange={e => setEmail(e.target.value)}
            autoComplete="off"
          />
          <TextField
            label="Nom complet"
            fullWidth
            value={fullName}
            onChange={e => setFullName(e.target.value)}
          />
          <TextField
            label="Mot de passe temporaire"
            type={showPassword ? 'text' : 'password'}
            fullWidth
            value={password}
            onChange={e => setPassword(e.target.value)}
            helperText="Min. 12 caractères, 1 majuscule, 1 minuscule, 1 chiffre"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton size="small" onClick={() => setShowPassword(v => !v)}>
                    {showPassword ? <VisibilityOffRoundedIcon fontSize="small" /> : <VisibilityRoundedIcon fontSize="small" />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Box>
            <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Rôles
            </Typography>
            <FormGroup row sx={{ gap: 0.5 }}>
              {SYSTEM_ROLES.map(role => (
                <FormControlLabel
                  key={role.code}
                  control={
                    <Checkbox
                      size="small"
                      checked={selectedRoles.includes(role.code)}
                      onChange={() => toggleRole(role.code)}
                      sx={{ p: 0.5 }}
                    />
                  }
                  label={
                    <Typography variant="caption" fontWeight={600}>{role.label}</Typography>
                  }
                  sx={{
                    m: 0,
                    px: 1.5,
                    py: 0.5,
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: selectedRoles.includes(role.code) ? role.color : '#E2E8F0',
                    bgcolor: selectedRoles.includes(role.code) ? role.color + '12' : 'transparent',
                  }}
                />
              ))}
            </FormGroup>
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={mutation.isPending}>
          {mutation.isPending ? 'Création…' : 'Créer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ─── Edit dialog ──────────────────────────────────────────────────────────────

function EditUserDialog({
  user,
  onClose,
}: {
  user: UserSummary | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [status, setStatus] = useState<'active' | 'inactive'>(
    user?.status === 'locked' ? 'active' : (user?.status ?? 'active')
  )

  const mutation = useMutation({
    mutationFn: () => usersApi.update(user!.id, { full_name: fullName, status }),
    onSuccess: () => {
      success('Utilisateur mis à jour.')
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: () => toastError('Erreur lors de la mise à jour.'),
  })

  if (!user) return null

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Modifier l'utilisateur</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} pt={1}>
          <TextField
            label="Nom complet"
            fullWidth
            value={fullName}
            onChange={e => setFullName(e.target.value)}
          />
          <TextField
            label="Statut"
            select
            fullWidth
            value={status}
            onChange={e => setStatus(e.target.value as 'active' | 'inactive')}
          >
            <MenuItem value="active">Actif</MenuItem>
            <MenuItem value="inactive">Inactif</MenuItem>
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={() => mutation.mutate()} disabled={mutation.isPending || !fullName.trim()}>
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ─── Assign roles dialog ──────────────────────────────────────────────────────

function AssignRolesDialog({
  user,
  onClose,
}: {
  user: UserSummary | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()
  const [selected, setSelected] = useState<string[]>(user?.roles ?? [])

  const mutation = useMutation({
    mutationFn: () => usersApi.assignRoles(user!.id, selected),
    onSuccess: () => {
      success('Rôles mis à jour.')
      qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(detail ?? 'Erreur lors de l\'assignation des rôles.')
    },
  })

  const toggle = (code: string) =>
    setSelected(prev => prev.includes(code) ? prev.filter(r => r !== code) : [...prev, code])

  if (!user) return null

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Rôles — {user.full_name}</DialogTitle>
      <DialogContent>
        <Stack spacing={1} pt={1}>
          {SYSTEM_ROLES.map(role => (
            <FormControlLabel
              key={role.code}
              control={
                <Checkbox
                  checked={selected.includes(role.code)}
                  onChange={() => toggle(role.code)}
                  sx={{ color: role.color, '&.Mui-checked': { color: role.color } }}
                />
              }
              label={
                <Box>
                  <Typography variant="body2" fontWeight={600}>{role.label}</Typography>
                  <Typography variant="caption" color="text.secondary" fontFamily="monospace">{role.code}</Typography>
                </Box>
              }
              sx={{
                m: 0,
                px: 1.5,
                py: 1,
                borderRadius: 1.5,
                border: '1px solid',
                borderColor: selected.includes(role.code) ? role.color : '#E2E8F0',
                bgcolor: selected.includes(role.code) ? role.color + '0D' : 'transparent',
                width: '100%',
              }}
            />
          ))}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const { success, error: toastError } = useToast()
  const [page, setPage] = useState(0)
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<UserSummary | null>(null)
  const [rolesTarget, setRolesTarget] = useState<UserSummary | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<UserSummary | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['users', page],
    queryFn: () => usersApi.list({ page: page + 1, page_size: 20 }),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => usersApi.deactivate(id),
    onSuccess: () => {
      success('Utilisateur désactivé.')
      setDeactivateTarget(null)
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(detail ?? 'Erreur lors de la désactivation.')
      setDeactivateTarget(null)
    },
  })

  const columns: Column<UserSummary>[] = [
    {
      id: 'user',
      label: 'Utilisateur',
      render: row => (
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              bgcolor: row.status === 'active' ? '#E2E8F0' : '#F1F5F9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <PersonRoundedIcon sx={{ color: row.status === 'active' ? '#1E293B' : '#94A3B8', fontSize: 18 }} />
          </Box>
          <Box>
            <Typography variant="body2" fontWeight={700}>{row.full_name}</Typography>
            <Typography variant="caption" color="text.secondary">{row.email}</Typography>
          </Box>
        </Stack>
      ),
    },
    {
      id: 'roles',
      label: 'Rôles',
      render: row => <RoleChips roles={row.roles} />,
    },
    {
      id: 'status',
      label: 'Statut',
      width: 110,
      render: row => <StatusChip status={row.status} />,
    },
    {
      id: 'last_login',
      label: 'Dernière connexion',
      width: 170,
      render: row => (
        <Typography variant="caption" color="text.secondary">
          {row.last_login_at
            ? new Date(row.last_login_at).toLocaleString('fr-FR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              })
            : 'Jamais connecté'}
        </Typography>
      ),
    },
    {
      id: 'created',
      label: 'Créé le',
      width: 110,
      render: row => (
        <Typography variant="caption" color="text.secondary">
          {new Date(row.created_at).toLocaleDateString('fr-FR')}
        </Typography>
      ),
    },
    {
      id: 'actions',
      label: '',
      width: 110,
      align: 'right',
      render: row => (
        <Stack direction="row" justifyContent="flex-end" spacing={0.25}>
          <Tooltip title="Modifier">
            <IconButton size="small" onClick={e => { e.stopPropagation(); setEditTarget(row) }}>
              <EditRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Gérer les rôles">
            <IconButton size="small" onClick={e => { e.stopPropagation(); setRolesTarget(row) }}>
              <KeyRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
          {row.id !== me?.id && row.status !== 'inactive' && (
            <Tooltip title="Désactiver">
              <IconButton
                size="small"
                color="error"
                onClick={e => { e.stopPropagation(); setDeactivateTarget(row) }}
              >
                <PersonOffRoundedIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      ),
    },
  ]

  return (
    <Box>
      <PageHeader
        title="Utilisateurs"
        subtitle={data ? `${data.total} utilisateur${data.total !== 1 ? 's' : ''}` : 'Gestion des accès'}
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>
            Nouvel utilisateur
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.id}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger la liste des utilisateurs."
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun utilisateur"
        emptyDescription="Créez le premier compte utilisateur pour votre équipe."
      />

      <CreateUserDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <EditUserDialog user={editTarget} onClose={() => setEditTarget(null)} />
      <AssignRolesDialog user={rolesTarget} onClose={() => setRolesTarget(null)} />

      <ConfirmDialog
        open={!!deactivateTarget}
        title="Désactiver l'utilisateur"
        message={`Désactiver ${deactivateTarget?.full_name} (${deactivateTarget?.email}) ? L'utilisateur ne pourra plus se connecter.`}
        confirmLabel="Désactiver"
        dangerous
        loading={deactivateMutation.isPending}
        onConfirm={() => deactivateTarget && deactivateMutation.mutate(deactivateTarget.id)}
        onCancel={() => setDeactivateTarget(null)}
      />
    </Box>
  )
}
