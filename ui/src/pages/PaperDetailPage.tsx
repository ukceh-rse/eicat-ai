import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import {
  Box, Breadcrumbs, CircularProgress, IconButton, Link, Paper, Tooltip, Typography,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'
import { usePapersStore } from '../store/papersStore'
import { PaperStatusChip } from '../components/StatusChips'

export default function PaperDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { papers, fetch } = usePapersStore()
  const [content, setContent] = useState<string | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)

  useEffect(() => { fetch() }, [fetch])

  const paper = papers.find((p) => p.id === id)

  useEffect(() => {
    if (!id || paper?.status !== 'ready') return
    api.papers.content(id)
      .then((r) => setContent(r.content))
      .catch((e) => setContentError(String(e)))
  }, [id, paper?.status])

  if (!paper && papers.length > 0) {
    return <Typography color="text.secondary">Paper not found.</Typography>
  }

  if (!paper) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
  }

  return (
    <Box>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          underline="hover"
          color="inherit"
          onClick={() => navigate('/papers')}
          sx={{ background: 'none', border: 'none', cursor: 'pointer', p: 0, font: 'inherit' }}
        >
          Papers
        </Link>
        <Typography color="text.primary">{paper.filename}</Typography>
      </Breadcrumbs>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>{paper.filename}</Typography>
          <PaperStatusChip status={paper.status} />
        </Box>
        <Tooltip title="Download PDF">
          <IconButton component="a" href={api.papers.download(paper.id)} download={paper.filename}>
            <DownloadIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Paper variant="outlined" sx={{ p: 3 }}>
        {paper.status !== 'ready' ? (
          <Typography color="text.secondary">
            {paper.status === 'converting' ? 'Paper is still being processed…' : 'Paper could not be processed.'}
          </Typography>
        ) : contentError ? (
          <Typography color="error">{contentError}</Typography>
        ) : content === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{
            '& h1, & h2, & h3, & h4': { mt: 2, mb: 1, fontWeight: 600 },
            '& h1': { fontSize: '1.5rem' },
            '& h2': { fontSize: '1.25rem' },
            '& h3': { fontSize: '1.1rem' },
            '& p': { mb: 1.5, lineHeight: 1.7 },
            '& ul, & ol': { pl: 3, mb: 1.5 },
            '& li': { mb: 0.5 },
            '& table': { borderCollapse: 'collapse', width: '100%', mb: 2 },
            '& th, & td': { border: '1px solid', borderColor: 'divider', p: '6px 12px' },
            '& th': { bgcolor: 'action.hover', fontWeight: 600 },
            '& blockquote': {
              borderLeft: '4px solid', borderColor: 'divider',
              pl: 2, ml: 0, color: 'text.secondary',
            },
            '& code': {
              fontFamily: 'monospace', fontSize: '0.875em',
              bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5,
            },
            '& pre': {
              bgcolor: 'action.hover', p: 2, borderRadius: 1,
              overflow: 'auto', mb: 2,
              '& code': { bgcolor: 'transparent', p: 0 },
            },
            '& hr': { border: 'none', borderTop: '1px solid', borderColor: 'divider', my: 2 },
          }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </Box>
        )}
      </Paper>
    </Box>
  )
}
