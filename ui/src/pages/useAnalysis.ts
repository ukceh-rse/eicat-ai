import { useEffect, useState } from 'react'
import { useAnalysesStore } from '../store/analysesStore'
import { usePapersStore } from '../store/papersStore'

// an analysis and the papers list, fetched when a page is opened by its address rather than from the analysis page
export function useAnalysis(id: string | undefined) {
  const { analyses, fetch } = useAnalysesStore()
  const { papers, fetch: fetchPapers } = usePapersStore()
  const analysis = analyses.find((a) => a.id === id)
  const [fetched, setFetched] = useState(analysis !== undefined && papers.length > 0)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (fetched) return
    Promise.all([fetch(), fetchPapers()])
      .then(() => setFetched(true))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
  }, [fetched, fetch, fetchPapers, attempt])

  const retry = () => {
    setError(null)
    setAttempt((a) => a + 1)
  }
  return { analysis, papers, loading: !fetched && !error, error, retry }
}
