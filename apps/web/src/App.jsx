import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import FeedPage from './pages/FeedPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/upload" element={<Navigate to="/" replace />} />
        <Route path="/feed" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
