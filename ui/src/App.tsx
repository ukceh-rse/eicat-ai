import { BrowserRouter, Routes, Route } from 'react-router'
import Upload from './components/Upload'
import Navigation from './components/Navigation'
import Analysis from './components/Analysis'
import Home from './components/Home'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Navigation />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/upload" element={<Upload />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
