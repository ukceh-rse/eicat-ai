import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Checkbox, Chip, Collapse, IconButton, ListItemIcon,
  ListItemText, Menu, MenuItem, Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import MoreVertIcon from '@mui/icons-material/MoreVert'
import HistoryIcon from '@mui/icons-material/History'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined'
import RestoreIcon from '@mui/icons-material/Undo'
import PostAddIcon from '@mui/icons-material/PostAdd'
import CancelIcon from '@mui/icons-material/Cancel'
import { CategoryChip } from './CategoryChip'
import ImpactHistoryDrawer from './ImpactHistoryDrawer'
import ReasonDialog from './ReasonDialog'
import { SpanStatus } from './SpanList'
import { CategorySelect, ConfidenceSelect, MechanismSelect, ReversibilitySelect, SpeciesInput } from './ImpactInputs'
import { FIELD_LABELS, REVERSIBILITIES, changedFromAi, needsReversibility, readable } from './impactFields'
import { useAnalysesStore } from '../store/analysesStore'
import type { AnalysisResponse, Impact, ImpactFields, PaperResponse, ReviewedImpact } from '../types'

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

// fixed column widths; evidence, with no width, takes what is left
const COLUMNS = [72, 124, 190, 150, 118, undefined, 104, 76]
const compact = { variant: 'standard' as const, size: 'small' as const, fullWidth: true }
const truncate = (v: string, n: number) => (v.length > n ? `${v.slice(0, n)}…` : v)

// a text field saved when it loses focus with a changed value; a failed save puts the stored value back
function BlurField({ value, onSave, ...props }: {
  value: string; onSave: (value: string) => Promise<boolean>; label: string; multiline?: boolean; disabled?: boolean
}) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  const save = async () => {
    if (text !== value && !(await onSave(text))) setText(value)
  }
  return (
    <TextField
      size="small" fullWidth minRows={props.multiline ? 2 : undefined} {...props} value={text}
      onChange={(e) => setText(e.target.value)} onBlur={save}
      onKeyDown={(e) => { if (e.key === 'Enter' && !props.multiline) (e.target as HTMLElement).blur() }}
    />
  )
}

function EvidenceCell({ impact, onOpen }: { impact: ReviewedImpact; onOpen: () => void }) {
  const unanchored = impact.evidence.find((s) => s.start === null)
  const approximate = impact.evidence.find((s) => s.approximate)
  const ai = impact.ai ? `The AI's evidence: ${truncate(impact.ai.evidence, 300)}` : undefined
  return (
    <TableCell>
      <Box
        role="link" tabIndex={0} onClick={onOpen} onKeyDown={(e) => { if (e.key === 'Enter') onOpen() }}
        sx={{ display: 'flex', gap: 0.5, cursor: 'pointer', '&:hover': { color: 'primary.main' } }}
      >
        {(unanchored || approximate) && <SpanStatus span={unanchored ?? approximate!} detail={ai} />}
        <Typography
          variant="body2" data-testid="evidence"
          sx={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {readable(impact.current.evidence)}
        </Typography>
      </Box>
    </TableCell>
  )
}

// origin, and for an AI impact a reviewer changed, which fields differ from the AI's values
function OriginCell({ impact }: { impact: ReviewedImpact }) {
  const fields = Object.entries(changedFromAi(impact)) as [keyof Impact, string][]
  const label = impact.origin === 'human' ? 'Human' : fields.length > 0 ? 'AI, edited' : 'AI'
  const chip = (
    <Chip
      label={label} size="small" variant="outlined" data-testid="origin"
      color={fields.length > 0 ? 'warning' : 'default'}
    />
  )
  return (
    <TableCell>
      {fields.length === 0 ? chip : (
        <Tooltip
          title={
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 600 }}>AI values</Typography>
              {fields.map(([k, v]) => (
                <Typography key={k} variant="caption" sx={{ display: 'block' }}>
                  {FIELD_LABELS[k]}: {truncate(v, 120)}
                </Typography>
              ))}
            </Box>
          }
        >
          {chip}
        </Tooltip>
      )}
    </TableCell>
  )
}

export default function ImpactsPanel({ analysis, papers, readOnly }: Props) {
  const { patchImpact, removeImpact, restoreImpact, removePaper } = useAnalysesStore()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [history, setHistory] = useState<ReviewedImpact | null>(null)
  const [confirm, setConfirm] = useState<{ action: 'remove' | 'restore'; impact: ReviewedImpact } | null>(null)
  const [menu, setMenu] = useState<{ impact: ReviewedImpact; anchor: HTMLElement } | null>(null)
  // a change to MR or MV waits for its reversibility
  const [pending, setPending] = useState<{ impact: ReviewedImpact; category: string; anchor: HTMLElement } | null>(null)
  const [detail, setDetail] = useState<Set<string>>(new Set())
  // a reason is recorded with the row's next change, then cleared
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  const aid = analysis.id
  const byId = new Map(analysis.impacts.map((i) => [i.id, i]))
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(analysis.paper_ids.slice(0, 1)))
  // the row to bring into view, e.g. after returning from its evidence page
  const [highlight, setHighlight] = useState<string | null>(null)
  const rowRef = useRef<HTMLTableRowElement | null>(null)
  const categoryCells = useRef<Record<string, HTMLTableCellElement | null>>({})

  const target = params.get('impact')
  useEffect(() => {
    if (!target) return
    const impact = analysis.impacts.find((i) => i.id === target)
    if (impact) {
      setExpanded((e) => new Set(e).add(impact.paper_id))
      setHighlight(target)
    }
    setParams((p) => { p.delete('impact'); return p }, { replace: true })
  }, [target, analysis.impacts, setParams])
  useEffect(() => {
    if (!highlight) return
    rowRef.current?.scrollIntoView({ block: 'center' })
    const timer = setTimeout(() => setHighlight(null), 3000)
    return () => clearTimeout(timer)
  }, [highlight])

  if (analysis.paper_ids.length === 0) {
    return <Typography color="text.secondary">No papers added yet.</Typography>
  }

  const act = async (action: () => Promise<void>) => {
    setError(null)
    try {
      await action()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      return false
    }
  }

  // an edit from a row: one change, saved at once, with the row's reason
  const edit = async (impact: ReviewedImpact, fields: ImpactFields) => {
    const note = reasons[impact.id]?.trim() || undefined
    const ok = await act(() => patchImpact(aid, impact.id, { fields, note }))
    if (ok && note) setReasons((r) => ({ ...r, [impact.id]: '' }))
    return ok
  }

  const changeCategory = (impact: ReviewedImpact, category: string) => {
    const anchor = categoryCells.current[impact.id]
    if (category === impact.current.category) return
    if (needsReversibility(category) && anchor) setPending({ impact, category, anchor })
    else edit(impact, { category })
  }

  const toggle = (set: Set<string>, id: string) => {
    const next = new Set(set)
    if (!next.delete(id)) next.add(id)
    return next
  }

  const actions = (impact: ReviewedImpact) => (
    <TableCell padding="none" sx={{ whiteSpace: 'nowrap' }}>
      {impact.state === 'active' && (
        <Tooltip title={detail.has(impact.id) ? 'Hide details' : 'Details'}>
          <IconButton size="small" aria-label="Details" onClick={() => setDetail((d) => toggle(d, impact.id))}>
            {detail.has(impact.id) ? <KeyboardArrowUpIcon fontSize="small" /> : <KeyboardArrowDownIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      )}
      <IconButton
        size="small" aria-label="Actions" onClick={(e) => setMenu({ impact, anchor: e.currentTarget })}
      >
        <MoreVertIcon fontSize="small" />
      </IconButton>
    </TableCell>
  )

  const row = (impact: ReviewedImpact) => {
    const lock = readOnly
    return [
      <TableRow
        key={impact.id} hover data-testid="impact-row" ref={impact.id === highlight ? rowRef : undefined}
        sx={{
          '& > td': { py: 0.5, verticalAlign: 'top', borderBottom: detail.has(impact.id) ? 'none' : undefined },
          ...(impact.id === highlight && { bgcolor: 'action.selected', transition: 'background-color 0.5s' }),
        }}
      >
        <TableCell padding="checkbox">
          <Tooltip title={impact.origin === 'human' ? 'Added by a reviewer' : impact.verified ? 'Verified' : 'Not verified'}>
            <span>
              <Checkbox
                size="small"
                checked={impact.verified || impact.origin === 'human'}
                disabled={lock || impact.origin === 'human'}
                onChange={(e) => act(() => patchImpact(aid, impact.id, { verified: e.target.checked }))}
                slotProps={{ input: { 'aria-label': 'Verified' } }}
              />
            </span>
          </Tooltip>
        </TableCell>
        <TableCell ref={(el: HTMLTableCellElement | null) => { categoryCells.current[impact.id] = el }}>
          <CategorySelect
            {...compact} disabled={lock} value={impact.current.category}
            onChange={(v) => changeCategory(impact, v)}
            slotProps={{
              input: { disableUnderline: true, 'aria-label': 'Category' } as object,
              select: { renderValue: (v) => <CategoryChip category={v as string} short /> },
            }}
          />
          {needsReversibility(impact.current.category) && (
            <ReversibilitySelect
              {...compact} disabled={lock} value={impact.current.reversibility}
              slotProps={{ input: { disableUnderline: true, 'aria-label': 'Reversibility' } as object }}
              sx={{ '& .MuiSelect-select': { fontSize: '0.75rem', py: 0 } }}
              onChange={(v) => edit(impact, { reversibility: v })}
            />
          )}
        </TableCell>
        <TableCell>
          <MechanismSelect
            {...compact} disabled={lock} value={impact.current.mechanism}
            slotProps={{ input: { disableUnderline: true, 'aria-label': 'Mechanism' } as object }}
            sx={{ '& .MuiSelect-select': { fontSize: '0.875rem' } }}
            onChange={(v) => { if (v !== impact.current.mechanism) edit(impact, { mechanism: v }) }}
          />
        </TableCell>
        <TableCell>
          <SpeciesInput
            {...compact} disabled={lock} value={impact.current.impacted_species}
            placeholder={impact.current.impacted_species.length ? undefined : 'Add…'}
            onChange={(v) => edit(impact, { impacted_species: v })}
          />
        </TableCell>
        <TableCell>
          <ConfidenceSelect
            {...compact} disabled={lock} value={impact.current.confidence ?? null}
            slotProps={{ input: { disableUnderline: true, 'aria-label': 'Confidence' } as object }}
            sx={{ '& .MuiSelect-select': { fontSize: '0.875rem' } }}
            onChange={(v) => { if (v !== (impact.current.confidence ?? null)) edit(impact, { confidence: v }) }}
          />
        </TableCell>
        <EvidenceCell
          impact={impact} onOpen={() => navigate(`/analyses/${aid}/impacts/${impact.id}/evidence`)}
        />
        <OriginCell impact={impact} />
        {actions(impact)}
      </TableRow>,
      <TableRow key={`${impact.id}-detail`}>
        <TableCell colSpan={COLUMNS.length} sx={{ py: 0, ...(!detail.has(impact.id) && { borderBottom: 'none' }) }}>
          <Collapse in={detail.has(impact.id)} unmountOnExit>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 2, py: 1.5 }}>
              <BlurField
                label="Alien species" value={impact.current.alien_species} disabled={lock}
                onSave={(v) => edit(impact, { alien_species: v })}
              />
              <TextField
                size="small" label="Reason for the next change (optional)" disabled={lock}
                value={reasons[impact.id] ?? ''}
                onChange={(e) => setReasons((r) => ({ ...r, [impact.id]: e.target.value }))}
                helperText="Recorded with the next field change saved on this impact"
              />
              <Box sx={{ gridColumn: '1 / -1' }}>
                <BlurField
                  label="Justification" multiline value={impact.current.justification} disabled={lock}
                  onSave={(v) => edit(impact, { justification: v })}
                />
              </Box>
              {Object.keys(changedFromAi(impact)).length > 0 && (
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>AI values</Typography>
                  {(Object.entries(changedFromAi(impact)) as [keyof Impact, string][]).map(([k, v]) => (
                    <Typography key={k} variant="body2" color="text.secondary">
                      {FIELD_LABELS[k]}: {truncate(v, 400)}
                    </Typography>
                  ))}
                </Box>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>,
    ]
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {analysis.paper_ids.map((paperId) => {
        const impacts = analysis.impacts.filter((x) => x.paper_id === paperId && x.state !== 'superseded')
        const active = impacts.filter((x) => x.state === 'active')
        const removed = impacts.filter((x) => x.state === 'removed')
        const suppressed = impacts.filter((x) => x.state === 'suppressed')
        const verified = active.filter((x) => x.verified || x.origin === 'human').length
        const run = paperId in analysis.results || impacts.length > 0
        const stop = (e: React.SyntheticEvent) => e.stopPropagation()
        return (
          <Accordion
            key={paperId} data-testid="paper-section"
            expanded={expanded.has(paperId)} onChange={() => setExpanded((e) => toggle(e, paperId))}
            sx={{ border: '1px solid', borderColor: 'divider', mb: 1, '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ '& .MuiAccordionSummary-content': { alignItems: 'center' } }}>
              <Typography sx={{ fontWeight: 600, mr: 2 }}>{paperName(papers, paperId)}</Typography>
              {run ? (
                <>
                  <Chip label={`${active.length} impact${active.length !== 1 ? 's' : ''}`} size="small" sx={{ mr: 1 }} />
                  <Chip
                    label={`${verified}/${active.length} verified`} size="small"
                    color={active.length > 0 && verified === active.length ? 'success' : 'default'} variant="outlined"
                  />
                </>
              ) : (
                <Chip label="Not run yet" size="small" variant="outlined" />
              )}
              <Box sx={{ ml: 'auto', mr: 1, display: 'flex' }} onClick={stop} onFocus={stop}>
                <Tooltip title="Add an impact from this paper">
                  <span>
                    <IconButton
                      component="span" size="small" disabled={readOnly} aria-label="Add an impact from this paper"
                      onClick={() => navigate(`/analyses/${aid}/papers/${paperId}/new-impact`)}
                    >
                      <PostAddIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
                <Tooltip title="Remove from analysis">
                  <span>
                    <IconButton
                      component="span" size="small" disabled={readOnly} aria-label="Remove from analysis"
                      onClick={() => act(() => removePaper(aid, paperId))}
                    >
                      <CancelIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <Table size="small" sx={{ tableLayout: 'fixed' }}>
                <colgroup>{COLUMNS.map((w, i) => <col key={i} style={w ? { width: w } : undefined} />)}</colgroup>
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox">Verified</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Mechanism</TableCell>
                    <TableCell>Impacted species</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Evidence</TableCell>
                    <TableCell>Origin</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {active.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={COLUMNS.length} sx={{ color: 'text.secondary' }}>
                        {run ? 'No impacts found.' : 'This paper has not been run yet.'}
                      </TableCell>
                    </TableRow>
                  )}
                  {active.flatMap(row)}
                </TableBody>
              </Table>
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
                            <OriginCell impact={impact} />
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

      <Menu anchorEl={menu?.anchor} open={menu !== null} onClose={() => setMenu(null)}>
        {menu?.impact.state === 'active' && (
          <MenuItem disabled={readOnly} onClick={() => { setConfirm({ action: 'remove', impact: menu.impact }); setMenu(null) }}>
            <ListItemIcon><DeleteOutlineIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Remove</ListItemText>
          </MenuItem>
        )}
        {(menu?.impact.state === 'removed' || menu?.impact.state === 'suppressed') && (
          <MenuItem disabled={readOnly} onClick={() => { setConfirm({ action: 'restore', impact: menu.impact }); setMenu(null) }}>
            <ListItemIcon><RestoreIcon fontSize="small" /></ListItemIcon>
            <ListItemText>Restore</ListItemText>
          </MenuItem>
        )}
        <MenuItem onClick={() => { setHistory(menu!.impact); setMenu(null) }}>
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>History</ListItemText>
        </MenuItem>
      </Menu>
      <Menu anchorEl={pending?.anchor} open={pending !== null} onClose={() => setPending(null)}>
        <MenuItem disabled dense><Typography variant="caption">Reversibility for {pending?.category}</Typography></MenuItem>
        {REVERSIBILITIES.map((r) => (
          <MenuItem
            key={r}
            onClick={() => { edit(pending!.impact, { category: pending!.category, reversibility: r }); setPending(null) }}
          >
            {r}
          </MenuItem>
        ))}
      </Menu>
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
