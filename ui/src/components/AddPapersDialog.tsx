import { useState } from 'react'
import {
  Button, Checkbox, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material'
import { usePapersStore } from '../store/papersStore'
import { useAnalysesStore } from '../store/analysesStore'
import { PaperStatusChip } from './StatusChips'

interface Props {
  open: boolean
  onClose: () => void
  analysisId: string
  existingPaperIds: string[]
}

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1_048_576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1_048_576).toFixed(1)} MB`
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
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Add Papers</DialogTitle>
      <DialogContent sx={{ px: 3, pt: 1, pb: 2 }}>
        {available.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 2 }}>
            No ready papers available to add.
          </Typography>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" />
                  <TableCell>Filename</TableCell>
                  <TableCell>Size</TableCell>
                  <TableCell>Uploaded</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {available.map((p) => (
                  <TableRow
                    key={p.id}
                    hover
                    selected={selected.has(p.id)}
                    onClick={() => toggle(p.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell padding="checkbox">
                      <Checkbox checked={selected.has(p.id)} size="small" disableRipple />
                    </TableCell>
                    <TableCell>{p.filename}</TableCell>
                    <TableCell>{formatBytes(p.size)}</TableCell>
                    <TableCell>{new Date(p.uploaded_at).toLocaleDateString()}</TableCell>
                    <TableCell><PaperStatusChip status={p.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
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
