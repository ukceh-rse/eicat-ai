import { useEffect, useState } from 'react'
import {
  Box, Button, CircularProgress, Paper,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import { useNavigate } from 'react-router'
import { useAnalysesStore } from '../store/analysesStore'
import { AnalysisStatusChip } from '../components/StatusChips'
import CreateAnalysisDialog from '../components/CreateAnalysisDialog'

export default function AnalysesPage() {
  const { analyses, loading, fetch } = useAnalysesStore()
  const [dialogOpen, setDialogOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { fetch() }, [fetch])

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>Analyses</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          New Analysis
        </Button>
      </Box>

      {loading && !analyses.length ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Species</TableCell>
                <TableCell>Common Names</TableCell>
                <TableCell>Papers</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Created</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {analyses.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} align="center" sx={{ py: 6, color: 'text.disabled' }}>
                    No analyses yet
                  </TableCell>
                </TableRow>
              ) : analyses.map((a) => (
                <TableRow
                  key={a.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/analyses/${a.id}`)}
                >
                  <TableCell>
                    <Typography sx={{ fontStyle: 'italic' }}>{a.species.scientific_name}</Typography>
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>
                    {a.species.vernacular_names.join(', ') || '—'}
                  </TableCell>
                  <TableCell>{a.paper_ids.length}</TableCell>
                  <TableCell><AnalysisStatusChip status={a.status} /></TableCell>
                  <TableCell>{new Date(a.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <CreateAnalysisDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </Box>
  )
}
