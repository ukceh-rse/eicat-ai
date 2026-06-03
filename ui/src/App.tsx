import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import PapersPage from './pages/PapersPage'
import PaperDetailPage from './pages/PaperDetailPage'
import AnalysesPage from './pages/AnalysesPage'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import AnalysisPaperDetailPage from './pages/AnalysisPaperDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="papers" element={<PapersPage />} />
          <Route path="papers/:id" element={<PaperDetailPage />} />
          <Route path="analyses" element={<AnalysesPage />} />
          <Route path="analyses/:id" element={<AnalysisDetailPage />} />
          <Route path="analyses/:id/papers/:paperId" element={<AnalysisPaperDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
