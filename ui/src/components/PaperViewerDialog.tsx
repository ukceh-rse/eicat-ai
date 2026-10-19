import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, List, ListItem, ListItemText, Paper, Popper, Typography,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import AddIcon from '@mui/icons-material/Add'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'
import type { EvidenceSpan } from '../types'
import { newRegistry, rehypeSourceOffsets, selectionToSpan, type SourceSpan } from './sourceOffsets'

// view: read the paper; highlight: show evidence spans in place; select: build a set of spans by selecting text
export type ViewerMode =
  | { kind: 'view' }
  | { kind: 'highlight'; spans: EvidenceSpan[] }
  | { kind: 'select'; spans?: EvidenceSpan[]; confirmLabel?: string; onConfirm: (spans: EvidenceSpan[]) => void }

interface Props {
  paperId: string
  filename: string
  onClose: () => void
  mode?: ViewerMode
}

type AnchoredSpan = EvidenceSpan & SourceSpan

const anchored = (spans: EvidenceSpan[]): AnchoredSpan[] =>
  spans.filter((s): s is AnchoredSpan => s.start !== null && s.end !== null)

// a selection's leading and trailing whitespace (e.g. the newline a triple-click takes) is not evidence
function trimmed(markdown: string, { start, end }: SourceSpan): AnchoredSpan | null {
  while (start < end && /\s/.test(markdown[start])) start++
  while (end > start && /\s/.test(markdown[end - 1])) end--
  return end > start ? { start, end, text: markdown.slice(start, end) } : null
}

export default function PaperViewerDialog({ paperId, filename, onClose, mode = { kind: 'view' } }: Props) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chosen, setChosen] = useState<AnchoredSpan[]>(mode.kind === 'select' ? anchored(mode.spans ?? []) : [])
  const [pending, setPending] = useState<{ span: AnchoredSpan; rect: DOMRect } | null>(null)
  const [selectError, setSelectError] = useState<string | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  const highlights: SourceSpan[] = mode.kind === 'highlight' ? anchored(mode.spans) : mode.kind === 'select' ? chosen : []
  const unanchored = mode.kind === 'highlight' ? mode.spans.filter((s) => s.start === null) : []

  const highlightKey = JSON.stringify(highlights)
  const { registry, rendered } = useMemo(() => {
    const registry = newRegistry()
    const rendered = content === null ? null : (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSourceOffsets, { markdown: content, registry, highlights: JSON.parse(highlightKey) }]]}
      >
        {content}
      </ReactMarkdown>
    )
    return { registry, rendered }
  }, [content, highlightKey])

  useEffect(() => {
    api.papers.content(paperId)
      .then((r) => setContent(r.content))
      .catch((e) => setError(String(e)))
  }, [paperId])

  // open at the evidence: scroll the first highlighted passage into view once the paper has rendered
  const scrolled = useRef(false)
  useEffect(() => {
    if (scrolled.current || !rendered || mode.kind === 'view') return
    bodyRef.current?.querySelector('mark')?.scrollIntoView({ block: 'center' })
    scrolled.current = true
  }, [rendered, mode.kind])

  const handleMouseUp = () => {
    if (mode.kind !== 'select' || content === null || !bodyRef.current) return
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed) {
      setPending(null)
      return
    }
    const source = selectionToSpan(content, registry, bodyRef.current)
    const span = source && trimmed(content, source)
    if (!span) {
      setPending(null)
      setSelectError('This selection could not be matched to the paper text; try selecting a slightly different passage.')
      return
    }
    setSelectError(null)
    setPending({ span, rect: selection.getRangeAt(0).getBoundingClientRect() })
  }

  const addPending = () => {
    if (!pending) return
    const { span } = pending
    setChosen((c) => c.some((s) => s.start === span.start && s.end === span.end)
      ? c
      : [...c, span].sort((a, b) => a.start - b.start))
    setPending(null)
    window.getSelection()?.removeAllRanges()
  }

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth scroll="paper">
      <DialogTitle sx={{ pr: 6 }}>
        {filename}
        {mode.kind === 'select' && (
          <Typography variant="body2" color="text.secondary">
            Select passages in the paper to use as evidence.
          </Typography>
        )}
        <IconButton
          onClick={onClose}
          size="small"
          sx={{ position: 'absolute', right: 12, top: 12 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {unanchored.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {unanchored.length === 1 ? 'This evidence passage' : `${unanchored.length} evidence passages`} could
            not be found in the paper:
            {unanchored.map((s, i) => (
              <Typography key={i} variant="body2" sx={{ fontStyle: 'italic', mt: 0.5 }}>“{s.text}”</Typography>
            ))}
          </Alert>
        )}
        {error ? (
          <Typography color="error">{error}</Typography>
        ) : content === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box
            ref={bodyRef}
            onMouseUp={handleMouseUp}
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
              '& mark': { bgcolor: '#fff176', color: 'inherit', borderRadius: 0.5 },
            }}
          >
            {rendered}
          </Box>
        )}
      </DialogContent>
      {mode.kind === 'select' && (
        <DialogActions sx={{ flexDirection: 'column', alignItems: 'stretch', gap: 1, px: 3, py: 2 }}>
          {selectError && <Alert severity="warning" onClose={() => setSelectError(null)}>{selectError}</Alert>}
          <Typography variant="subtitle2">Evidence ({chosen.length})</Typography>
          {chosen.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No passages selected yet.</Typography>
          ) : (
            <List dense disablePadding sx={{ maxHeight: 160, overflow: 'auto' }}>
              {chosen.map((s) => (
                <ListItem
                  key={`${s.start}-${s.end}`}
                  disableGutters
                  secondaryAction={
                    <IconButton
                      edge="end"
                      size="small"
                      aria-label="Remove passage"
                      onClick={() => setChosen((c) => c.filter((x) => x !== s))}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  }
                >
                  <ListItemText
                    primary={s.text.length > 160 ? `${s.text.slice(0, 160)}…` : s.text}
                    slotProps={{ primary: { variant: 'body2' } }}
                  />
                </ListItem>
              ))}
            </List>
          )}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="contained" disabled={chosen.length === 0} onClick={() => mode.onConfirm(chosen)}>
              {mode.confirmLabel ?? 'Use as evidence'}
            </Button>
          </Box>
        </DialogActions>
      )}
      <Popper
        open={pending !== null}
        anchorEl={pending && { getBoundingClientRect: () => pending.rect }}
        placement="top"
        sx={{ zIndex: 1500 }}
      >
        <Paper elevation={4}>
          <Button size="small" startIcon={<AddIcon />} onMouseDown={(e) => e.preventDefault()} onClick={addPending}>
            Add passage
          </Button>
        </Paper>
      </Popper>
    </Dialog>
  )
}
