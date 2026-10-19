import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Alert, Box, Button, CircularProgress, Paper, Popper, Typography } from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api/client'
import type { AnchoredSpan } from './impactFields'
import { newRegistry, rehypeSourceOffsets, selectionToSpan, type SourceSpan } from './sourceOffsets'

// a selection's leading and trailing whitespace (e.g. the newline a triple-click takes) is not evidence
function trimmed(markdown: string, { start, end }: SourceSpan): AnchoredSpan | null {
  while (start < end && /\s/.test(markdown[start])) start++
  while (end > start && /\s/.test(markdown[end - 1])) end--
  return end > start ? { start, end, text: markdown.slice(start, end) } : null
}

interface Props {
  paperId: string
  // passages to highlight; the first is scrolled into view once the paper has rendered
  highlights?: SourceSpan[]
  // when given, selecting text offers to add it as a passage
  onSelect?: (span: AnchoredSpan) => void
}

// a paper's markdown, rendered with highlighted passages and, optionally, selection of new ones
export default function PaperText({ paperId, highlights = [], onSelect }: Props) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<{ span: AnchoredSpan; rect: DOMRect } | null>(null)
  const [selectError, setSelectError] = useState<string | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  const highlightKey = JSON.stringify(highlights.map(({ start, end }) => ({ start, end })))
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
    if (scrolled.current || !rendered) return
    bodyRef.current?.querySelector('mark')?.scrollIntoView({ block: 'center' })
    scrolled.current = true
  }, [rendered])

  const handleMouseUp = () => {
    if (!onSelect || content === null || !bodyRef.current) return
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
    if (!pending || !onSelect) return
    onSelect(pending.span)
    setPending(null)
    window.getSelection()?.removeAllRanges()
  }

  let body: ReactNode
  if (error) {
    body = <Typography color="error">{error}</Typography>
  } else if (content === null) {
    body = <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
  } else {
    body = (
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
    )
  }

  return (
    <>
      {selectError && <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setSelectError(null)}>{selectError}</Alert>}
      {body}
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
    </>
  )
}
