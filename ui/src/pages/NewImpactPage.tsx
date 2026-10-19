import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Alert, Box, Breadcrumbs, Button, CircularProgress, Link, TextField, Typography } from '@mui/material'
import PaperLayout from '../components/PaperLayout'
import PaperText from '../components/PaperText'
import SpanList from '../components/SpanList'
import {
  CategorySelect, ConfidenceSelect, MechanismSelect, ReversibilitySelect, SpeciesInput,
} from '../components/ImpactInputs'
import { needsReversibility, type AnchoredSpan } from '../components/impactFields'
import { useAnalysesStore } from '../store/analysesStore'
import type { Impact } from '../types'
import { useAnalysis } from './useAnalysis'

type Form = Omit<Impact, 'evidence'>

// a reviewer's own impact on a paper: its evidence selected in the paper, its fields in the panel beside it
export default function NewImpactPage() {
  const { id, paperId } = useParams<{ id: string; paperId: string }>()
  const navigate = useNavigate()
  const { analysis, papers, loading, error: loadError, retry } = useAnalysis(id)
  const { createImpact } = useAnalysesStore()
  const [form, setForm] = useState<Form | null>(null)
  const [spans, setSpans] = useState<AnchoredSpan[]>([])
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
  if (loadError) {
    return <Alert severity="error" action={<Button color="inherit" onClick={retry}>Retry</Button>}>Could not load the analysis: {loadError}</Alert>
  }
  if (!analysis || !paperId || !analysis.paper_ids.includes(paperId)) {
    return <Typography color="text.secondary">Paper not found in this analysis.</Typography>
  }

  const fields: Form = form ?? {
    alien_species: analysis.species.scientific_name, mechanism: '', category: '', reversibility: null,
    confidence: null, justification: '', impacted_species: [],
  }
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...fields, [key]: value })
  const reversibilityMissing = needsReversibility(fields.category) && !fields.reversibility
  const readOnly = analysis.status === 'running'
  const filename = papers.find((p) => p.id === paperId)?.filename ?? paperId
  const back = (impactId?: string) => navigate(`/analyses/${analysis.id}${impactId ? `?impact=${impactId}` : ''}`)

  const add = (span: AnchoredSpan) => setSpans((c) => c.some((s) => s.start === span.start && s.end === span.end)
    ? c
    : [...c, span].sort((a, b) => a.start - b.start))

  const save = async () => {
    setSaving(true)
    setError(null)
    const before = new Set(analysis.impacts.map((i) => i.id))
    try {
      const values = { ...fields, reversibility: needsReversibility(fields.category) ? fields.reversibility : null }
      await createImpact(analysis.id, paperId, values, spans, note.trim() || undefined)
      // the response replaces the analysis in the store; the new impact is the one not there before
      const updated = useAnalysesStore.getState().analyses.find((a) => a.id === analysis.id)
      back(updated?.impacts.find((i) => !before.has(i.id))?.id)
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
          <Link component="button" underline="hover" color="inherit" sx={{ fontStyle: 'italic' }} onClick={() => back()}>
            {analysis.species.scientific_name}
          </Link>
          <Typography color="text.primary">New impact: {filename}</Typography>
        </Breadcrumbs>
      }
      paper={<PaperText paperId={paperId} highlights={spans} onSelect={readOnly ? undefined : add} />}
      panel={
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>New impact</Typography>
          {readOnly && <Alert severity="info">Review is paused while the analysis runs.</Alert>}
          <TextField
            size="small" label="Alien species" required value={fields.alien_species}
            onChange={(e) => set('alien_species', e.target.value)}
          />
          <MechanismSelect size="small" label="Mechanism" required value={fields.mechanism} onChange={(v) => set('mechanism', v)} />
          <CategorySelect size="small" label="Category" required value={fields.category} onChange={(v) => set('category', v)} />
          {needsReversibility(fields.category) && (
            <ReversibilitySelect
              size="small" label="Reversibility" required value={fields.reversibility}
              onChange={(v) => set('reversibility', v)}
              error={reversibilityMissing} helperText={reversibilityMissing ? 'Required for MR and MV' : undefined}
            />
          )}
          <ConfidenceSelect size="small" label="Confidence" value={fields.confidence} onChange={(v) => set('confidence', v)} />
          <SpeciesInput
            size="small" label="Impacted species" helperText="Press Enter after each name"
            value={fields.impacted_species} onChange={(v) => set('impacted_species', v)}
          />
          <TextField
            size="small" label="Justification" multiline minRows={2} value={fields.justification}
            onChange={(e) => set('justification', e.target.value)}
          />
          <Typography variant="subtitle2">Evidence ({spans.length})</Typography>
          <SpanList spans={spans} onRemove={(s) => setSpans((c) => c.filter((x) => x !== s))} />
          <TextField
            size="small" label="Reason (optional)" value={note} onChange={(e) => setNote(e.target.value)}
            helperText="Recorded in the impact's history"
          />
          {error && <Alert severity="error">{error}</Alert>}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button onClick={() => back()}>Cancel</Button>
            <Button
              variant="contained" onClick={save}
              disabled={
                readOnly || saving || reversibilityMissing || !fields.alien_species.trim() || !fields.mechanism
                || !fields.category || spans.length === 0
              }
            >
              Save
            </Button>
          </Box>
        </Box>
      }
    />
  )
}
