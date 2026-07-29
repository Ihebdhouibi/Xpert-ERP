import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import { customerApi } from '../../lib/customerApi'
import type { CustomerImportResult } from '../../lib/customerApi'
import { useToast } from '../../contexts/ToastContext'

interface CustomerImportDialogProps {
  open: boolean
  onClose: () => void
}

const ACCEPT = '.xlsx,.xlsm'

export function CustomerImportDialog({ open, onClose }: CustomerImportDialogProps) {
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<CustomerImportResult | null>(null)

  const mutation = useMutation({
    mutationFn: (f: File) => customerApi.importXlsx(f),
    onSuccess: (data) => {
      setResult(data)
      if (data.created > 0) {
        success(`${data.created} client(s) importé(s).`)
        queryClient.invalidateQueries({ queryKey: ['customers'] })
      }
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(detail ?? "Échec de l'import du fichier.")
    },
  })

  const handleClose = () => {
    if (mutation.isPending) return
    setFile(null)
    setResult(null)
    mutation.reset()
    onClose()
  }

  const handlePick = () => inputRef.current?.click()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setFile(f)
    setResult(null)
    // Allow re-selecting the same file later.
    e.target.value = ''
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: 3 } }}>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <UploadFileRoundedIcon sx={{ color: 'primary.main', fontSize: 22 }} />
        Importer des clients (Excel)
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" lineHeight={1.7} mb={2}>
          Sélectionnez un fichier <strong>.xlsx</strong> avec une ligne d'en-tête. Colonnes
          reconnues : Nom, Prénom, Nom de l'entreprise, Téléphone, E-mail, Adresse, Code postal,
          Ville. Les colonnes vides sont ignorées, les doublons (même téléphone ou e-mail) sont
          évités.
        </Typography>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={handleFileChange}
        />

        <Stack direction="row" spacing={1.5} alignItems="center">
          <Button variant="outlined" onClick={handlePick} disabled={mutation.isPending}>
            Choisir un fichier
          </Button>
          <Typography variant="body2" color="text.secondary" noWrap>
            {file ? file.name : 'Aucun fichier sélectionné'}
          </Typography>
        </Stack>

        {result && (
          <Box mt={3}>
            <Divider sx={{ mb: 2 }} />
            <Alert severity={result.created > 0 ? 'success' : 'info'} sx={{ mb: 2 }}>
              {result.created} créé(s) · {result.skipped} ignoré(s) (doublons) ·{' '}
              {result.errors.length} erreur(s) sur {result.total_rows} ligne(s).
            </Alert>
            {result.errors.length > 0 && (
              <List dense sx={{ maxHeight: 200, overflow: 'auto', bgcolor: 'action.hover', borderRadius: 2 }}>
                {result.errors.map((e) => (
                  <ListItem key={e.row}>
                    <ListItemText
                      primary={`Ligne ${e.row}`}
                      secondary={e.reason}
                      primaryTypographyProps={{ variant: 'body2', fontWeight: 600 }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={mutation.isPending} color="inherit">
          {result ? 'Fermer' : 'Annuler'}
        </Button>
        <Button
          variant="contained"
          onClick={() => file && mutation.mutate(file)}
          disabled={!file || mutation.isPending}
          startIcon={mutation.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Importer
        </Button>
      </DialogActions>
    </Dialog>
  )
}
