import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import {
  Alert, Box, Breadcrumbs, Button, Chip, CircularProgress,
  Divider, IconButton, Link, List, ListItem, ListItemText,
  Paper, Tooltip, Typography,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import DeleteIcon from '@mui/icons-material/Delete'
import AddIcon from '@mui/icons-material/Add'
import CancelIcon from '@mui/icons-material/Cancel'
import { useAnalysesStore } from '../store/analysesStore'
import { usePapersStore } from '../store/papersStore'
import { AnalysisStatusChip } from '../components/StatusChips'
import AddPapersDialog from '../components/AddPapersDialog'
import ImpactsPanel from '../components/ImpactsPanel'

export default function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { analyses, fetch, remove, removePaper, run, refresh } = useAnalysesStore()
  const { papers, fetch: fetchPapers } = usePapersStore()
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [fetched, setFetched] = useState(false)

  useEffect(() => {
    Promise.all([fetch(), fetchPapers()]).then(() => setFetched(true))
  }, [fetch, fetchPapers])

  const analysis = analyses.find((a) => a.id === id)

  useEffect(() => {
    if (analysis?.status !== 'running') return
    const timer = setInterval(() => refresh(id!), 5000)
    return () => clearInterval(timer)
  }, [analysis?.status, id, refresh])

  if (!fetched) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
  }
  if (!analysis) {
    return <Typography color="text.secondary">Analysis not found.</Typography>
  }

  const analysisPapers = papers.filter((p) => analysis.paper_ids.includes(p.id))
  const canRun = analysis.status !== 'running'

  const handleRun = async () => {
    setActionError(null)
    try { await run(id!) } catch (e) { setActionError(String(e)) }
  }

  const handleDelete = async () => {
    await remove(id!)
    navigate('/analyses')
  }

  return (
    <Box>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          underline="hover"
          color="inherit"
          onClick={() => navigate('/analyses')}
          sx={{ background: 'none', border: 'none', cursor: 'pointer', p: 0, font: 'inherit' }}
        >
          Analyses
        </Link>
        <Typography color="text.primary" sx={{ fontStyle: 'italic' }}>
          {analysis.species.scientific_name}
        </Typography>
      </Breadcrumbs>

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 600, fontStyle: 'italic' }}>
            {analysis.species.scientific_name}
          </Typography>
          {analysis.species.vernacular_names.length > 0 && (
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.75, flexWrap: 'wrap' }}>
              {analysis.species.vernacular_names.map((n) => (
                <Chip key={n} label={n} size="small" variant="outlined" />
              ))}
            </Box>
          )}
          <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <AnalysisStatusChip status={analysis.status} />
            {analysis.status === 'running' && <CircularProgress size={16} />}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Button
            variant="contained"
            startIcon={
              analysis.status === 'running'
                ? <CircularProgress size={16} color="inherit" />
                : <PlayArrowIcon />
            }
            onClick={handleRun}
            disabled={!canRun || analysis.paper_ids.length === 0}
          >
            {analysis.status === 'running' ? 'Running…' : 'Run Analysis'}
          </Button>
          <Tooltip title="Delete analysis">
            <IconButton onClick={handleDelete} color="error">
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {actionError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}
      {analysis.error && (
        <Alert severity="error" sx={{ mb: 2 }}>{analysis.error}</Alert>
      )}

      {/* Papers */}
      <Paper variant="outlined" sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>Papers</Typography>
          <Button size="small" startIcon={<AddIcon />} onClick={() => setAddDialogOpen(true)}>
            Add Papers
          </Button>
        </Box>
        {analysisPapers.length === 0 ? (
          <Typography color="text.secondary">No papers added yet.</Typography>
        ) : (
          <List dense disablePadding>
            {analysisPapers.map((p, i) => (
              <Box key={p.id}>
                {i > 0 && <Divider />}
                <ListItem
                  secondaryAction={
                    <Tooltip title="Remove from analysis">
                      <IconButton edge="end" size="small" onClick={() => removePaper(id!, p.id)}>
                        <CancelIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  }
                >
                  <ListItemText primary={p.filename} />
                </ListItem>
              </Box>
            ))}
          </List>
        )}
      </Paper>

      {/* Results */}
      {analysis.status === 'completed' && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>Results</Typography>
          <ImpactsPanel results={analysis.results} papers={papers} />
        </Paper>
      )}

      <AddPapersDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        analysisId={id!}
        existingPaperIds={analysis.paper_ids}
      />
    </Box>
  )
}
