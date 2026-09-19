import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Dashboard from './pages/Dashboard'
import Repositories from './pages/Repositories'
import Chat from './pages/Chat'
import Analysis from './pages/Analysis'
import TestGen from './pages/TestGen'
import DocsGen from './pages/DocsGen'
import Explorer from './pages/Explorer'
import SearchPage from './pages/Search'

export default function App() {
  return (
    <BrowserRouter>
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}