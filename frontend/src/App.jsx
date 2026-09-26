import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import TopNav from './components/TopNav.jsx'
import Analyze from './pages/Analyze.jsx'
import CaseReport from './pages/CaseReport.jsx'
import Dataset from './pages/Dataset.jsx'
import Method from './pages/Method.jsx'
import Cases from './pages/Cases.jsx'
import Train from './pages/Train.jsx'

// Recharts is large; only the Research page needs it.
const Research = lazy(() => import('./pages/Research.jsx'))

export default function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-[1200px] px-4 sm:px-8 py-8">
        <Routes>
          <Route path="/" element={<Analyze />} />
          <Route path="/case/:id" element={<CaseReport />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/research" element={<Suspense fallback={<p className="text-sm text-muted">Loading results…</p>}><Research /></Suspense>} />
          <Route path="/dataset" element={<Dataset />} />
          <Route path="/train" element={<Train />} />
          <Route path="/method" element={<Method />} />
        </Routes>
      </main>
    </div>
  )
}
