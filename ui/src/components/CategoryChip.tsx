import { Chip, Tooltip } from '@mui/material'
import { CATEGORY_LABELS } from './impactFields'

const colors: Record<string, { bg: string; color: string }> = {
  MV: { bg: '#b71c1c', color: '#fff' },
  MR: { bg: '#e53935', color: '#fff' },
  MO: { bg: '#f57c00', color: '#fff' },
  MN: { bg: '#fdd835', color: '#212121' },
  MC: { bg: '#388e3c', color: '#fff' },
  DD: { bg: '#757575', color: '#fff' },
}

// short: the code alone, with the full name on hover, for compact table cells
export function CategoryChip({ category, short = false }: { category: string; short?: boolean }) {
  const cfg = colors[category] ?? { bg: '#9e9e9e', color: '#fff' }
  const label = CATEGORY_LABELS[category] ?? category
  const chip = (
    <Chip
      label={short ? category : label}
      size="small"
      sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 600, whiteSpace: 'nowrap' }}
    />
  )
  return short ? <Tooltip title={label}>{chip}</Tooltip> : chip
}
