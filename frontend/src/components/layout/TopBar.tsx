import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'

interface TopBarProps {
  title: string
  subtitle?: string
}

export default function TopBar({ title, subtitle }: TopBarProps) {
  const navigate = useNavigate()

  return (
    <div style={{
      height: '56px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      background: 'var(--bg-surface)',
      position: 'sticky',
      top: 0,
      zIndex: 10,
    }}>
      <div>
        <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text)' }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {subtitle}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          className="btn-ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px' }}
          onClick={() => navigate('/repositories')}
        >
          <Plus size={13} />
          New Repo
        </button>
      </div>
    </div>
  )
}