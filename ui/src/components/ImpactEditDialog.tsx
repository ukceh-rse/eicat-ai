import { useState } from 'react'
import {
  Alert, Autocomplete, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  MenuItem, TextField, Typography,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import PaperViewerDialog from './PaperViewerDialog'
import { CATEGORIES, CONFIDENCES, MECHANISMS, REVERSIBILITIES, needsReversibility } from './impactFields'
import type { EvidenceSpan, Impact, ImpactFields } from '../types'

interface Props {
  title: string
  paperId: string
  filename: string
  initial: Impact
  evidence: EvidenceSpan[]
  // a new impact is saved with all its fields; an edit with only the fields that changed, and the evidence if it did
  isNew?: boolean
  onSave: (fields: ImpactFields, evidence: EvidenceSpan[] | undefined, note: string | undefined) => Promise<void>
  onClose: () => void
}

type Form = Omit<Impact, 'evidence'>

export default function ImpactEditDialog({
  title, paperId, filename, initial, evidence: initialEvidence, isNew = false, onSave, onClose,
}: Props) {
  const [form, setForm] = useState<Form>(() => ({
    alien_species: initial.alien_species,
    mechanism: initial.mechanism,
    category: initial.category,
    reversibility: initial.reversibility,
    confidence: initial.confidence,
    justification: initial.justification,
    impacted_species: initial.impacted_species,
  }))
  const [evidence, setEvidence] = useState(initialEvidence)
  const [note, setNote] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }))
  const reversibilityMissing = needsReversibility(form.category) && !form.reversibility
  const evidenceChanged = JSON.stringify(evidence) !== JSON.stringify(initialEvidence)
  const unanchored = evidence.filter((s) => s.start === null)

  const handleSave = async () => {
    const fields: ImpactFields = {}
    const next: Form = { ...form, reversibility: needsReversibility(form.category) ? form.reversibility : null }
    for (const key of Object.keys(next) as (keyof Form)[]) {
      if (isNew || JSON.stringify(next[key] ?? null) !== JSON.stringify(initial[key] ?? null)) {
        (fields as Record<string, unknown>)[key] = next[key]
      }
    }
    setSaving(true)
    setError(null)
    try {
      await onSave(fields, isNew || evidenceChanged ? evidence : undefined, note.trim() || undefined)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setSaving(false)
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Alien species"
            value={form.alien_species}
            onChange={(e) => set('alien_species', e.target.value)}
            required
          />
          <TextField select label="Mechanism" value={form.mechanism} onChange={(e) => set('mechanism', e.target.value)} required>
            {MECHANISMS.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
          </TextField>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              select fullWidth label="Category" value={form.category}
              onChange={(e) => set('category', e.target.value)} required
            >
              {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
            </TextField>
            {needsReversibility(form.category) && (
              <TextField
                select fullWidth required label="Reversibility" value={form.reversibility ?? ''}
                onChange={(e) => set('reversibility', e.target.value as Form['reversibility'])}
                error={reversibilityMissing}
                helperText={reversibilityMissing ? 'Required for MR and MV' : undefined}
              >
                {REVERSIBILITIES.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
              </TextField>
            )}
            <TextField
              select fullWidth label="Confidence" value={form.confidence ?? ''}
              onChange={(e) => set('confidence', e.target.value || null)}
            >
              <MenuItem value=""><em>None</em></MenuItem>
              {CONFIDENCES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
            </TextField>
          </Box>
          <Autocomplete
            multiple freeSolo options={[] as string[]}
            value={form.impacted_species}
            onChange={(_, value) => set('impacted_species', value)}
            renderInput={(params) => (
              <TextField {...params} label="Impacted species" helperText="Press Enter after each name" />
            )}
          />
          <TextField
            label="Justification" multiline minRows={2} value={form.justification}
            onChange={(e) => set('justification', e.target.value)}
          />
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="subtitle2">Evidence ({evidence.length})</Typography>
              <Button size="small" startIcon={<EditIcon />} onClick={() => setSelecting(true)}>Edit evidence</Button>
            </Box>
            {unanchored.length > 0 && (
              <Alert severity="warning" icon={<WarningAmberIcon fontSize="inherit" />} sx={{ mb: 1 }}>
                Some evidence could not be found in the paper. Reselect it with “Edit evidence”.
              </Alert>
            )}
            {evidence.map((s, i) => (
              <Typography
                key={i} variant="body2"
                sx={{ borderLeft: '3px solid', borderColor: s.start === null ? 'warning.main' : 'divider', pl: 1, mb: 0.5, whiteSpace: 'pre-wrap' }}
              >
                {s.text.length > 300 ? `${s.text.slice(0, 300)}…` : s.text}
              </Typography>
            ))}
          </Box>
          <TextField
            label="Reason (optional)" value={note} onChange={(e) => setNote(e.target.value)}
            helperText="Recorded with this change in the impact's history"
          />
          {error && <Alert severity="error">{error}</Alert>}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained" onClick={handleSave}
          disabled={
            saving || reversibilityMissing || !form.alien_species.trim() || !form.mechanism || !form.category
            || evidence.length === 0
          }
        >
          Save
        </Button>
      </DialogActions>
      {selecting && (
        <PaperViewerDialog
          paperId={paperId}
          filename={filename}
          onClose={() => setSelecting(false)}
          mode={{
            kind: 'select',
            spans: evidence,
            onConfirm: (spans) => {
              setEvidence(spans)
              setSelecting(false)
            },
          }}
        />
      )}
    </Dialog>
  )
}
