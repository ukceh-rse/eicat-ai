import { useState } from 'react'
import {
  Box, Button, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, IconButton, TextField, Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import CloseIcon from '@mui/icons-material/Close'
import { useAnalysesStore } from '../store/analysesStore'
import { useNavigate } from 'react-router'

interface Props {
  open: boolean
  onClose: () => void
}

export default function CreateAnalysisDialog({ open, onClose }: Props) {
  const navigate = useNavigate()
  const create = useAnalysesStore((s) => s.create)
  const [scientificName, setScientificName] = useState('')
  const [otherNames, setOtherNames] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateName = (i: number, value: string) =>
    setOtherNames((names) => names.map((n, idx) => (idx === i ? value : n)))

  const removeName = (i: number) =>
    setOtherNames((names) => names.filter((_, idx) => idx !== i))

  const handleSubmit = async () => {
    if (!scientificName.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const vernacular_names = [...new Set(otherNames.map((n) => n.trim()).filter(Boolean))]
      const analysis = await create({ scientific_name: scientificName.trim(), vernacular_names })
      handleClose()
      navigate(`/analyses/${analysis.id}`)
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    setScientificName('')
    setOtherNames([])
    setError(null)
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>New Analysis</DialogTitle>
      <DialogContent>
        <TextField
          label="Scientific Name"
          value={scientificName}
          onChange={(e) => setScientificName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
          fullWidth
          required
          autoFocus
          margin="normal"
        />

        <Box sx={{ mt: 2, mb: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="body2" color="text.secondary">
            Other names (vernacular, common etc.)
          </Typography>
          <IconButton size="small" onClick={() => setOtherNames((n) => [...n, ''])}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Box>

        {otherNames.map((name, i) => (
          <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <TextField
              value={name}
              onChange={(e) => updateName(i, e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
              size="small"
              fullWidth
              autoFocus={name === ''}
              placeholder={`Name ${i + 1}`}
            />
            <IconButton size="small" onClick={() => removeName(i)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        ))}

        {error && (
          <Box sx={{ mt: 2, color: 'error.main', fontSize: 14 }}>{error}</Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!scientificName.trim() || submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Create
        </Button>
      </DialogActions>
    </Dialog>
  )
}
