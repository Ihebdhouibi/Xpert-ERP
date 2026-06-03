import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Autocomplete,
  Box,
  CircularProgress,
  TextField,
  Typography,
} from '@mui/material'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'

interface CustomerAutocompleteProps {
  value: number | null
  onChange: (customerId: number | null, customer: CustomerSummary | null) => void
  label?: string
  required?: boolean
  error?: boolean
  helperText?: string
  disabled?: boolean
  size?: 'small' | 'medium'
}

export function CustomerAutocomplete({
  value,
  onChange,
  label = 'Client',
  required,
  error,
  helperText,
  disabled,
  size = 'medium',
}: CustomerAutocompleteProps) {
  const [inputValue, setInputValue] = useState('')

  const { data, isFetching } = useQuery({
    queryKey: ['customer-search', inputValue],
    queryFn: () => customerApi.list({ q: inputValue, page_size: 10, status: 'active' }),
    enabled: inputValue.length >= 1 || value === null,
    staleTime: 10_000,
  })

  const options: CustomerSummary[] = data?.items ?? []

  const selectedOption = options.find(o => o.numeric_id === value) ?? null

  const getLabel = useCallback((c: CustomerSummary) => {
    const name = c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name
    return name
  }, [])

  return (
    <Autocomplete
      value={selectedOption}
      onChange={(_, newValue) => {
        onChange(newValue?.numeric_id ?? null, newValue)
      }}
      inputValue={inputValue}
      onInputChange={(_, v) => setInputValue(v)}
      options={options}
      getOptionLabel={getLabel}
      isOptionEqualToValue={(a, b) => a.numeric_id === b.numeric_id}
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
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.numeric_id}>
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
      )}
    />
  )
}
