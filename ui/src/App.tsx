import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import LandingPage from './pages/LandingPage'
import PapersPage from './pages/PapersPage'
import AnalysesPage from './pages/AnalysesPage'
import AnalysisDetailPage from './pages/AnalysisDetailPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<Layout />}>
          <Route path="papers" element={<PapersPage />} />
          <Route path="analyses" element={<AnalysesPage />} />
          <Route path="analyses/:id" element={<AnalysisDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
