import { useState } from 'react'
import {
  Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, TextField,
} from '@mui/material'
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
  const [vernacularInput, setVernacularInput] = useState('')
  const [vernacularNames, setVernacularNames] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const addVernacular = () => {
    const v = vernacularInput.trim()
    if (v && !vernacularNames.includes(v)) setVernacularNames((n) => [...n, v])
    setVernacularInput('')
  }

  const handleSubmit = async () => {
    if (!scientificName.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const analysis = await create({
        scientific_name: scientificName.trim(),
        vernacular_names: vernacularNames,
      })
      handleClose()
      navigate(`/analyses/${analysis.id}`)
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    setScientificName('')
    setVernacularNames([])
    setVernacularInput('')
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
          fullWidth
          required
          autoFocus
          margin="normal"
        />
        <TextField
          label="Vernacular / Common Name"
          value={vernacularInput}
          onChange={(e) => setVernacularInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addVernacular() } }}
          fullWidth
          margin="normal"
          helperText="Press Enter to add each name"
        />
        {vernacularNames.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            {vernacularNames.map((n) => (
              <Chip
                key={n}
                label={n}
                size="small"
                onDelete={() => setVernacularNames((v) => v.filter((x) => x !== n))}
              />
            ))}
          </Box>
        )}
        {error && (
          <Box sx={{ mt: 1, color: 'error.main', fontSize: 14 }}>{error}</Box>
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
