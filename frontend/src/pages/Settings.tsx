import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { supabase } from '../auth/client'
import { getDeletionStatus, deleteAccount } from '../services/api'
import TopBar from '../components/layout/TopBar'
import Appearance from '../theme/Appearance'
import './settings.css'
import { AccountDialog, BusyLabel, useToast } from '../components/ui/AccountFeedback'

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
  const working = useRef(false)
  const deletionTrigger = useRef<HTMLButtonElement>(null)
  const notify = useToast()
  const emailMatches = Boolean(email.trim()) && email.trim().toLowerCase() === session?.user.email?.toLowerCase()
  const confirmationHint = !emailMatches
    ? 'Enter your account email in the field above to enable deletion.'
    : confirmation !== 'DELETE'
      ? 'Type DELETE exactly as shown to enable deletion.'
      : 'Both confirmations match. Deleting your account is permanent.'
  useEffect(() => {
    let active = true
    void getDeletionStatus().then(({ data }) => { if (active) setStatus(data) })
      .catch(() => { if (active) setError('Unable to check account settings. Refresh to try again.') })
    return () => { active = false }
  }, [session?.user.id])
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
    if (working.current || busy || !status?.enabled || !status.recent_sign_in || confirmation !== 'DELETE' || !emailMatches) return
    working.current = true
    setBusy(true); setError('')
    try {
      const { data } = await deleteAccount(email.trim(), confirmation)
      if (data.status === 'deleted') {
        notify('Your CodeLens_AI account has been permanently deleted.', 'success')
        try { await supabase?.auth.signOut({ scope: 'local' }) } catch { /* Server already confirmed deletion. */ }
        navigate('/login?deleted=1', { replace: true })
      } else if (data.status === 'pending') {
        setStatus({ ...status, pending: true }); setExpanded(false)
        notify('Deletion is still in progress. Cleanup will continue on the server.', 'info')
      } else {
        throw new Error('Unexpected deletion response')
      }
    } catch (err: unknown) {
      const failure = err as { response?: { status?: number; data?: { detail?: unknown } } }
      const detail = failure.response?.data?.detail
      const message = typeof detail === 'string' ? detail : 'We could not confirm completion. Refresh Settings to check the deletion status before trying again.'
      setError(message); notify(message, 'error')
      if (failure.response?.status === 403) { setStatus({ ...status, recent_sign_in: false }); setExpanded(false) }
    } finally { working.current = false; setBusy(false) }
  }
  return <>
    <TopBar title="Settings" subtitle="Manage your CodeLens account" />
    <div className="account-settings" style={{ padding: 24, maxWidth: 760, width: '100%' }}>
      <section id="account" className="card" style={{ padding: 24 }} aria-labelledby="account-heading">
        <h2 id="account-heading">Your account</h2>
        <p style={{ overflowWrap: 'anywhere', marginTop: 12 }}>{session?.user.email}</p>
      </section>
      <Appearance />
      <section className="card" style={{ padding: 24, marginTop: 24, borderColor: 'var(--danger)' }} aria-labelledby="delete-heading">
        <h2 id="delete-heading">Danger Zone</h2>
        <p style={{ marginTop: 16, lineHeight: 1.7 }}>Permanently remove your CodeLens login, saved repositories, source files, vector indexes, chats, analysis results and usage history. This cannot be undone.</p>
        <p style={{ marginTop: 12, lineHeight: 1.7 }}>Your GitHub repositories, Google and GitHub accounts, and other users’ data are unaffected. Existing backups can retain data until rotated or manually removed. If you register again, you start with a fresh analysis allowance.</p>
        {!status && !error && <p role="status">Checking account settings…</p>}
        {status?.pending ? <p role="status" style={{ marginTop: 16 }}>Deletion is in progress. Your workspace is locked while cleanup finishes. The server will retry automatically if needed; you can close this page. Contact support if it remains pending.</p> : status && <>
          {!status.enabled ? <p style={{ marginTop: 16 }}>Self-service deletion is not available yet. Contact <a href="mailto:thejacksparrow805@gmail.com">thejacksparrow805@gmail.com</a> for help.</p> : !status.recent_sign_in ? <div style={{ marginTop: 16 }}>
            <p>Sign in again, then return to Settings within 10 minutes to confirm deletion.</p>
            <button className="btn btn-secondary" style={{ marginTop: 16 }} disabled={busy} onClick={() => void signInAgain()}>Sign out and sign in again</button>
          </div> : <button ref={deletionTrigger} className="account-button danger" style={{ marginTop: 20 }} onClick={() => { setError(''); setExpanded(true) }}>Delete Account</button>}
        </>}
        {error && !expanded && <p role="alert" style={{ marginTop: 16 }}>{error}</p>}
      </section>
      <AccountDialog open={expanded} onOpenChange={value => { setExpanded(value); if (!value) { setEmail(''); setConfirmation(''); setError('') } }}
        busy={busy} destructive returnFocus={() => deletionTrigger.current?.focus()} title="Permanently delete your account?"
        description="This action cannot be undone. Your CodeLens_AI account and associated repositories, uploaded files, vector indexes, chats, analysis results, and usage history will be permanently deleted.">
        <p>Your Google/GitHub accounts and original repositories are unaffected. Existing backup copies may remain until rotated or manually removed.</p>
        <form onSubmit={submit}>
            <label htmlFor="deletion-email">Confirm your account email</label>
            <input id="deletion-email" className="deletion-input" type="email" placeholder="Enter your account email" autoComplete="email" aria-describedby="deletion-hint" required value={email} disabled={busy} onChange={event => setEmail(event.target.value)} />
            <label htmlFor="deletion-confirmation">Type DELETE to confirm</label>
            <input id="deletion-confirmation" className="deletion-input" placeholder="DELETE" autoComplete="off" aria-describedby="deletion-hint" required value={confirmation} disabled={busy} onChange={event => setConfirmation(event.target.value)} />
            <p id="deletion-hint" aria-live="polite" style={{ marginBottom: 16 }}>{confirmationHint}</p>
            {error && <p role="alert" className="account-error">{error}</p>}
            <button type="submit" className="account-button danger" aria-describedby="deletion-hint" disabled={busy || confirmation !== 'DELETE' || !emailMatches}>{busy ? <BusyLabel>Deleting account...</BusyLabel> : 'Permanently Delete Account'}</button>
        </form>
      </AccountDialog>
    </div>
  </>
}
