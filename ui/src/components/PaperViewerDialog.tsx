import { useEffect, useState } from 'react'
import {
  Box, CircularProgress, Dialog, DialogContent, DialogTitle,
  IconButton, Typography,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'

interface Props {
  paperId: string
  filename: string
  onClose: () => void
}

export default function PaperViewerDialog({ paperId, filename, onClose }: Props) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.papers.content(paperId)
      .then((r) => setContent(r.content))
      .catch((e) => setError(String(e)))
  }, [paperId])

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth scroll="paper">
      <DialogTitle sx={{ pr: 6 }}>
        {filename}
        <IconButton
          onClick={onClose}
          size="small"
          sx={{ position: 'absolute', right: 12, top: 12 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {error ? (
          <Typography color="error">{error}</Typography>
        ) : content === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box
            sx={{
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
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  )
}
