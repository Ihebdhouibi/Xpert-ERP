/**
 * MoneyField — a number input for monetary amounts.
 *
 * The form/API works in minor units (cents), but the user sees and edits
 * EUROS: the value is shown in euros and the up/down arrows step by €1
 * (configurable). Conversion happens inside this component, so callers keep
 * storing cents and nothing downstream changes.
 */
import { useEffect, useState } from 'react'
import { InputAdornment, TextField } from '@mui/material'
import type { TextFieldProps } from '@mui/material'

type MoneyFieldProps = Omit<TextFieldProps, 'value' | 'onChange' | 'type'> & {
  /** Amount in minor units (cents). */
  valueMinor: number
  /** Called with the new amount in minor units (cents). */
  onChangeMinor: (minor: number) => void
  /** Arrow step, in euros (default 1). */
  stepEuros?: number
}

const minorToText = (minor: number) => (minor ? String(minor / 100) : '')
const textToMinor = (text: string) =>
  text === '' ? 0 : Math.round(parseFloat(text) * 100)

export function MoneyField({
  valueMinor,
  onChangeMinor,
  stepEuros = 1,
  InputProps,
  inputProps,
  ...rest
}: MoneyFieldProps) {
  // Local text buffer so typing decimals isn't clobbered by the round-trip.
  const [text, setText] = useState(() => minorToText(valueMinor))

  useEffect(() => {
    // Re-sync when the value changes externally (reset, line add/remove, etc.).
    if (textToMinor(text) !== valueMinor) setText(minorToText(valueMinor))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valueMinor])

  return (
    <TextField
      {...rest}
      type="number"
      value={text}
      onChange={(e) => {
        setText(e.target.value)
        onChangeMinor(textToMinor(e.target.value))
      }}
      inputProps={{ min: 0, step: stepEuros, ...(inputProps ?? {}) }}
      InputProps={{
        endAdornment: <InputAdornment position="end">€</InputAdornment>,
        ...(InputProps ?? {}),
      }}
    />
  )
}
