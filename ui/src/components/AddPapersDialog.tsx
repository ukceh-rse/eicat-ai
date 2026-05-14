import { useState } from 'react'
import {
  Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Typography,
} from '@mui/material'
import { usePapersStore } from '../store/papersStore'
import { useAnalysesStore } from '../store/analysesStore'

interface Props {
  open: boolean
  onClose: () => void
  analysisId: string
  existingPaperIds: string[]
}

export default function AddPapersDialog({ open, onClose, analysisId, existingPaperIds }: Props) {
  const papers = usePapersStore((s) => s.papers)
  const addPaper = useAnalysesStore((s) => s.addPaper)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [adding, setAdding] = useState(false)

  const available = papers.filter((p) => p.status === 'ready' && !existingPaperIds.includes(p.id))

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const handleAdd = async () => {
    setAdding(true)
    for (const id of selected) await addPaper(analysisId, id)
    setAdding(false)
    setSelected(new Set())
    onClose()
  }

  const handleClose = () => {
    setSelected(new Set())
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add Papers</DialogTitle>
      <DialogContent>
        {available.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 2 }}>
            No ready papers available to add.
          </Typography>
        ) : (
          <List dense disablePadding>
            {available.map((p) => (
              <ListItem key={p.id} disablePadding>
                <ListItemButton onClick={() => toggle(p.id)}>
                  <ListItemIcon>
                    <Checkbox edge="start" checked={selected.has(p.id)} disableRipple />
                  </ListItemIcon>
                  <ListItemText primary={p.filename} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleAdd}
          disabled={selected.size === 0 || adding}
          startIcon={adding ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Add{selected.size > 0 ? ` (${selected.size})` : ''}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
