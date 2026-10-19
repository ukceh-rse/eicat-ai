import { Autocomplete, MenuItem, TextField, type TextFieldProps } from '@mui/material'
import { CATEGORIES, CATEGORY_LABELS, CONFIDENCES, MECHANISMS, REVERSIBILITIES } from './impactFields'
import type { Impact } from '../types'

// selects for impact fields, as form fields (with a label) or compact table cells (variant="standard")
type SelectProps<T> = Omit<TextFieldProps, 'value' | 'onChange' | 'select'> & { value: T; onChange: (value: T) => void }

export function CategorySelect({ value, onChange, ...props }: SelectProps<string>) {
  return (
    <TextField select value={value} onChange={(e) => onChange(e.target.value)} {...props}>
      {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{CATEGORY_LABELS[c]}</MenuItem>)}
    </TextField>
  )
}

export function MechanismSelect({ value, onChange, ...props }: SelectProps<string>) {
  return (
    <TextField select value={value} onChange={(e) => onChange(e.target.value)} {...props}>
      {MECHANISMS.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
    </TextField>
  )
}

export function ReversibilitySelect({ value, onChange, ...props }: SelectProps<Impact['reversibility']>) {
  return (
    <TextField
      select value={value ?? ''} onChange={(e) => onChange(e.target.value as Impact['reversibility'])} {...props}
    >
      {REVERSIBILITIES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
    </TextField>
  )
}

export function ConfidenceSelect({ value, onChange, ...props }: SelectProps<Impact['confidence']>) {
  return (
    <TextField select value={value ?? ''} onChange={(e) => onChange(e.target.value || null)} {...props}>
      <MenuItem value=""><em>None</em></MenuItem>
      {CONFIDENCES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
    </TextField>
  )
}

export function SpeciesInput({ value, onChange, ...props }: SelectProps<string[]>) {
  return (
    <Autocomplete
      multiple freeSolo options={[] as string[]} value={value} onChange={(_, v) => onChange(v)}
      size={props.size === 'small' ? 'small' : 'medium'} disabled={props.disabled}
      renderInput={(params) => <TextField {...params} {...props} />}
    />
  )
}
