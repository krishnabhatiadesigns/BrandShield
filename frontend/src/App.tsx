import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/AuthContext'
import Layout from './components/Layout'
import { LoadingBlock } from './components/ui'
import ApprovalScreen from './pages/ApprovalScreen'
import BrandProfilePage from './pages/BrandProfile'
import Dashboard from './pages/Dashboard'
import HistoryPage from './pages/HistoryPage'
import Landing from './pages/Landing'
import NewSubmission from './pages/NewSubmission'
import Queue from './pages/Queue'
import ReviewScreen from './pages/ReviewScreen'

function Protected({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth()
  if (loading) return <LoadingBlock label="Restoring your session…" />
  if (!me) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/new" element={<NewSubmission />} />
        <Route path="/review/:id" element={<ReviewScreen />} />
        <Route path="/approval/:id" element={<ApprovalScreen />} />
        <Route path="/queue" element={<Queue />} />
        <Route path="/brand" element={<BrandProfilePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/history/:id" element={<HistoryPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
