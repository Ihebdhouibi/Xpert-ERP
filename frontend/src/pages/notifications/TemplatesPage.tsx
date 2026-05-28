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
  Divider,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import PreviewIcon from '@mui/icons-material/Visibility'
import EmailIcon from '@mui/icons-material/Email'
import SmsIcon from '@mui/icons-material/Sms'
import {
  notificationApi,
  type NotificationTemplate,
} from '../../lib/notificationApi'

// ---------------------------------------------------------------------------
// Channel chip
// ---------------------------------------------------------------------------

function ChannelChip({ channel }: { channel: string }) {
  return channel === 'email' ? (
    <Chip icon={<EmailIcon />} label="Email" size="small" color="primary" variant="outlined" />
  ) : (
    <Chip icon={<SmsIcon />} label="SMS" size="small" color="secondary" variant="outlined" />
  )
}

function TriggerTypeBadge({ type }: { type: string }) {
  return (
    <Chip
      label={type === 'event' ? 'Événement' : 'Planifié'}
      size="small"
      color={type === 'event' ? 'success' : 'info'}
      variant="filled"
    />
  )
}

// ---------------------------------------------------------------------------
// Edit dialog
// ---------------------------------------------------------------------------

interface EditDialogProps {
  template: NotificationTemplate
  open: boolean
  onClose: () => void
}

function EditDialog({ template, open, onClose }: EditDialogProps) {
  const qc = useQueryClient()
  const [subject, setSubject] = useState(template.subject ?? '')
  const [body, setBody] = useState(template.body)
  const [active, setActive] = useState(template.active)
  const [preview, setPreview] = useState<{ subject: string | null; body: string } | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewTab, setPreviewTab] = useState(0)

  const save = useMutation({
    mutationFn: () =>
      notificationApi.update(template.id, {
        subject: subject || null,
        body,
        active,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notification-templates'] })
      onClose()
    },
  })

  const handlePreview = async () => {
    setPreviewLoading(true)
    try {
      const res = await notificationApi.preview(template.id)
      setPreview(res)
      setPreviewTab(1)
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6">
            Modifier le template — <code>{template.code}</code>
          </Typography>
          <ChannelChip channel={template.channel} />
          {template.is_override && (
            <Chip label="Personnalisé" size="small" color="warning" variant="outlined" />
          )}
        </Stack>
      </DialogTitle>
      <DialogContent>
        <Tabs value={previewTab} onChange={(_, v) => setPreviewTab(v)} sx={{ mb: 2 }}>
          <Tab label="Éditeur" />
          <Tab label="Aperçu" disabled={!preview} />
        </Tabs>

        {previewTab === 0 && (
          <Stack spacing={2}>
            {template.channel === 'email' && (
              <TextField
                label="Sujet (Jinja2)"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                fullWidth
                size="small"
                helperText="Ex: Votre véhicule {{ vehicle }} est prêt"
              />
            )}
            <TextField
              label="Corps du message (Jinja2)"
              value={body}
              onChange={e => setBody(e.target.value)}
              fullWidth
              multiline
              minRows={10}
              inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
              helperText="Variables disponibles selon le déclencheur. Cliquez sur Aperçu pour tester."
            />
            <FormControlLabel
              control={<Switch checked={active} onChange={e => setActive(e.target.checked)} />}
              label="Actif"
            />
          </Stack>
        )}

        {previewTab === 1 && preview && (
          <Box>
            {preview.subject && (
              <Box mb={2}>
                <Typography variant="caption" color="text.secondary">
                  SUJET
                </Typography>
                <Typography variant="body1" fontWeight="bold">
                  {preview.subject}
                </Typography>
                <Divider sx={{ mt: 1 }} />
              </Box>
            )}
            <Typography variant="caption" color="text.secondary">
              CORPS
            </Typography>
            {template.channel === 'email' ? (
              <Box
                sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2, mt: 1 }}
                dangerouslySetInnerHTML={{ __html: preview.body }}
              />
            ) : (
              <Paper variant="outlined" sx={{ p: 2, mt: 1, fontFamily: 'monospace', fontSize: 13 }}>
                {preview.body}
              </Paper>
            )}
          </Box>
        )}

        {save.isError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Erreur lors de la sauvegarde.
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button
          startIcon={previewLoading ? <CircularProgress size={14} /> : <PreviewIcon />}
          onClick={handlePreview}
          disabled={previewLoading}
        >
          Aperçu
        </Button>
        <Box flex={1} />
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          onClick={() => save.mutate()}
          disabled={save.isPending || !body.trim()}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function TemplatesPage() {
  const [editing, setEditing] = useState<NotificationTemplate | null>(null)

  const { data: triggers = [] } = useQuery({
    queryKey: ['notification-triggers'],
    queryFn: notificationApi.triggers,
  })

  const { data: templates = [], isLoading } = useQuery({
    queryKey: ['notification-templates'],
    queryFn: notificationApi.list,
  })

  // Group templates by trigger code
  const byCode = templates.reduce<Record<string, NotificationTemplate[]>>((acc, tmpl) => {
    ;(acc[tmpl.code] ??= []).push(tmpl)
    return acc
  }, {})

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" pt={8}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box p={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" fontWeight="bold">
          Templates de notification
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {templates.length} templates • {triggers.length} déclencheurs
        </Typography>
      </Stack>

      <Stack spacing={3}>
        {triggers.map(trigger => {
          const group = byCode[trigger.code] ?? []
          return (
            <Paper key={trigger.code} variant="outlined" sx={{ p: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" mb={1.5}>
                <Typography variant="subtitle1" fontWeight="bold">
                  {trigger.label}
                </Typography>
                <TriggerTypeBadge type={trigger.type} />
              </Stack>
              <Typography variant="body2" color="text.secondary" mb={2}>
                {trigger.description}
              </Typography>

              <Stack spacing={1}>
                {group.length === 0 && (
                  <Typography variant="body2" color="text.disabled">
                    Aucun template trouvé.
                  </Typography>
                )}
                {group.map(tmpl => (
                  <Box
                    key={tmpl.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.5,
                      p: 1.5,
                      borderRadius: 1,
                      bgcolor: 'action.hover',
                    }}
                  >
                    <ChannelChip channel={tmpl.channel} />
                    <Typography
                      variant="body2"
                      sx={{ flex: 1, fontFamily: 'monospace', fontSize: 12, color: 'text.secondary' }}
                      noWrap
                    >
                      {tmpl.subject || tmpl.body.slice(0, 80) + '…'}
                    </Typography>
                    {tmpl.is_override && (
                      <Tooltip title="Template personnalisé (remplace le système)">
                        <Chip label="Custom" size="small" color="warning" variant="outlined" />
                      </Tooltip>
                    )}
                    {!tmpl.active && (
                      <Chip label="Inactif" size="small" color="default" variant="outlined" />
                    )}
                    <Tooltip title="Modifier">
                      <Button
                        size="small"
                        startIcon={<EditIcon />}
                        onClick={() => setEditing(tmpl)}
                        variant="outlined"
                      >
                        Modifier
                      </Button>
                    </Tooltip>
                  </Box>
                ))}
              </Stack>
            </Paper>
          )
        })}
      </Stack>

      {editing && (
        <EditDialog
          template={editing}
          open={!!editing}
          onClose={() => setEditing(null)}
        />
      )}
    </Box>
  )
}
