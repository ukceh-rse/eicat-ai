import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import {
  Box, Chip, CircularProgress, IconButton, Paper, Tooltip, Typography,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import type { Element } from 'hast'
import { api } from '../api/client'
import { useAnalysesStore } from '../store/analysesStore'
import { usePapersStore } from '../store/papersStore'
import { categoryConfig } from '../components/CategoryChip'
import type { Impact } from '../types'

const markdownStyles = {
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
}

// --- Sliding-window highlight matching ---

interface WordToken { norm: string; start: number; end: number }

function tokenizeWithPositions(text: string): WordToken[] {
  const tokens: WordToken[] = []
  const re = /\S+/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const norm = m[0].toLowerCase().replace(/[^a-z0-9]/g, '')
    if (norm.length > 1) tokens.push({ norm, start: m.index, end: m.index + m[0].length })
  }
  return tokens
}

function normalizeWords(text: string): string[] {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(w => w.length > 1)
}

function findSpan(
  contentTokens: WordToken[],
  evidenceText: string,
  threshold = 0.55,
): { start: number; end: number } | null {
  const evWords = normalizeWords(evidenceText)
  if (!evWords.length) return null
  const windowSize = evWords.length
  if (contentTokens.length < windowSize) return null

  // Evidence word frequency map
  const evCounts = new Map<string, number>()
  for (const w of evWords) evCounts.set(w, (evCounts.get(w) ?? 0) + 1)

  // O(n) sliding window: track how many evidence tokens are satisfied
  const winCounts = new Map<string, number>()
  let matches = 0

  const add = (t: string) => {
    const wc = winCounts.get(t) ?? 0
    const ec = evCounts.get(t) ?? 0
    if (ec > 0 && wc < ec) matches++
    winCounts.set(t, wc + 1)
  }
  const remove = (t: string) => {
    const wc = winCounts.get(t) ?? 0
    const ec = evCounts.get(t) ?? 0
    if (ec > 0 && wc > 0 && wc <= ec) matches--
    winCounts.set(t, wc - 1)
  }

  for (let j = 0; j < windowSize; j++) add(contentTokens[j].norm)

  let bestScore = matches / evWords.length
  let bestIdx = 0

  for (let i = 1; i <= contentTokens.length - windowSize; i++) {
    remove(contentTokens[i - 1].norm)
    add(contentTokens[i + windowSize - 1].norm)
    const score = matches / evWords.length
    if (score > bestScore) { bestScore = score; bestIdx = i }
  }

  if (bestScore < threshold) return null
  return {
    start: contentTokens[bestIdx].start,
    end: contentTokens[bestIdx + windowSize - 1].end,
  }
}

function insertHighlightMarkers(content: string, impacts: Impact[]): string {
  const contentTokens = tokenizeWithPositions(content)
  type Span = { start: number; end: number; i: number }
  const spans: Span[] = []

  for (let i = 0; i < impacts.length; i++) {
    const evidence = impacts[i].evidence
    if (!evidence?.trim()) continue

    // Try exact match first
    const escaped = evidence.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    try {
      const m = new RegExp(escaped).exec(content)
      if (m) { spans.push({ start: m.index, end: m.index + evidence.length, i }); continue }
    } catch { /* fall through */ }

    // Sliding window fallback
    const span = findSpan(contentTokens, evidence)
    if (span) spans.push({ ...span, i })
  }

  // Insert from end → start to keep earlier offsets valid
  spans.sort((a, b) => b.start - a.start)
  let result = content
  for (const { start, end, i } of spans) {
    result = result.slice(0, start) + `<mark data-impact-index="${i}">` + result.slice(start, end) + '</mark>' + result.slice(end)
  }
  return result
}

export default function AnalysisPaperDetailPage() {
  const { id, paperId } = useParams<{ id: string; paperId: string }>()
  const navigate = useNavigate()
  const { analyses, fetch: fetchAnalyses } = useAnalysesStore()
  const { papers, fetch: fetchPapers } = usePapersStore()
  const [content, setContent] = useState<string | null>(null)
  const [contentError, setContentError] = useState<string | null>(null)

  useEffect(() => { Promise.all([fetchAnalyses(), fetchPapers()]) }, [fetchAnalyses, fetchPapers])

  const analysis = analyses.find((a) => a.id === id)
  const paper = papers.find((p) => p.id === paperId)
  const impacts: Impact[] = useMemo(
    () => (analysis && paperId ? analysis.results[paperId] ?? [] : []),
    [analysis, paperId],
  )

  useEffect(() => {
    if (!paperId || paper?.status !== 'ready') return
    api.papers.content(paperId)
      .then((r) => setContent(r.content))
      .catch((e) => setContentError(String(e)))
  }, [paperId, paper?.status])

  const processedContent = useMemo(
    () => (content && impacts.length ? insertHighlightMarkers(content, impacts) : content),
    [content, impacts],
  )

  const markComponent = useMemo(() => ({
    mark: ({ node, children }: { node?: Element; children?: React.ReactNode }) => {
      const idx = parseInt(String(node?.properties?.dataImpactIndex ?? '-1'))
      const impact = impacts[idx]
      if (!impact) return <mark>{children}</mark>
      const cfg = categoryConfig[impact.category] ?? { label: impact.category, bg: '#9e9e9e', color: '#fff' }
      return (
        <Tooltip
          arrow
          title={
            <Box sx={{ p: 0.25 }}>
              <Chip
                label={cfg.label}
                size="small"
                sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 600, mb: 0.75, display: 'flex' }}
              />
              <Typography variant="caption" sx={{ display: 'block' }}><b>Mechanism:</b> {impact.mechanism}</Typography>
              <Typography variant="caption" sx={{ display: 'block' }}><b>Impacted species:</b> {impact.impacted_species.join(', ')}</Typography>
              {impact.confidence && (
                <Typography variant="caption" sx={{ display: 'block' }}><b>Confidence:</b> {impact.confidence}</Typography>
              )}
            </Box>
          }
        >
          <mark style={{
            backgroundColor: `${cfg.bg}33`,
            borderBottom: `2px solid ${cfg.bg}`,
            borderRadius: 2,
            cursor: 'help',
            padding: '1px 0',
          }}>
            {children}
          </mark>
        </Tooltip>
      )
    },
  }), [impacts])

  if (!analysis || !paper) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress /></Box>
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography
            variant="h5"
            onClick={() => navigate('/analyses')}
            sx={{ fontWeight: 400, color: 'text.secondary', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
          >
            Analyses
          </Typography>
          <Typography variant="h5" color="text.disabled">/</Typography>
          <Typography
            variant="h5"
            onClick={() => navigate(`/analyses/${id}`)}
            sx={{ fontWeight: 400, fontStyle: 'italic', color: 'text.secondary', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
          >
            {analysis.species.scientific_name}
          </Typography>
          <Typography variant="h5" color="text.disabled">/</Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>{paper.filename}</Typography>
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
        ) : processedContent === null ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={markdownStyles}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
              components={markComponent as never}
            >
              {processedContent}
            </ReactMarkdown>
          </Box>
        )}
      </Paper>
    </Box>
  )
}
