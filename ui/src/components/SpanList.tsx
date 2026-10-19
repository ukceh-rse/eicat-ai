import { Box, IconButton, Tooltip, Typography } from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import type { EvidenceSpan } from '../types'
import { readable } from './impactFields'

export const UNANCHORED = 'Not found in the paper: this is the AI\'s text'
export const APPROXIMATE = 'The AI didn\'t quote this word for word; this is the closest passage in the paper'

// an evidence span's status icon: not found in the paper, or the closest passage to the AI's evidence; detail is
// added to the tooltip
export function SpanStatus({ span, detail }: { span: EvidenceSpan; detail?: string }) {
  const title = (text: string) => <Box sx={{ whiteSpace: 'pre-wrap' }}>{detail ? `${text}\n\n${detail}` : text}</Box>
  if (span.start === null) {
    return <Tooltip title={title(UNANCHORED)}><WarningAmberIcon fontSize="small" color="warning" aria-label={UNANCHORED} /></Tooltip>
  }
  if (span.approximate) {
    return <Tooltip title={title(APPROXIMATE)}><InfoOutlinedIcon fontSize="small" color="info" aria-label={APPROXIMATE} /></Tooltip>
  }
  return null
}

interface Props {
  spans: EvidenceSpan[]
  onRemove?: (span: EvidenceSpan) => void
}

// an impact's evidence spans in paper order, each with its status
export default function SpanList({ spans, onRemove }: Props) {
  if (spans.length === 0) {
    return <Typography variant="body2" color="text.secondary">No passages selected yet. Select text in the paper to add one.</Typography>
  }
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {spans.map((s, i) => (
        <Box
          key={s.start === null ? `u${i}` : `${s.start}-${s.end}`}
          data-testid="evidence-span"
          sx={{
            display: 'flex', gap: 1, alignItems: 'flex-start', borderLeft: '3px solid', pl: 1,
            borderColor: s.start === null ? 'warning.main' : s.approximate ? 'info.main' : '#fff176',
          }}
        >
          <SpanStatus span={s} />
          <Typography variant="body2" sx={{ flex: 1, whiteSpace: 'pre-wrap' }}>
            {readable(s.text).length > 300 ? `${readable(s.text).slice(0, 300)}…` : readable(s.text)}
          </Typography>
          {onRemove && (
            <IconButton size="small" aria-label="Remove passage" onClick={() => onRemove(s)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
        </Box>
      ))}
    </Box>
  )
}
