import type { ReactNode } from 'react'
import { Box, Paper } from '@mui/material'

interface Props {
  header: ReactNode
  paper: ReactNode
  // the side panel beside the paper; omitted for plain reading
  panel?: ReactNode
}

// a paper with its own scroll, beside a panel that stays in view
export default function PaperLayout({ header, paper, panel }: Props) {
  return (
    <Box>
      {header}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        <Paper variant="outlined" sx={{ flex: 1, minWidth: 0, p: 3, height: 'calc(100vh - 200px)', overflow: 'auto' }}>
          {paper}
        </Paper>
        {panel && (
          <Paper
            variant="outlined"
            sx={{ width: 380, flexShrink: 0, p: 2, maxHeight: 'calc(100vh - 200px)', overflow: 'auto' }}
          >
            {panel}
          </Paper>
        )}
      </Box>
    </Box>
  )
}
