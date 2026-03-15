import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import LabDetail from './pages/LabDetail'
import TopologyEditor from './pages/TopologyEditor'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/labs/:slug" element={<LabDetail />} />
        <Route path="/labs/:slug/editor" element={<TopologyEditor />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
