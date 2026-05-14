import { Chip } from '@mui/material'

const config: Record<string, { label: string; bg: string; color: string }> = {
  MV: { label: 'MV – Massive',        bg: '#b71c1c', color: '#fff' },
  MR: { label: 'MR – Major',          bg: '#e53935', color: '#fff' },
  MO: { label: 'MO – Moderate',       bg: '#f57c00', color: '#fff' },
  MN: { label: 'MN – Minor',          bg: '#fdd835', color: '#212121' },
  MC: { label: 'MC – Min. Concern',   bg: '#388e3c', color: '#fff' },
  DD: { label: 'DD – Data Deficient', bg: '#757575', color: '#fff' },
}

export function CategoryChip({ category }: { category: string }) {
  const cfg = config[category] ?? { label: category, bg: '#9e9e9e', color: '#fff' }
  return (
    <Chip
      label={cfg.label}
      size="small"
      sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 600, whiteSpace: 'nowrap' }}
    />
  )
}
