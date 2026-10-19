import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Alert, Box, Breadcrumbs, Button, CircularProgress, Link, TextField, Typography } from '@mui/material'
import PaperLayout from '../components/PaperLayout'
import PaperText from '../components/PaperText'
import SpanList from '../components/SpanList'
import { anchored } from '../components/impactFields'
import { useAnalysesStore } from '../store/analysesStore'
import { isLocked, type EvidenceSpan } from '../types'
import { useAnalysis } from './useAnalysis'

// an impact's evidence in the paper: its spans highlighted, and reselected by selecting paper text
export default function EvidencePage() {
  const { id, impactId } = useParams<{ id: string; impactId: string }>()
  const navigate = useNavigate()
  const { analysis, papers, loading, error: loadError, retry } = useAnalysis(id)
  const { patchImpact } = useAnalysesStore()
  const impact = analysis?.impacts.find((i) => i.id === impactId)
  const [spans, setSpans] = useState<EvidenceSpan[] | null>(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
  if (loadError) {
    return <Alert severity="error" action={<Button color="inherit" onClick={retry}>Retry</Button>}>Could not load the analysis: {loadError}</Alert>
  }
  if (!analysis || !impact) return <Typography color="text.secondary">Impact not found.</Typography>

  const current = spans ?? impact.evidence
  // saving approximate spans unchanged accepts them as the evidence
  const changed = (spans !== null && JSON.stringify(spans) !== JSON.stringify(impact.evidence))
    || current.some((s) => s.approximate)
  const unanchored = current.some((s) => s.start === null)
  const locked = isLocked(analysis, impact.paper_id)
  const readOnly = locked || impact.state !== 'active'
  const filename = papers.find((p) => p.id === impact.paper_id)?.filename ?? impact.paper_id
  const back = () => navigate(`/analyses/${analysis.id}?impact=${impact.id}`)
  // the AI's own wording, shown where the spans stand in for it: closest passages, or sentences not found
  const aiWording = impact.ai && current.some((s) => s.start === null || s.approximate) ? impact.ai.evidence : null

  const add = (span: EvidenceSpan) => setSpans((c) => {
    const base = c ?? impact.evidence
    if (base.some((s) => s.start === span.start && s.end === span.end)) return base
    return [...base, span].sort((a, b) => (a.start ?? Infinity) - (b.start ?? Infinity))
  })

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await patchImpact(analysis.id, impact.id, { evidence: current, note: note.trim() || undefined })
      back()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setSaving(false)
    }
  }

  return (
    <PaperLayout
      header={
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link component="button" underline="hover" color="inherit" onClick={() => navigate('/analyses')}>Analyses</Link>
          <Link component="button" underline="hover" color="inherit" sx={{ fontStyle: 'italic' }} onClick={back}>
            {analysis.species.scientific_name}
          </Link>
          <Typography color="text.primary">
            Evidence: {impact.current.mechanism} ({impact.current.category}), {filename}
          </Typography>
        </Breadcrumbs>
      }
      paper={<PaperText paperId={impact.paper_id} highlights={anchored(current)} onSelect={readOnly ? undefined : add} />}
      panel={
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Evidence ({current.length})</Typography>
          {readOnly && (
            <Alert severity="info">
              {locked ? 'Review of this paper is paused while it runs.' : 'Only active impacts can be edited.'}
            </Alert>
          )}
          <SpanList
            spans={current}
            onRemove={readOnly ? undefined : (s) => setSpans(current.filter((x) => x !== s))}
          />
          {aiWording && (
            <Box>
              <Typography variant="caption" color="text.secondary">The AI's evidence</Typography>
              <Typography variant="body2" sx={{ fontStyle: 'italic', whiteSpace: 'pre-wrap' }}>{aiWording}</Typography>
            </Box>
          )}
          {!readOnly && unanchored && (
            <Alert severity="warning">
              Remove passages not found in the paper, and select their evidence in the paper instead, before saving.
            </Alert>
          )}
          {!readOnly && (
            <TextField
              size="small" label="Reason (optional)" value={note} onChange={(e) => setNote(e.target.value)}
              helperText="Recorded with this change in the impact's history"
            />
          )}
          {error && <Alert severity="error">{error}</Alert>}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button onClick={back}>{readOnly ? 'Back' : 'Cancel'}</Button>
            {!readOnly && (
              <Button
                variant="contained" onClick={save}
                disabled={saving || !changed || current.length === 0 || unanchored}
              >
                Save
              </Button>
            )}
          </Box>
        </Box>
      }
    />
  )
}
