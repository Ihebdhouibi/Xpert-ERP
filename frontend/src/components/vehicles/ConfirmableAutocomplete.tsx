import { useEffect, useState } from 'react'
import {
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  TextField,
  Typography,
} from '@mui/material'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import type { VehicleOption } from '../../lib/vehicleOptions'

interface ConfirmableAutocompleteProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: VehicleOption[]
  loading?: boolean
  disabled?: boolean
  required?: boolean
  error?: boolean
  helperText?: string
  placeholder?: string
  autoFocus?: boolean
  canDeleteCustomOptions?: boolean
  onDeleteCustomOption?: (label: string) => void
}

type PendingDialog =
  | { kind: 'fuzzy'; typed: string; match: string }
  | { kind: 'novel'; typed: string }

function levenshtein(a: string, b: string): number {
  const al = a.length
  const bl = b.length
  if (al === 0) return bl
  if (bl === 0) return al
  const matrix: number[][] = Array.from({ length: al + 1 }, () => new Array<number>(bl + 1).fill(0))
  for (let i = 0; i <= al; i++) matrix[i][0] = i
  for (let j = 0; j <= bl; j++) matrix[0][j] = j
  for (let i = 1; i <= al; i++) {
    for (let j = 1; j <= bl; j++) {
      const cost = a[i - 1].toLowerCase() === b[j - 1].toLowerCase() ? 0 : 1
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost,
      )
    }
  }
  return matrix[al][bl]
}

// Ratio-based, not absolute distance: short model codes one edit apart ("208"/"308",
// "X3"/"X5") are genuinely different vehicles and must NOT prompt "did you mean",
// while longer typos ("Renau" -> "Renault") still should.
function findCloseMatch(typed: string, candidates: string[]): string | null {
  if (typed.length < 3) return null
  let best: { label: string; distance: number; maxLen: number } | null = null
  for (const candidate of candidates) {
    const distance = levenshtein(typed, candidate)
    if (distance === 0) continue
    const maxLen = Math.max(typed.length, candidate.length)
    if (!best || distance < best.distance) best = { label: candidate, distance, maxLen }
  }
  if (!best) return null
  return best.distance / best.maxLen <= 0.3 ? best.label : null
}

export function ConfirmableAutocomplete({
  label,
  value,
  onChange,
  options,
  loading,
  disabled,
  required,
  error,
  helperText,
  placeholder,
  autoFocus,
  canDeleteCustomOptions,
  onDeleteCustomOption,
}: ConfirmableAutocompleteProps) {
  const [inputValue, setInputValue] = useState(value)
  const [pending, setPending] = useState<PendingDialog | null>(null)

  useEffect(() => {
    setInputValue(value)
  }, [value])

  const optionLabels = options.map(o => o.label)
  const customLabels = new Set(options.filter(o => o.isCustom).map(o => o.label.toLowerCase()))

  const commit = (raw: string) => {
    const trimmed = raw.trim()
    setInputValue(trimmed)
    onChange(trimmed)
  }

  const handleBlur = () => {
    const trimmed = inputValue.trim()
    if (trimmed === value) return
    if (!trimmed) {
      onChange('')
      return
    }
    const exact = optionLabels.find(o => o.toLowerCase() === trimmed.toLowerCase())
    if (exact) {
      commit(exact)
      return
    }
    const closeMatch = findCloseMatch(trimmed, optionLabels)
    if (closeMatch) {
      setPending({ kind: 'fuzzy', typed: trimmed, match: closeMatch })
    } else {
      setPending({ kind: 'novel', typed: trimmed })
    }
  }

  const useMatch = () => {
    if (pending?.kind === 'fuzzy') commit(pending.match)
    setPending(null)
  }

  const useTyped = () => {
    if (pending) commit(pending.typed)
    setPending(null)
  }

  const cancelPending = () => setPending(null)

  return (
    <>
      <Autocomplete
        freeSolo
        options={optionLabels}
        inputValue={inputValue}
        onInputChange={(_e, newValue) => setInputValue(newValue)}
        onChange={(_e, newValue) => {
          if (typeof newValue === 'string') commit(newValue)
        }}
        onBlur={handleBlur}
        loading={loading}
        disabled={disabled}
        renderOption={(liProps, option) => (
          <Box
            component="li"
            {...liProps}
            key={option}
            sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          >
            <Typography variant="body2">{option}</Typography>
            {canDeleteCustomOptions && customLabels.has(option.toLowerCase()) && (
              <IconButton
                size="small"
                aria-label={`Supprimer ${option}`}
                onClick={e => {
                  e.stopPropagation()
                  onDeleteCustomOption?.(option)
                }}
              >
                <CloseRoundedIcon fontSize="inherit" />
              </IconButton>
            )}
          </Box>
        )}
        renderInput={params => (
          <TextField
            {...params}
            label={label}
            required={required}
            error={error}
            helperText={helperText}
            placeholder={placeholder}
            autoFocus={autoFocus}
            fullWidth
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {loading ? <CircularProgress color="inherit" size={16} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
      />

      <Dialog open={pending?.kind === 'fuzzy'} onClose={cancelPending} maxWidth="xs" fullWidth>
        <DialogTitle>
          Vouliez-vous dire « {pending?.kind === 'fuzzy' ? pending.match : ''} » ?
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            « {pending?.kind === 'fuzzy' ? pending.typed : ''} » ressemble à une valeur déjà
            connue.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={useTyped}>
            Non, ajouter « {pending?.kind === 'fuzzy' ? pending.typed : ''} »
          </Button>
          <Button variant="contained" onClick={useMatch}>
            Utiliser « {pending?.kind === 'fuzzy' ? pending.match : ''} »
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={pending?.kind === 'novel'} onClose={cancelPending} maxWidth="xs" fullWidth>
        <DialogTitle>Confirmer l'orthographe</DialogTitle>
        <DialogContent>
          <DialogContentText>
            « {pending?.kind === 'novel' ? pending.typed : ''} » n'est pas dans la liste. Cette
            valeur sera ajoutée aux suggestions de votre garage.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={cancelPending}>Modifier</Button>
          <Button variant="contained" onClick={useTyped}>
            Confirmer
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
