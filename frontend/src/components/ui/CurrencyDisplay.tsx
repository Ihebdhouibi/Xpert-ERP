import { Typography, type TypographyProps } from '@mui/material'

interface CurrencyDisplayProps extends Omit<TypographyProps, 'children'> {
  minor: number | null | undefined
  currency?: string
  colorize?: boolean
  showSign?: boolean
}

export function CurrencyDisplay({
  minor,
  currency = 'EUR',
  colorize = false,
  showSign = false,
  ...typographyProps
}: CurrencyDisplayProps) {
  if (minor == null) {
    return (
      <Typography component="span" color="text.disabled" {...typographyProps}>
        —
      </Typography>
    )
  }

  const value = minor / 100
  const formatted = value.toLocaleString('fr-FR', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  })

  const display = showSign && value > 0 ? `+${formatted}` : formatted

  const color = colorize
    ? value < 0
      ? 'error.main'
      : value > 0
        ? 'success.main'
        : 'text.secondary'
    : typographyProps.color

  return (
    <Typography component="span" {...typographyProps} color={color}>
      {display}
    </Typography>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatMinor(
  minor: number | null | undefined,
  currency = 'EUR',
): string {
  if (minor == null) return '—'
  return (minor / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  })
}
