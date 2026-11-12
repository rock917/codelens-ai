import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { supabase } from '../auth/client'
import { getDeletionStatus, deleteAccount } from '../services/api'
import TopBar from '../components/layout/TopBar'

type DeletionStatus = { enabled: boolean; pending: boolean; recent_sign_in: boolean }

export default function Settings() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [status, setStatus] = useState<DeletionStatus | null>(null)
  const [email, setEmail] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void getDeletionStatus().then(({ data }) => { if (active) setStatus(data) })
      .catch(() => { if (active) setError('Unable to check account settings. Refresh to try again.') })
    return () => { active = false }
  }, [session?.user.id])
  useEffect(() => {
    if (!status?.pending) return
    let active = true
    const timer = window.setInterval(() => {
      void getDeletionStatus().catch(async err => {
        // An expired session can also return 401: do not claim deletion completed.
        if (active && err.response?.status === 401) {
          await supabase?.auth.signOut({ scope: 'local' })
          if (active) navigate('/login?deletion=pending', { replace: true })
        }
      })
    }, 5000)
    return () => { active = false; window.clearInterval(timer) }
  }, [status?.pending, navigate])
  async function signInAgain() {
    if (!supabase) return
    setBusy(true); setError('')
    try {
      const result = await supabase.auth.signOut({ scope: 'local' })
      if (result.error) throw result.error
      navigate('/login', { replace: true })
    } catch { setError('Unable to sign out. Please try again.'); setBusy(false) }
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !status?.enabled || !status.recent_sign_in || confirmation !== 'DELETE' || email.trim().toLowerCase() !== session?.user.email?.toLowerCase()) return
    setBusy(true); setError('')
    try {
      const { data } = await deleteAccount(email.trim(), confirmation)
      if (data.status === 'deleted') {
        await supabase?.auth.signOut({ scope: 'local' })
        navigate('/login?deleted=1', { replace: true })
      } else {
        setStatus({ ...status, pending: true }); setExpanded(false)
      }
    } catch (err: unknown) {
      const failure = err as { response?: { status?: number; data?: { detail?: unknown } } }
      const detail = failure.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'We could not confirm completion. Refresh Settings to check the deletion status before trying again.')
      if (failure.response?.status === 403) setStatus({ ...status, recent_sign_in: false })
    } finally { setBusy(false) }
  }
  return <>
    <TopBar title="Settings" subtitle="Manage your CodeLens account" />
    <div style={{ padding: 24, maxWidth: 760, width: '100%' }}>
      <section className="card" style={{ padding: 24 }} aria-labelledby="account-heading">
        <h2 id="account-heading">Your account</h2>
        <p style={{ overflowWrap: 'anywhere', marginTop: 12 }}>{session?.user.email}</p>
      </section>
      <section className="card" style={{ padding: 24, marginTop: 24, borderColor: 'var(--danger, #b94d64)' }} aria-labelledby="delete-heading">
        <h2 id="delete-heading">Delete account</h2>
        <p style={{ marginTop: 16, lineHeight: 1.7 }}>Permanently remove your CodeLens login, saved repositories, source files, vector indexes, chats, analysis results and usage history. This cannot be undone.</p>
        <p style={{ marginTop: 12, lineHeight: 1.7 }}>Your GitHub repositories, Google and GitHub accounts, and other users’ data are unaffected. Existing backups can retain data until rotated or manually removed. If you register again, you start with a fresh analysis allowance.</p>
        {!status && !error && <p role="status">Checking account settings…</p>}
        {status?.pending ? <p role="status" style={{ marginTop: 16 }}>Deletion is in progress. Your workspace is locked while cleanup finishes. The server will retry automatically if needed; you can close this page. Contact support if it remains pending.</p> : status && <>
          {!status.enabled ? <p style={{ marginTop: 16 }}>Self-service deletion is not available yet. Contact <a href="mailto:thejacksparrow805@gmail.com">thejacksparrow805@gmail.com</a> for help.</p> : !status.recent_sign_in ? <div style={{ marginTop: 16 }}>
            <p>Sign in again, then return to Settings within 10 minutes to confirm deletion.</p>
            <button className="btn btn-secondary" style={{ marginTop: 16 }} disabled={busy} onClick={() => void signInAgain()}>Sign out and sign in again</button>
          </div> : !expanded ? <button className="btn btn-secondary" style={{ marginTop: 20 }} onClick={() => setExpanded(true)}>Delete my account…</button> : <form onSubmit={submit} style={{ marginTop: 20 }}>
            <label htmlFor="deletion-email">Confirm your account email</label>
            <input id="deletion-email" type="email" autoComplete="email" required value={email} disabled={busy} onChange={event => setEmail(event.target.value)} style={{ display: 'block', width: '100%', margin: '8px 0 16px' }} />
            <label htmlFor="deletion-confirmation">Type DELETE to confirm</label>
            <input id="deletion-confirmation" autoComplete="off" required value={confirmation} disabled={busy} onChange={event => setConfirmation(event.target.value)} style={{ display: 'block', width: '100%', margin: '8px 0 16px' }} />
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => { setExpanded(false); setEmail(''); setConfirmation(''); setError('') }}>Keep my account</button>
              <button type="submit" className="btn btn-secondary" style={{ color: 'var(--danger, #ff869b)' }} disabled={busy || confirmation !== 'DELETE' || email.trim().toLowerCase() !== session?.user.email?.toLowerCase()}>{busy ? 'Deleting…' : 'Permanently delete my account'}</button>
            </div>
          </form>}
        </>}
        {error && <p role="alert" style={{ marginTop: 16 }}>{error}</p>}
      </section>
    </div>
  </>
}
