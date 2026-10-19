import { useState } from 'react'
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField } from '@mui/material'

interface Props {
  title: string
  text: string
  confirmLabel: string
  onConfirm: (note: string | undefined) => Promise<void>
  onClose: () => void
}

// confirms a review action, with an optional reason recorded in the impact's history
export default function ReasonDialog({ title, text, confirmLabel, onConfirm, onClose }: Props) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    setBusy(true)
    try {
      await onConfirm(note.trim() || undefined)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>{text}</DialogContentText>
        <TextField
          autoFocus fullWidth label="Reason (optional)" value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="contained" onClick={handleConfirm} disabled={busy}>{confirmLabel}</Button>
      </DialogActions>
    </Dialog>
  )
}
