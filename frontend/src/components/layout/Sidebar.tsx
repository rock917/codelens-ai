import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, GitBranch, MessageSquare,
  Shield, FlaskConical, FileText,
  Zap, FolderTree, Search
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/repositories', icon: GitBranch, label: 'Repositories' },
  { to: '/explorer', icon: FolderTree, label: 'Explorer' },
  { to: '/search', icon: Search, label: 'Search' },
  { to: '/chat', icon: MessageSquare, label: 'AI Chat' },
  { to: '/analysis', icon: Shield, label: 'Analysis' },
  { to: '/tests', icon: FlaskConical, label: 'Test Gen' },
  { to: '/docs', icon: FileText, label: 'Docs Gen' },
]

export default function Sidebar() {
  return (
    <aside style={{
      width: '220px', minWidth: '220px',
      height: '100vh', background: 'var(--bg-surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      padding: '16px 12px', position: 'sticky', top: 0,
    }}>
      {/* Logo */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '10px',
        padding: '8px 12px', marginBottom: '24px',
      }}>
        <div style={{
          width: '28px', height: '28px',
          background: 'linear-gradient(135deg, #6366f1, #a855f7)',
          borderRadius: '8px', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <Zap size={14} color="white" />
        </div>
        <div>
          <div style={{
            fontSize: '13px', fontWeight: '700',
            background: 'linear-gradient(135deg, #6366f1, #a855f7)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            CodeLens
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '-2px' }}>
            AI Platform
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to} to={to} end={to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div style={{
        padding: '12px', borderTop: '1px solid var(--border)', marginTop: '16px',
      }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>
          v1.0.0 · Backend <span style={{ color: 'var(--success)' }}>●</span>
        </div>
      </div>
    </aside>
  )
}