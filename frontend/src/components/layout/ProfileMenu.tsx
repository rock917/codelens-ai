import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ChevronsUpDown, UserRound, Settings, LockKeyhole, Moon, LogOut } from 'lucide-react'
import { useAuth } from '../../auth/AuthProvider'
import { supabase } from '../../auth/client'
import { AccountDialog, BusyLabel, useToast } from '../ui/AccountFeedback'
import { useTheme } from '../../theme/ThemeProvider'
import { themes } from '../../theme/preferences'

export default function ProfileMenu() {
  const { session } = useAuth()
  const { theme } = useTheme()
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const working = useRef(false)
  const box = useRef<HTMLDivElement>(null)
  const toggle = useRef<HTMLButtonElement>(null)
  const first = useRef<HTMLAnchorElement>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const notify = useToast()
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!box.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); toggle.current?.focus() } }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [open])
  async function signOut() {
    if (working.current || !supabase) return
    working.current = true; setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.signOut({ scope: 'local' })
      if (error) throw error
      notify('You have signed out of CodeLens_AI.', 'success')
      navigate('/login', { replace: true })
    } catch {
      const message = 'Unable to sign out. Please try again.'
      setError(message); notify(message, 'error')
    } finally { working.current = false; setBusy(false) }
  }
  return <div className="profile-box" ref={box}>
    <button ref={toggle} className="profile-toggle" aria-label="Open profile menu" aria-expanded={open} aria-controls="profile-actions" onClick={() => setOpen(value => !value)} onKeyDown={event => {
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); requestAnimationFrame(() => first.current?.focus()) }
    }}>
      <span className="profile-avatar" aria-hidden="true">{(session?.user.email?.[0] || 'U').toUpperCase()}</span>
      <span className="profile-identity"><strong title={session?.user.email}>{session?.user.email}</strong><small>Personal account</small></span><ChevronsUpDown size={14} />
    </button>
    {open && <nav id="profile-actions" className="profile-actions" aria-label="Profile actions">
      <Link ref={first} to="/settings#account" onClick={() => setOpen(false)}><UserRound size={16} />My Account</Link>
      <Link to="/settings" aria-current={location.pathname === '/settings' ? 'page' : undefined} onClick={() => setOpen(false)}><Settings size={16} />Settings</Link>
      <Link to="/reset-password" onClick={() => setOpen(false)}><LockKeyhole size={16} />Change Password</Link>
      <Link to="/settings#appearance" onClick={() => setOpen(false)}><Moon size={16} />Appearance<span className="profile-theme">{themes.find(option => option.id === theme)?.short}</span></Link>
      <button className="profile-signout" onClick={() => { setOpen(false); setError(''); setConfirm(true) }}><LogOut size={16} />Sign Out</button>
    </nav>}
    <AccountDialog open={confirm} onOpenChange={setConfirm} busy={busy} returnFocus={() => toggle.current?.focus()} title="Sign out of CodeLens_AI?"
      description="Are you sure you want to sign out of your account? You will need to sign in again to access your repositories and workspace.">
      {error && <p role="alert" className="account-error">{error}</p>}
      <button className="account-button primary" disabled={busy || !supabase} onClick={() => void signOut()}>{busy ? <BusyLabel>Signing out...</BusyLabel> : 'Sign Out'}</button>
    </AccountDialog>
  </div>
}
