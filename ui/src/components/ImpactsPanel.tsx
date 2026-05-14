import { useState } from 'react'
import {
  Accordion, AccordionDetails, AccordionSummary, Box, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { CategoryChip } from './CategoryChip'
import type { Impact, PaperResponse } from '../types'

interface Props {
  results: Record<string, Impact[]>
  papers: PaperResponse[]
}

function paperName(papers: PaperResponse[], id: string) {
  return papers.find((p) => p.id === id)?.filename ?? id
}

function EvidenceCell({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const truncate = text.length > 240
  return (
    <TableCell sx={{ maxWidth: 380 }}>
      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
        {truncate && !expanded ? `${text.slice(0, 240)}…` : text}
      </Typography>
      {truncate && (
        <Typography
          variant="caption"
          color="primary"
          sx={{ cursor: 'pointer', display: 'block', mt: 0.5 }}
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? 'Show less' : 'Show more'}
        </Typography>
      )}
    </TableCell>
  )
}

export default function ImpactsPanel({ results, papers }: Props) {
  const entries = Object.entries(results).filter(([, impacts]) => impacts.length > 0)

  if (entries.length === 0) {
    return <Typography color="text.secondary">No impacts found.</Typography>
  }

  return (
    <Box>
      {entries.map(([paperId, impacts], i) => (
        <Accordion
          key={paperId}
          defaultExpanded={i === 0}
          sx={{ border: '1px solid', borderColor: 'divider', mb: 1, '&:before': { display: 'none' } }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography sx={{ fontWeight: 600, mr: 2 }}>
              {paperName(papers, paperId)}
            </Typography>
            <Chip label={`${impacts.length} impact${impacts.length !== 1 ? 's' : ''}`} size="small" />
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Category</TableCell>
                    <TableCell>Mechanism</TableCell>
                    <TableCell>Impacted Species</TableCell>
                    <TableCell>Confidence</TableCell>
                    <TableCell>Evidence</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {impacts.map((impact, j) => (
                    <TableRow key={j} hover>
                      <TableCell><CategoryChip category={impact.category} /></TableCell>
                      <TableCell>{impact.mechanism}</TableCell>
                      <TableCell>{impact.impacted_species.join(', ')}</TableCell>
                      <TableCell>{impact.confidence ?? '—'}</TableCell>
                      <EvidenceCell text={impact.evidence} />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  )
}
