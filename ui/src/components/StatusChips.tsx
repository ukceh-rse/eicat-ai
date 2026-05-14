import { Chip } from '@mui/material'
import type { AnalysisStatus, PaperStatus } from '../types'

const paperColor: Record<PaperStatus, 'warning' | 'success' | 'error'> = {
  converting: 'warning',
  ready: 'success',
  failed: 'error',
}

export function PaperStatusChip({ status }: { status: PaperStatus }) {
  return <Chip label={status} color={paperColor[status]} size="small" />
}

const analysisColor: Record<AnalysisStatus, 'default' | 'warning' | 'success' | 'error'> = {
  pending: 'default',
  running: 'warning',
  completed: 'success',
  failed: 'error',
}

export function AnalysisStatusChip({ status }: { status: AnalysisStatus }) {
  return <Chip label={status} color={analysisColor[status]} size="small" />
}
