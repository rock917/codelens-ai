import { AuthProvider, useAuth } from './auth/AuthProvider'
import { Login, AuthCallback, ResetPassword, AuthFrame } from './auth/AuthPages'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Dashboard from './pages/Dashboard'
import Repositories from './pages/Repositories'
import Chat from './pages/Chat'
import Analysis from './pages/Analysis'
import TestGen from './pages/TestGen'
import DocsGen from './pages/DocsGen'
import Explorer from './pages/Explorer'
import SearchPage from './pages/Search'
import Settings from './pages/Settings'

function PrivateWorkspace() {
  const { session, loading } = useAuth()
  if (loading) return <AuthFrame><p role="status">Loading your workspace…</p></AuthFrame>
  if (!session) return <Navigate to="/login" replace />
  return (
    <div key={session.user.id}>
      <div style={{
        display: 'flex', height: '100vh',
        overflow: 'hidden', background: 'var(--bg-base)',
      }}>
        <Sidebar />
        <main style={{
          flex: 1, overflow: 'auto',
          display: 'flex', flexDirection: 'column',
        }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/repositories" element={<Repositories />} />
            <Route path="/explorer" element={<Explorer />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/tests" element={<TestGen />} />
            <Route path="/docs" element={<DocsGen />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
export default function App() {
  return <BrowserRouter><AuthProvider><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/auth/callback" element={<AuthCallback />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/*" element={<PrivateWorkspace />} />
  </Routes></AuthProvider></BrowserRouter>
}
