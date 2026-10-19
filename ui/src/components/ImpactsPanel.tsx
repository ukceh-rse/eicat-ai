import { useState } from 'react'
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Checkbox, Chip, IconButton, Link,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import EditIcon from '@mui/icons-material/Edit'
import HistoryIcon from '@mui/icons-material/History'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined'
import RestoreIcon from '@mui/icons-material/Undo'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { CategoryChip } from './CategoryChip'
import ImpactEditDialog from './ImpactEditDialog'
import ImpactHistoryDrawer from './ImpactHistoryDrawer'
import PaperViewerDialog from './PaperViewerDialog'
import ReasonDialog from './ReasonDialog'
import { FIELD_LABELS, changedFromAi } from './impactFields'
import { useAnalysesStore } from '../store/analysesStore'
import type { AnalysisResponse, Impact, PaperResponse, ReviewedImpact } from '../types'

interface Props {
  analysis: AnalysisResponse
  papers: PaperResponse[]
  // review is locked while the analysis is running
  readOnly: boolean
}

function paperName(papers: PaperResponse[], id: string) {
  return papers.find((p) => p.id === id)?.filename ?? id
}

const describe = (i: ReviewedImpact) => `${i.current.mechanism} (${i.current.category})`

// why an impact holds its key: removed, added by a reviewer, or verified (it may have been unverified since)
function holderState(i: ReviewedImpact) {
  if (i.state === 'removed') return 'removed'
  if (i.origin === 'human') return 'added by a reviewer'
  return i.verified ? 'verified' : 'no longer verified'
}

// marks a value a reviewer changed, showing the AI's original on hover
function Changed({ ai }: { ai?: string }) {
  if (ai === undefined) return null
  return (
    <Tooltip title={`AI: ${ai}`}>
      <Box
        component="span" data-testid="changed-from-ai"
        sx={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', bgcolor: 'warning.main', ml: 0.75 }}
      />
    </Tooltip>
  )
}

function EvidenceCell({ impact, changed, onShow }: { impact: ReviewedImpact; changed?: string; onShow: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const text = impact.current.evidence
  const truncate = text.length > 240
  const unanchored = impact.evidence.some((s) => s.start === null)
  return (
    <TableCell sx={{ maxWidth: 380 }}>
      {unanchored && (
        <Alert severity="warning" icon={<WarningAmberIcon fontSize="inherit" />} sx={{ py: 0, mb: 0.5 }}>
          Evidence not found in the paper
        </Alert>
      )}
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
        {truncate && !expanded ? `${text.slice(0, 240)}…` : text}
        <Changed ai={changed && changed.length > 240 ? `${changed.slice(0, 240)}…` : changed} />
      </Typography>
      <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5 }}>
        {truncate && (
          <Link component="button" variant="caption" onClick={() => setExpanded((e) => !e)}>
            {expanded ? 'Show less' : 'Show more'}
          </Link>
        )}
        <Link component="button" variant="caption" onClick={onShow}>Show in paper</Link>
      </Box>
    </TableCell>
  )
}

export default function ImpactsPanel({ analysis, papers, readOnly }: Props) {
  const { patchImpact, removeImpact, restoreImpact } = useAnalysesStore()
  const [viewing, setViewing] = useState<ReviewedImpact | null>(null)
  const [editing, setEditing] = useState<ReviewedImpact | null>(null)
  const [history, setHistory] = useState<ReviewedImpact | null>(null)
  const [confirm, setConfirm] = useState<{ action: 'remove' | 'restore'; impact: ReviewedImpact } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const aid = analysis.id
  const byId = new Map(analysis.impacts.map((i) => [i.id, i]))
  const entries = analysis.paper_ids
    .map((pid) => [pid, analysis.impacts.filter((i) => i.paper_id === pid && i.state !== 'superseded')] as const)
    .filter(([, impacts]) => impacts.length > 0)

  if (entries.length === 0) {
    return <Typography color="text.secondary">No impacts found.</Typography>
  }

  const act = async (action: () => Promise<void>) => {
    setError(null)
    try { await action() } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const actions = (impact: ReviewedImpact) => (
    <TableCell padding="none" sx={{ whiteSpace: 'nowrap' }}>
      {impact.state === 'active' && (
        <>
          <Tooltip title="Edit">
            <span>
              <IconButton size="small" aria-label="Edit" disabled={readOnly} onClick={() => setEditing(impact)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Remove">
            <span>
              <IconButton
                size="small" aria-label="Remove" disabled={readOnly}
                onClick={() => setConfirm({ action: 'remove', impact })}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </>
      )}
      {(impact.state === 'removed' || impact.state === 'suppressed') && (
        <Tooltip title="Restore">
          <span>
            <IconButton
              size="small" aria-label="Restore" disabled={readOnly}
              onClick={() => setConfirm({ action: 'restore', impact })}
            >
              <RestoreIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      )}
      <Tooltip title="History">
        <IconButton size="small" aria-label="History" onClick={() => setHistory(impact)}>
          <HistoryIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </TableCell>
  )

  const origin = (impact: ReviewedImpact) => {
    const changed = changedFromAi(impact)
    const fields = Object.entries(changed) as [keyof Impact, string][]
    return (
      <TableCell sx={{ whiteSpace: 'nowrap' }}>
        <Chip label={impact.origin === 'ai' ? 'AI' : 'Human'} size="small" variant="outlined" />
        {fields.length > 0 && (
          <Tooltip
            title={
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>AI values</Typography>
                {fields.map(([k, v]) => (
                  <Typography key={k} variant="caption" sx={{ display: 'block' }}>
                    {FIELD_LABELS[k]}: {v.length > 120 ? `${v.slice(0, 120)}…` : v}
                  </Typography>
                ))}
              </Box>
            }
          >
            <Chip label="Changed from AI" size="small" color="warning" variant="outlined" sx={{ ml: 0.5 }} />
          </Tooltip>
        )}
      </TableCell>
    )
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {entries.map(([paperId, impacts], i) => {
        const active = impacts.filter((x) => x.state === 'active')
        const removed = impacts.filter((x) => x.state === 'removed')
        const suppressed = impacts.filter((x) => x.state === 'suppressed')
        const verified = active.filter((x) => x.verified || x.origin === 'human').length
        return (
          <Accordion
            key={paperId}
            defaultExpanded={i === 0}
            sx={{ border: '1px solid', borderColor: 'divider', mb: 1, '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography sx={{ fontWeight: 600, mr: 2 }}>
                {paperName(papers, paperId)}
              </Typography>
              <Chip label={`${active.length} impact${active.length !== 1 ? 's' : ''}`} size="small" sx={{ mr: 1 }} />
              <Chip
                label={`${verified}/${active.length} verified`} size="small"
                color={active.length > 0 && verified === active.length ? 'success' : 'default'} variant="outlined"
              />
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell padding="checkbox">Verified</TableCell>
                      <TableCell>Category</TableCell>
                      <TableCell>Mechanism</TableCell>
                      <TableCell>Impacted Species</TableCell>
                      <TableCell>Confidence</TableCell>
                      <TableCell>Evidence</TableCell>
                      <TableCell>Origin</TableCell>
                      <TableCell />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {active.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} sx={{ color: 'text.secondary' }}>No active impacts.</TableCell>
                      </TableRow>
                    )}
                    {active.map((impact) => {
                      const changed = changedFromAi(impact)
                      return (
                        <TableRow key={impact.id} hover data-testid="impact-row">
                          <TableCell padding="checkbox">
                            <Tooltip title={impact.origin === 'human' ? 'Added by a reviewer' : impact.verified ? 'Verified' : 'Not verified'}>
                              <span>
                                <Checkbox
                                  checked={impact.verified || impact.origin === 'human'}
                                  disabled={readOnly || impact.origin === 'human'}
                                  onChange={(e) => act(() => patchImpact(aid, impact.id, { verified: e.target.checked }))}
                                  slotProps={{ input: { 'aria-label': 'Verified' } }}
                                />
                              </span>
                            </Tooltip>
                          </TableCell>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>
                            <CategoryChip category={impact.current.category} /><Changed ai={changed.category} />
                            {impact.current.reversibility && (
                              <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                                {impact.current.reversibility}<Changed ai={changed.reversibility} />
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>{impact.current.mechanism}<Changed ai={changed.mechanism} /></TableCell>
                          <TableCell>
                            {impact.current.impacted_species.join(', ')}<Changed ai={changed.impacted_species} />
                          </TableCell>
                          <TableCell>{impact.current.confidence ?? '—'}<Changed ai={changed.confidence} /></TableCell>
                          <EvidenceCell impact={impact} changed={changed.evidence} onShow={() => setViewing(impact)} />
                          {origin(impact)}
                          {actions(impact)}
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
              {removed.length > 0 && (
                <Accordion disableGutters elevation={0} sx={{ borderTop: '1px solid', borderColor: 'divider', '&:before': { display: 'none' } }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Removed ({removed.length})</Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ p: 0 }}>
                    <Table size="small">
                      <TableBody>
                        {removed.map((impact) => (
                          <TableRow key={impact.id} data-testid="removed-row">
                            <TableCell><CategoryChip category={impact.current.category} /></TableCell>
                            <TableCell>{impact.current.mechanism}</TableCell>
                            <TableCell>{impact.current.impacted_species.join(', ')}</TableCell>
                            {origin(impact)}
                            {actions(impact)}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </AccordionDetails>
                </Accordion>
              )}
              {suppressed.length > 0 && (
                <Accordion disableGutters elevation={0} sx={{ borderTop: '1px solid', borderColor: 'divider', '&:before': { display: 'none' } }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Suppressed ({suppressed.length})</Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ p: 0 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 1 }}>
                      Found again by a run, but an expert decision already holds this mechanism for the paper.
                    </Typography>
                    <Table size="small">
                      <TableBody>
                        {suppressed.map((impact) => {
                          const holder = impact.held_by ? byId.get(impact.held_by) : undefined
                          return (
                            <TableRow key={impact.id} data-testid="suppressed-row">
                              <TableCell><CategoryChip category={impact.current.category} /></TableCell>
                              <TableCell>{impact.current.mechanism}</TableCell>
                              <TableCell>
                                <Typography variant="body2">
                                  Held by: {holder
                                    ? `${describe(holder)}, ${holderState(holder)}`
                                    : 'unknown'}
                                </Typography>
                                {impact.sightings.map((s) => (
                                  <Typography key={s.run_id} variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                    Run {new Date(s.at.endsWith('Z') ? s.at : `${s.at}Z`).toLocaleString()}: {s.ai.category}
                                    {s.ai.confidence ? `, ${s.ai.confidence} confidence` : ''}
                                    {s.ai.impacted_species.length > 0 ? `, ${s.ai.impacted_species.join(', ')}` : ''}
                                  </Typography>
                                ))}
                              </TableCell>
                              {actions(impact)}
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  </AccordionDetails>
                </Accordion>
              )}
            </AccordionDetails>
          </Accordion>
        )
      })}

      {viewing && (
        <PaperViewerDialog
          paperId={viewing.paper_id}
          filename={paperName(papers, viewing.paper_id)}
          onClose={() => setViewing(null)}
          mode={{ kind: 'highlight', spans: viewing.evidence }}
        />
      )}
      {editing && (
        <ImpactEditDialog
          title="Edit impact"
          paperId={editing.paper_id}
          filename={paperName(papers, editing.paper_id)}
          initial={editing.current}
          evidence={editing.evidence}
          onSave={(fields, evidence, note) => patchImpact(aid, editing.id, { fields, evidence, note })}
          onClose={() => setEditing(null)}
        />
      )}
      {history && (
        <ImpactHistoryDrawer
          analysisId={aid}
          impactId={history.id}
          title={describe(history)}
          onClose={() => setHistory(null)}
        />
      )}
      {confirm && (
        <ReasonDialog
          title={confirm.action === 'remove' ? 'Remove impact' : 'Restore impact'}
          text={confirm.action === 'remove'
            ? `${describe(confirm.impact)} will move to the paper's Removed list. You can restore it later.`
            : confirm.impact.state === 'suppressed'
              ? `${describe(confirm.impact)} will become an active, verified impact with the values of its latest sighting.`
              : `${describe(confirm.impact)} will become active again.`}
          confirmLabel={confirm.action === 'remove' ? 'Remove' : 'Restore'}
          onConfirm={(note) => (confirm.action === 'remove' ? removeImpact : restoreImpact)(aid, confirm.impact.id, note)}
          onClose={() => setConfirm(null)}
        />
      )}
    </Box>
  )
}
