import { useState } from 'react'
import { Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField } from '@mui/material'
import BookmarkAddRoundedIcon from '@mui/icons-material/BookmarkAddRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import { useLocalStoragePref } from '../../hooks/useLocalStoragePref'

interface SavedView<TState> {
  name: string
  state: TState
}

interface SavedViewsBarProps<TState> {
  /** localStorage key this page's saved views live under — one per list page,
   * e.g. "customers_list". Distinct from the state values themselves. */
  storageKey: string
  /** The page's current filter/sort state, captured when the user saves a view. */
  currentState: TState
  /** Applied when a saved view chip is clicked — hand it back to the page's
   * own useState setters, same shape as `currentState`. */
  onApply: (state: TState) => void
}

/**
 * A row of filter-preset chips a list page can save/reapply, on top of
 * whatever filter/sort state it already manages itself — this component
 * only persists and replays that state, it never owns it.
 */
export function SavedViewsBar<TState>({ storageKey, currentState, onApply }: SavedViewsBarProps<TState>) {
  const [views, setViews] = useLocalStoragePref<SavedView<TState>[]>(`${storageKey}_views`, [])
  const [saveOpen, setSaveOpen] = useState(false)
  const [name, setName] = useState('')

  const handleSave = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setViews(prev => [...prev.filter(v => v.name !== trimmed), { name: trimmed, state: currentState }])
    setName('')
    setSaveOpen(false)
  }

  const handleRemove = (viewName: string) => {
    setViews(prev => prev.filter(v => v.name !== viewName))
  }

  if (views.length === 0 && !saveOpen) {
    return (
      <Box sx={{ mb: 1.5 }}>
        <Button
          size="small"
          startIcon={<BookmarkAddRoundedIcon />}
          onClick={() => setSaveOpen(true)}
          sx={{ textTransform: 'none', color: 'text.secondary' }}
        >
          Enregistrer cette vue
        </Button>
        <SaveViewDialog
          open={saveOpen}
          name={name}
          onNameChange={setName}
          onSave={handleSave}
          onClose={() => setSaveOpen(false)}
        />
      </Box>
    )
  }

  return (
    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 1.5, rowGap: 1 }}>
      {views.map(v => (
        <Chip
          key={v.name}
          label={v.name}
          size="small"
          onClick={() => onApply(v.state)}
          onDelete={() => handleRemove(v.name)}
          deleteIcon={<CloseRoundedIcon />}
          sx={{ cursor: 'pointer' }}
        />
      ))}
      <Button
        size="small"
        startIcon={<BookmarkAddRoundedIcon />}
        onClick={() => setSaveOpen(true)}
        sx={{ textTransform: 'none', color: 'text.secondary' }}
      >
        Enregistrer la vue actuelle
      </Button>
      <SaveViewDialog
        open={saveOpen}
        name={name}
        onNameChange={setName}
        onSave={handleSave}
        onClose={() => setSaveOpen(false)}
      />
    </Stack>
  )
}

function SaveViewDialog({
  open,
  name,
  onNameChange,
  onSave,
  onClose,
}: {
  open: boolean
  name: string
  onNameChange: (v: string) => void
  onSave: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Enregistrer cette vue</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          fullWidth
          label="Nom de la vue"
          placeholder="Ex. Factures impayées"
          value={name}
          onChange={e => onNameChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onSave() }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={onSave} disabled={!name.trim()}>
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}
