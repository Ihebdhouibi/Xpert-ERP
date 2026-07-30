import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import AddCircleOutlineRoundedIcon from '@mui/icons-material/AddCircleOutlineRounded'
import ChecklistRoundedIcon from '@mui/icons-material/ChecklistRounded'
import { inspectionApi, type TemplateSection, type TemplateItem } from '../../lib/inspectionApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { EmptyState } from '../../components/ui/EmptyState'
import { TableLoadingSkeleton } from '../../components/ui/LoadingScreen'

function newSection(): TemplateSection {
  return { id: crypto.randomUUID(), title: '', items: [] }
}

function newItem(): TemplateItem {
  return { id: crypto.randomUUID(), label: '', requires_photo: false }
}

function SectionEditor({
  section,
  onChange,
  onDelete,
}: {
  section: TemplateSection
  onChange: (s: TemplateSection) => void
  onDelete: () => void
}) {
  const updateItem = (idx: number, item: TemplateItem) => {
    const items = [...section.items]
    items[idx] = item
    onChange({ ...section, items })
  }
  const removeItem = (idx: number) =>
    onChange({ ...section, items: section.items.filter((_, i) => i !== idx) })

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        p: 2,
        mb: 2,
        bgcolor: '#FAFAFA',
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <TextField
          fullWidth
          size="small"
          label="Titre de la section"
          value={section.title}
          onChange={e => onChange({ ...section, title: e.target.value })}
        />
        <IconButton color="error" onClick={onDelete} size="small">
          <DeleteRoundedIcon fontSize="small" />
        </IconButton>
      </Stack>

      <Stack spacing={0.75}>
        {section.items.map((item, idx) => (
          <Stack key={item.id} direction="row" spacing={1} alignItems="center">
            <Box
              sx={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                flexShrink: 0,
                ml: 0.5,
              }}
            />
            <TextField
              fullWidth
              size="small"
              placeholder={`Élément ${idx + 1}`}
              value={item.label}
              onChange={e => updateItem(idx, { ...item, label: e.target.value })}
            />
            <IconButton size="small" color="error" onClick={() => removeItem(idx)}>
              <DeleteRoundedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Stack>
        ))}
      </Stack>

      <Button
        size="small"
        startIcon={<AddCircleOutlineRoundedIcon />}
        onClick={() => onChange({ ...section, items: [...section.items, newItem()] })}
        sx={{ mt: 1.25, color: 'text.secondary' }}
      >
        Ajouter un élément
      </Button>
    </Box>
  )
}

function CreateTemplateDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [sections, setSections] = useState<TemplateSection[]>([newSection()])
  const [error, setError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () => inspectionApi.createTemplate({ name, sections }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inspection-templates'] })
      onClose()
      setName('')
      setSections([newSection()])
      setError(null)
    },
    onError: () => setError('Erreur lors de la création du modèle.'),
  })

  const updateSection = (idx: number, s: TemplateSection) => {
    const updated = [...sections]
    updated[idx] = s
    setSections(updated)
  }

  const totalItems = sections.reduce((sum, s) => sum + s.items.length, 0)

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Box sx={{ color: 'primary.main' }}>
            <ChecklistRoundedIcon />
          </Box>
          <span>Nouveau modèle d'inspection</span>
        </Stack>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          fullWidth
          label="Nom du modèle *"
          value={name}
          onChange={e => setName(e.target.value)}
          sx={{ mb: 3 }}
          placeholder="ex. Contrôle technique 52 points"
          autoFocus
        />
        <Typography variant="caption" color="text.secondary" display="block" mb={1.5} fontWeight={600}>
          SECTIONS ({sections.length})
        </Typography>
        {sections.map((s, idx) => (
          <SectionEditor
            key={s.id}
            section={s}
            onChange={updated => updateSection(idx, updated)}
            onDelete={() => setSections(sections.filter((_, i) => i !== idx))}
          />
        ))}
        <Button
          startIcon={<AddRoundedIcon />}
          onClick={() => setSections([...sections, newSection()])}
          variant="outlined"
          fullWidth
          sx={{ mt: 0.5 }}
        >
          Ajouter une section
        </Button>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Typography variant="caption" color="text.secondary" mr="auto">
          {sections.length} section{sections.length !== 1 ? 's' : ''} · {totalItems} élément{totalItems !== 1 ? 's' : ''}
        </Typography>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          Créer le modèle
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function InspectionTemplatesPage() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['inspection-templates'],
    queryFn: () => inspectionApi.listTemplates({ page_size: 100 }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => inspectionApi.deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inspection-templates'] })
      setDeleteTarget(null)
    },
  })

  const templates = data?.items ?? []

  return (
    <Box>
      <PageHeader
        title="Modèles d'inspection"
        subtitle="Définissez les grilles de contrôle utilisées lors des inspections véhicule"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouveau modèle
          </Button>
        }
      />

      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Impossible de charger les modèles d'inspection.
        </Alert>
      )}

      {isLoading ? (
        <TableLoadingSkeleton cols={5} rows={4} />
      ) : templates.length === 0 ? (
        <EmptyState
          title="Aucun modèle d'inspection"
          description="Créez votre premier modèle pour structurer vos contrôles véhicule."
          action={
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => setCreateOpen(true)}
            >
              Nouveau modèle
            </Button>
          }
        />
      ) : (
        <Stack spacing={2}>
          {templates.map(template => {
            const totalItems = template.sections.reduce((sum, s) => sum + s.items.length, 0)
            return (
              <Card
                key={template.id}
                sx={{
                  transition: 'box-shadow 0.15s ease, transform 0.15s ease',
                  '&:hover': {
                    boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
                    transform: 'translateY(-1px)',
                  },
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
                    <Stack direction="row" alignItems="center" spacing={2} flex={1} minWidth={0}>
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: '10px',
                          bgcolor: '#F1F5F9',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <ChecklistRoundedIcon sx={{ color: '#334155', fontSize: 20 }} />
                      </Box>
                      <Box flex={1} minWidth={0}>
                        <Typography variant="subtitle1" fontWeight={700} noWrap>
                          {template.name}
                        </Typography>
                        <Stack direction="row" spacing={0.75} mt={0.75} flexWrap="wrap" useFlexGap>
                          <Chip
                            label={`${template.sections.length} section${template.sections.length !== 1 ? 's' : ''}`}
                            size="small"
                            sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600, height: 22 }}
                          />
                          <Chip
                            label={`${totalItems} élément${totalItems !== 1 ? 's' : ''}`}
                            size="small"
                            sx={{ bgcolor: '#F0FDF4', color: '#16A34A', fontWeight: 600, height: 22 }}
                          />
                          {template.sections.slice(0, 3).map(s => (
                            <Chip
                              key={s.id}
                              label={s.title || '(sans titre)'}
                              size="small"
                              variant="outlined"
                              sx={{ height: 22, fontSize: '0.6875rem' }}
                            />
                          ))}
                          {template.sections.length > 3 && (
                            <Chip
                              label={`+${template.sections.length - 3}`}
                              size="small"
                              variant="outlined"
                              sx={{ height: 22, fontSize: '0.6875rem', color: 'text.disabled' }}
                            />
                          )}
                        </Stack>
                      </Box>
                    </Stack>
                    <IconButton
                      color="error"
                      size="small"
                      onClick={() => setDeleteTarget(template.id)}
                      sx={{ ml: 1, flexShrink: 0 }}
                    >
                      <DeleteRoundedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                </CardContent>
              </Card>
            )
          })}
        </Stack>
      )}

      <CreateTemplateDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      <ConfirmDialog
        open={!!deleteTarget}
        title="Supprimer ce modèle ?"
        message="Cette action est irréversible. Toutes les inspections liées à ce modèle conserveront leurs données, mais le modèle ne sera plus disponible."
        confirmLabel="Supprimer"
        dangerous
        loading={deleteMutation.isPending}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </Box>
  )
}
