import { useEffect, useState } from 'react'
import { getAnalysisUsage } from '../services/api'

export default function UsageBanner({ refreshKey = '' }: { refreshKey?: string }) {
  const [usage, setUsage] = useState<{ used: number; reserved: number; remaining: number; limit: number } | null>(null)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true
    getAnalysisUsage().then(({ data }) => { if (active) { setUsage(data); setError(false) } })
      .catch(() => { if (active) setError(true) })
    return () => { active = false }
  }, [refreshKey, retry])
  return <div className="card" role="status" style={{ padding: '14px 18px', marginBottom: 18, fontSize: 12, lineHeight: 1.7 }}>
    {error ? <>Usage unavailable. <button className="btn-ghost" onClick={() => setRetry(n => n + 1)}>Retry</button></> : usage ? <>
      <strong>{usage.used} of {usage.limit} lifetime analyses used</strong>
      <span style={{ color: 'var(--text-muted)' }}> · {usage.reserved} in progress · {usage.remaining} available</span>
      <div style={{ color: 'var(--text-muted)' }}>Each successful repository import uses one credit. Unchanged saved results and health rescans are free. Failed imports release their slot; deleting a repository does not restore credits.</div>
    </> : 'Loading analysis allowance…'}
  </div>
}
