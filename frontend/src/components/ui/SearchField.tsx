import { InputAdornment, TextField } from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'

interface SearchFieldProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  fullWidth?: boolean
}

export function SearchField({ value, onChange, placeholder, fullWidth = true }: SearchFieldProps) {
  return (
    <TextField
      placeholder={placeholder ?? 'Rechercher…'}
      fullWidth={fullWidth}
      size="small"
      value={value}
      onChange={e => onChange(e.target.value)}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchRoundedIcon sx={{ color: 'text.disabled', fontSize: 18 }} />
          </InputAdornment>
        ),
      }}
    />
  )
}
