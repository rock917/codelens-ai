import { Sparkles } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import './dashboard-welcome.css'

export default function DashboardWelcome() {
  const { session } = useAuth()
  const metadata = session?.user.user_metadata
  const displayName = [metadata?.full_name, metadata?.name, metadata?.preferred_username, metadata?.user_name]
    .find((value): value is string => typeof value === 'string' && Boolean(value.trim()) && !value.includes('@'))
    ?.trim().replace(/\s+/g, ' ')

  return <section className="dashboard-welcome" aria-labelledby="dashboard-welcome-heading">
    <div>
      <p className="dashboard-welcome-label">YOUR WORKSPACE</p>
      <h1 id="dashboard-welcome-heading">Welcome back{displayName ? <>, <span><bdi>{displayName}</bdi></span></> : ''}.</h1>
      <p className="dashboard-welcome-description">Pick up where you left off. Your code, insights, and conversations are right here.</p>
    </div>
    <span className="dashboard-welcome-icon" aria-hidden="true"><Sparkles size={26} /></span>
  </section>
}
