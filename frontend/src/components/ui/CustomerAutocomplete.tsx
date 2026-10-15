import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
  createFilterOptions,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'

interface CustomerAutocompleteProps {
  value: number | null
  onChange: (customerId: number | null, customer: CustomerSummary | null) => void
  label?: string
  required?: boolean
  error?: boolean
  helperText?: string
  disabled?: boolean
  size?: 'small' | 'medium'
  /**
   * Let the user create a walk-in client ("client passager") from just a name,
   * inline, without leaving the form. Only shown to users holding
   * `customer.create`. Leave off for filters.
   */
  allowCreate?: boolean
}

/** Synthetic last entry of the dropdown: "＋ Créer le client « name »". */
interface CreateOption {
  create: true
  name: string
}
type Option = CustomerSummary | CreateOption

const isCreateOption = (o: Option): o is CreateOption => 'create' in o

const customerLabel = (c: CustomerSummary) =>
  c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name

const filterCustomers = createFilterOptions<Option>({
  stringify: o => (isCreateOption(o) ? o.name : customerLabel(o)),
})

export function CustomerAutocomplete({
  value,
  onChange,
  label = 'Client',
  required,
  error,
  helperText,
  disabled,
  size = 'medium',
  allowCreate = false,
}: CustomerAutocompleteProps) {
  const { user } = useAuth()
  const { success } = useToast()
  const queryClient = useQueryClient()
  const canCreate =
    allowCreate && !disabled && (user?.permissions.includes('customer.create') ?? false)

  const [inputValue, setInputValue] = useState('')
  // Remembered so a client created a second ago stays selected even though it
  // is not in the current search results.
  const [selected, setSelected] = useState<CustomerSummary | null>(null)
  // Inline "new client" mode: the search field is replaced by a small form.
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [nameError, setNameError] = useState(false)

  const { data, isFetching } = useQuery({
    queryKey: ['customer-search', inputValue],
    queryFn: () => customerApi.list({ q: inputValue, page_size: 20, status: 'active' }),
    enabled: inputValue.length >= 1,
    staleTime: 10_000,
  })

  const results: CustomerSummary[] = data?.items ?? []
  const selectedOption =
    selected && selected.int_id === value
      ? selected
      : (results.find(o => o.int_id === value) ?? null)
  // The selection must stay in `options` or MUI warns and may drop it.
  const options: Option[] =
    selectedOption && !results.some(o => o.int_id === selectedOption.int_id)
      ? [selectedOption, ...results]
      : results

  const createMutation = useMutation({
    mutationFn: (fullName: string) => customerApi.quickCreate({ full_name: fullName }),
    // Runs even if the picker was unmounted mid-request: the client exists now.
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['customers'] })
      void queryClient.invalidateQueries({ queryKey: ['customer-search'] })
    },
  })

  function startCreate(prefill: string) {
    createMutation.reset()
    setNewName(prefill)
    setNameError(false)
    setCreating(true)
    // Stop the host form from submitting for the previous client while the new
    // one is being typed.
    if (value !== null) onChange(null, null)
  }

  function cancelCreate() {
    createMutation.reset()
    setCreating(false)
    setInputValue('')
  }

  function submitCreate() {
    const name = newName.trim()
    if (!name) {
      setNameError(true)
      return
    }
    createMutation.mutate(name, {
      // Per-call callback: react-query skips it if the picker unmounted (the
      // popup was closed) so a late result can never select a client in a form
      // the user already dismissed.
      onSuccess: created => {
        setSelected(created)
        setInputValue(customerLabel(created))
        setCreating(false)
        onChange(created.int_id, created)
        success(`Client « ${created.full_name} » créé`)
      },
    })
  }

  if (creating) {
    const createError = createMutation.isError
      ? axios.isAxiosError(createMutation.error) && createMutation.error.response?.status === 403
        ? "Vous n'avez pas le droit de créer un client."
        : 'Impossible de créer le client. Réessayez.'
      : null

    return (
      <Paper
        variant="outlined"
        role="group"
        aria-label="Nouveau client"
        sx={{ p: 2, borderRadius: 2, bgcolor: 'action.hover' }}
      >
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="subtitle2" fontWeight={700}>
              Nouveau client
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Seul le nom est requis. La fiche pourra être complétée plus tard.
            </Typography>
          </Box>
          <TextField
            label="Nom du client"
            value={newName}
            onChange={e => {
              setNewName(e.target.value)
              setNameError(false)
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                e.preventDefault()
                submitCreate()
              }
            }}
            required
            autoFocus
            fullWidth
            size={size}
            disabled={createMutation.isPending}
            error={nameError || !!error}
            helperText={
              nameError ? 'Le nom est requis' : error ? 'Créez le client pour continuer' : undefined
            }
            inputProps={{ maxLength: 255 }}
          />
          {createError && <Alert severity="error">{createError}</Alert>}
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={cancelCreate} disabled={createMutation.isPending} color="inherit">
              Annuler
            </Button>
            <Button
              variant="contained"
              onClick={submitCreate}
              disabled={createMutation.isPending}
              startIcon={
                createMutation.isPending ? <CircularProgress size={16} color="inherit" /> : undefined
              }
            >
              Créer le client
            </Button>
          </Stack>
        </Stack>
      </Paper>
    )
  }

  return (
    <Box>
      <Autocomplete
        value={selectedOption}
        onChange={(_, newValue) => {
          if (newValue && isCreateOption(newValue)) {
            startCreate(newValue.name)
            return
          }
          setSelected(newValue)
          onChange(newValue?.int_id ?? null, newValue)
        }}
        inputValue={inputValue}
        onInputChange={(_, v) => setInputValue(v)}
        options={options}
        filterOptions={(opts, state) => {
          const filtered = filterCustomers(opts, state)
          const typed = state.inputValue.trim()
          // Offer to create only once the search for this text has settled, so
          // a half-loaded list never shows "create" as the only choice.
          if (canCreate && typed && !isFetching) filtered.push({ create: true, name: typed })
          return filtered
        }}
        getOptionLabel={o => (isCreateOption(o) ? o.name : customerLabel(o))}
        isOptionEqualToValue={(a, b) =>
          !isCreateOption(a) && !isCreateOption(b) && a.int_id === b.int_id
        }
        loading={isFetching}
        disabled={disabled}
        noOptionsText={inputValue.length < 1 ? 'Tapez pour rechercher…' : 'Aucun client trouvé'}
        size={size}
        renderInput={params => (
          <TextField
            {...params}
            label={label}
            required={required}
            error={error}
            helperText={helperText}
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {isFetching ? <CircularProgress size={16} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) =>
          isCreateOption(option) ? (
            <Box
              component="li"
              {...props}
              key="__create__"
              sx={{ gap: 1, color: 'primary.main', fontWeight: 600 }}
            >
              <AddRoundedIcon fontSize="small" />
              <Typography variant="body2" fontWeight={600} noWrap>
                Créer le client « {option.name} »
              </Typography>
            </Box>
          ) : (
            <Box component="li" {...props} key={option.int_id}>
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  {option.company_name
                    ? `${option.full_name} — ${option.company_name}`
                    : option.full_name}
                </Typography>
                {option.phone_e164 && (
                  <Typography variant="caption" color="text.secondary">
                    {option.phone_e164}
                  </Typography>
                )}
              </Box>
            </Box>
          )
        }
      />
      {canCreate && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
          <Button
            size="small"
            startIcon={<AddRoundedIcon />}
            // Keep focus in the search field: blurring it makes MUI clear the
            // typed text before onClick runs, and we want to carry it over.
            onMouseDown={e => e.preventDefault()}
            onClick={() => startCreate(selectedOption ? '' : inputValue.trim())}
          >
            Nouveau client
          </Button>
        </Box>
      )}
    </Box>
  )
}
