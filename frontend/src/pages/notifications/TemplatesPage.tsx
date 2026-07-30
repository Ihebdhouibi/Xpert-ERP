import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import PreviewRoundedIcon from '@mui/icons-material/PreviewRounded'
import EmailRoundedIcon from '@mui/icons-material/EmailRounded'
import SmsRoundedIcon from '@mui/icons-material/SmsRounded'
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded'
import {
  notificationApi,
  type NotificationTemplate,
} from '../../lib/notificationApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { LoadingScreen } from '../../components/ui/LoadingScreen'

function ChannelChip({ channel }: { channel: string }) {
  return channel === 'email' ? (
    <Chip
      icon={<EmailRoundedIcon />}
      label="Email"
      size="small"
      sx={{ bgcolor: '#E2E8F0', color: '#1E293B', fontWeight: 600, '& .MuiChip-icon': { color: '#1E293B' } }}
    />
  ) : (
    <Chip
      icon={<SmsRoundedIcon />}
      label="SMS"
      size="small"
      sx={{ bgcolor: '#F5F3FF', color: '#7C3AED', fontWeight: 600, '& .MuiChip-icon': { color: '#7C3AED' } }}
    />
  )
}

function TriggerBadge({ type }: { type: string }) {
  return (
    <Chip
      label={type === 'event' ? 'Événement' : 'Planifié'}
      size="small"
      sx={{
        bgcolor: type === 'event' ? '#F0FDF4' : '#E2E8F0',
        color: type === 'event' ? '#16A34A' : '#1E293B',
        fontWeight: 600,
        fontSize: '0.6875rem',
        height: 22,
      }}
    />
  )
}

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
      notificationApi.update(template.id, { subject: subject || null, body, active }),
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

  // Rendered inline (not in a Dialog) to avoid nesting complexity
  if (!open) return null

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: 1300,
        bgcolor: 'rgba(15,23,42,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <Card sx={{ width: '100%', maxWidth: 760, maxHeight: '90vh', display: 'flex', flexDirection: 'column', borderRadius: 3 }}>
        <Box sx={{ p: 3, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Typography variant="h6" fontWeight={700} flex={1}>
              Modifier le template
            </Typography>
            <ChannelChip channel={template.channel} />
            <Typography variant="body2" fontFamily="monospace" color="text.secondary">
              {template.code}
            </Typography>
            {template.is_override && (
              <Chip
                label="Personnalisé"
                size="small"
                sx={{ bgcolor: '#FFFBEB', color: '#D97706', fontWeight: 600 }}
              />
            )}
          </Stack>
        </Box>

        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          <Tabs value={previewTab} onChange={(_, v) => setPreviewTab(v)} sx={{ mb: 2.5 }}>
            <Tab label="Éditeur" />
            <Tab label="Aperçu" disabled={!preview} />
          </Tabs>

          {previewTab === 0 && (
            <Stack spacing={2.5}>
              {template.channel === 'email' && (
                <TextField
                  label="Sujet (Jinja2)"
                  value={subject}
                  onChange={e => setSubject(e.target.value)}
                  fullWidth
                  helperText='Ex: Votre véhicule {{ vehicle }} est prêt'
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
                label="Template actif"
              />
            </Stack>
          )}

          {previewTab === 1 && preview && (
            <Box>
              {preview.subject && (
                <Box mb={2.5}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.75}>
                    SUJET
                  </Typography>
                  <Typography variant="body1" fontWeight={700}>{preview.subject}</Typography>
                  <Divider sx={{ mt: 1.5 }} />
                </Box>
              )}
              <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.75}>
                CORPS
              </Typography>
              {template.channel === 'email' ? (
                <Box
                  sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1.5, p: 2 }}
                  dangerouslySetInnerHTML={{ __html: preview.body }}
                />
              ) : (
                <Box
                  sx={{ bgcolor: '#F8FAFC', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, p: 2, fontFamily: 'monospace', fontSize: 13 }}
                >
                  {preview.body}
                </Box>
              )}
            </Box>
          )}

          {save.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              Erreur lors de la sauvegarde.
            </Alert>
          )}
        </Box>

        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ p: 2.5, borderTop: '1px solid', borderColor: 'divider' }}
        >
          <Button
            startIcon={previewLoading ? undefined : <PreviewRoundedIcon />}
            onClick={handlePreview}
            disabled={previewLoading}
          >
            {previewLoading ? 'Chargement…' : 'Aperçu'}
          </Button>
          <Box flex={1} />
          <Button variant="outlined" onClick={onClose}>Annuler</Button>
          <Button
            variant="contained"
            onClick={() => save.mutate()}
            disabled={save.isPending || !body.trim()}
          >
            Enregistrer
          </Button>
        </Stack>
      </Card>
    </Box>
  )
}

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

  const byCode = templates.reduce<Record<string, NotificationTemplate[]>>((acc, tmpl) => {
    ;(acc[tmpl.code] ??= []).push(tmpl)
    return acc
  }, {})

  const activeCount = templates.filter(t => t.active).length
  const overrideCount = templates.filter(t => t.is_override).length

  if (isLoading) return <LoadingScreen />

  return (
    <Box>
      <PageHeader
        title="Templates de notification"
        subtitle={`${templates.length} templates · ${triggers.length} déclencheurs · ${activeCount} actifs · ${overrideCount} personnalisés`}
      />

      <Stack spacing={2.5}>
        {triggers.map(trigger => {
          const group = byCode[trigger.code] ?? []
          return (
            <Card key={trigger.code}>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" spacing={1.5} alignItems="center" mb={0.75}>
                  <Box sx={{ color: 'primary.main' }}>
                    <NotificationsRoundedIcon sx={{ fontSize: 20 }} />
                  </Box>
                  <Typography variant="subtitle1" fontWeight={700} flex={1}>
                    {trigger.label}
                  </Typography>
                  <TriggerBadge type={trigger.type} />
                </Stack>
                <Typography variant="body2" color="text.secondary" mb={2.5}>
                  {trigger.description}
                </Typography>

                <Divider sx={{ mb: 2 }} />

                {group.length === 0 ? (
                  <Typography variant="body2" color="text.disabled">
                    Aucun template configuré pour ce déclencheur.
                  </Typography>
                ) : (
                  <Stack spacing={1}>
                    {group.map(tmpl => (
                      <Stack
                        key={tmpl.id}
                        direction="row"
                        alignItems="center"
                        spacing={1.5}
                        sx={{
                          p: 1.5,
                          borderRadius: 1.5,
                          border: '1px solid',
                          borderColor: 'divider',
                          bgcolor: tmpl.active ? '#FAFAFA' : '#F8FAFC',
                          opacity: tmpl.active ? 1 : 0.65,
                        }}
                      >
                        <ChannelChip channel={tmpl.channel} />
                        <Typography
                          variant="body2"
                          sx={{ flex: 1, fontFamily: 'monospace', fontSize: '0.8rem', color: 'text.secondary' }}
                          noWrap
                        >
                          {tmpl.subject || tmpl.body.slice(0, 80) + '…'}
                        </Typography>
                        <Stack direction="row" spacing={0.75} alignItems="center">
                          {tmpl.is_override && (
                            <Chip
                              label="Custom"
                              size="small"
                              sx={{ bgcolor: '#FFFBEB', color: '#D97706', fontWeight: 600, fontSize: '0.6875rem', height: 20 }}
                            />
                          )}
                          {!tmpl.active && (
                            <Chip
                              label="Inactif"
                              size="small"
                              sx={{ bgcolor: '#F1F5F9', color: '#94A3B8', fontWeight: 600, fontSize: '0.6875rem', height: 20 }}
                            />
                          )}
                          <Button
                            size="small"
                            startIcon={<EditRoundedIcon />}
                            onClick={() => setEditing(tmpl)}
                            variant="outlined"
                            sx={{ fontSize: '0.8125rem' }}
                          >
                            Modifier
                          </Button>
                        </Stack>
                      </Stack>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>
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
