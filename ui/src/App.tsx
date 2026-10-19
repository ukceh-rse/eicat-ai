import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import PapersPage from './pages/PapersPage'
import AnalysesPage from './pages/AnalysesPage'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import EvidencePage from './pages/EvidencePage'
import NewImpactPage from './pages/NewImpactPage'
import PaperPage from './pages/PaperPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="papers" element={<PapersPage />} />
          <Route path="papers/:paperId" element={<PaperPage />} />
          <Route path="analyses" element={<AnalysesPage />} />
          <Route path="analyses/:id" element={<AnalysisDetailPage />} />
          <Route path="analyses/:id/impacts/:impactId/evidence" element={<EvidencePage />} />
          <Route path="analyses/:id/papers/:paperId/new-impact" element={<NewImpactPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
