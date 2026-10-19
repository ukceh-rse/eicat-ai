import { useEffect, useState } from 'react'
import {
  Box, Chip, CircularProgress, Divider, Drawer, IconButton, Typography,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import { api } from '../api/client'
import { FIELD_LABELS, formatValue } from './impactFields'
import type { AuditEvent } from '../types'

interface Props {
  analysisId: string
  impactId: string
  title: string
  onClose: () => void
}

const ACTOR_COLORS = { human: 'primary', ai: 'secondary', system: 'default' } as const

const truncate = (text: string) => (text.length > 200 ? `${text.slice(0, 200)}…` : text)

export default function ImpactHistoryDrawer({ analysisId, impactId, title, onClose }: Props) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.analyses.audit(analysisId, impactId)
      .then(setEvents)
      .catch((e) => setError(String(e)))
  }, [analysisId, impactId])

  return (
    <Drawer anchor="right" open onClose={onClose} slotProps={{ paper: { sx: { width: { xs: '100%', sm: 440 } } } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>History</Typography>
          <Typography variant="body2" color="text.secondary">{title}</Typography>
        </Box>
        <IconButton onClick={onClose} size="small"><CloseIcon /></IconButton>
      </Box>
      <Divider />
      <Box sx={{ p: 2 }}>
        {error ? (
          <Typography color="error">{error}</Typography>
        ) : events === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress /></Box>
        ) : events.length === 0 ? (
          <Typography color="text.secondary">No recorded events.</Typography>
        ) : events.map((e) => (
          <Box key={e._id} data-testid="history-event" sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle2">{e.action.replace('_', ' ')}</Typography>
              <Chip label={e.actor.kind} size="small" color={ACTOR_COLORS[e.actor.kind]} variant="outlined" />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                {new Date(e.at.endsWith('Z') ? e.at : `${e.at}Z`).toLocaleString()}
              </Typography>
            </Box>
            {e.changes.filter((c) => c.field !== 'held_by').map((c) => (
              <Typography key={c.field} variant="body2" sx={{ mt: 0.5 }}>
                <strong>{FIELD_LABELS[c.field] ?? c.field}:</strong>{' '}
                <Box component="span" sx={{ color: 'text.secondary', textDecoration: 'line-through' }}>
                  {truncate(formatValue(c.old))}
                </Box>
                {' → '}
                {truncate(formatValue(c.new))}
              </Typography>
            ))}
            {e.note && (
              <Typography variant="body2" sx={{ mt: 0.5, fontStyle: 'italic' }}>Reason: {e.note}</Typography>
            )}
          </Box>
        ))}
      </Box>
    </Drawer>
  )
}
