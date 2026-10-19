import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Breadcrumbs, Link, Typography } from '@mui/material'
import PaperLayout from '../components/PaperLayout'
import PaperText from '../components/PaperText'
import { usePapersStore } from '../store/papersStore'

// a paper's text, for reading
export default function PaperPage() {
  const { paperId } = useParams<{ paperId: string }>()
  const navigate = useNavigate()
  const { papers, fetch } = usePapersStore()
  const paper = papers.find((p) => p.id === paperId)

  useEffect(() => { if (papers.length === 0) fetch() }, [papers.length, fetch])

  return (
    <PaperLayout
      header={
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link component="button" underline="hover" color="inherit" onClick={() => navigate('/papers')}>Papers</Link>
          <Typography color="text.primary">{paper?.filename ?? paperId}</Typography>
        </Breadcrumbs>
      }
      paper={<PaperText paperId={paperId!} />}
    />
  )
}
