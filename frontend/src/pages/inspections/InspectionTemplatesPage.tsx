import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import { inspectionApi, type TemplateSection, type TemplateItem } from '../../lib/inspectionApi'

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
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
        <TextField
          fullWidth
          size="small"
          label="Titre de la section"
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
        />
        <IconButton color="error" onClick={onDelete}>
          <DeleteIcon />
        </IconButton>
      </Stack>
      {section.items.map((item, idx) => (
        <Stack key={item.id} direction="row" spacing={1} alignItems="center" mb={0.5}>
          <TextField
            fullWidth
            size="small"
            label={`Élément ${idx + 1}`}
            value={item.label}
            onChange={(e) => updateItem(idx, { ...item, label: e.target.value })}
          />
          <IconButton size="small" color="error" onClick={() => removeItem(idx)}>
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Stack>
      ))}
      <Button
        size="small"
        startIcon={<AddCircleIcon />}
        onClick={() => onChange({ ...section, items: [...section.items, newItem()] })}
        sx={{ mt: 0.5 }}
      >
        Ajouter un élément
      </Button>
    </Paper>
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

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Créer un modèle d'inspection</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          fullWidth
          label="Nom du modèle"
          value={name}
          onChange={(e) => setName(e.target.value)}
          sx={{ mb: 3 }}
        />
        {sections.map((s, idx) => (
          <SectionEditor
            key={s.id}
            section={s}
            onChange={(updated) => updateSection(idx, updated)}
            onDelete={() => setSections(sections.filter((_, i) => i !== idx))}
          />
        ))}
        <Button
          startIcon={<AddIcon />}
          onClick={() => setSections([...sections, newSection()])}
          variant="outlined"
          fullWidth
        >
          Ajouter une section
        </Button>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          Créer
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

  return (
    <Box sx={{ p: 3, maxWidth: 900, mx: 'auto' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Modèles d'inspection
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {data?.total ?? 0} modèle{(data?.total ?? 0) !== 1 ? 's' : ''}
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Nouveau modèle
        </Button>
      </Stack>

      {isLoading && <CircularProgress />}
      {isError && <Alert severity="error">Impossible de charger les modèles.</Alert>}

      {data?.items.map((template) => (
        <Paper key={template.id} sx={{ mb: 2, p: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="h6" fontWeight={600}>
                {template.name}
              </Typography>
              <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap" useFlexGap>
                {template.sections.map((s) => (
                  <Chip
                    key={s.id}
                    label={`${s.title || '(sans titre)'} · ${s.items.length} élément${s.items.length !== 1 ? 's' : ''}`}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Stack>
            </Box>
            <IconButton color="error" onClick={() => setDeleteTarget(template.id)}>
              <DeleteIcon />
            </IconButton>
          </Stack>
        </Paper>
      ))}

      {data?.items.length === 0 && !isLoading && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            Aucun modèle d'inspection. Créez-en un pour commencer.
          </Typography>
        </Paper>
      )}

      <CreateTemplateDialog open={createOpen} onClose={() => setCreateOpen(false)} />

      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Supprimer ce modèle ?</DialogTitle>
        <DialogContent>
          <Typography>Cette action est irréversible.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Annuler</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
          >
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
