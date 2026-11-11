import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { GitBranch, Zap } from 'lucide-react'
import { supabase } from './client'
import { useAuth } from './AuthProvider'
import './auth.css'

export function AuthFrame({ children }: { children: ReactNode }) {
  return <main className="auth-page"><section className="auth-card">
    <div className="auth-brand"><Zap aria-hidden="true" /> CodeLens AI</div>{children}
  </section></main>
}

export function Login() {
  const { session, loading } = useAuth()
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  if (loading) return <AuthFrame><p role="status">Loading your account�</p></AuthFrame>
  if (session) return <Navigate to="/" replace />
  const callback = `${window.location.origin}/auth/callback`
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase || busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (mode === 'reset') {
        const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${callback}?next=reset` })
        if (error) throw error
        setNotice('If an account exists for this email, you will receive a password reset link. Open it in this browser.')
      } else if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: callback } })
        if (error) throw error
        setNotice('Check your email for a confirmation link. Open it in this browser to finish creating your account.')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.') }
    finally { setBusy(false) }
  }
  async function oauth(provider: 'google' | 'github') {
    if (!supabase || busy) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.signInWithOAuth({ provider, options: { redirectTo: callback } })
      if (error) throw error
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign in.'); setBusy(false) }
  }
  function changeMode(next: typeof mode) { setMode(next); setPassword(''); setError(''); setNotice('') }
  return <AuthFrame>
    <h1>{mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : 'Welcome back'}</h1>
    <p className="auth-subtitle">Your repositories, insights, and conversations in one private workspace.</p>
    {!supabase && <p role="alert">Sign-in is temporarily unavailable. Please try again later.</p>}
    <form onSubmit={submit}>
      <fieldset disabled={busy || !supabase}>
        {mode !== 'reset' && <><div className="auth-social">
          <button type="button" onClick={() => void oauth('google')}>Continue with Google</button>
          <button type="button" onClick={() => void oauth('github')}><GitBranch size={17} aria-hidden="true" /> Continue with GitHub</button>
        </div><div className="auth-divider">or use your email</div></>}
        <label htmlFor="email">Email address</label>
        <input id="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} />
        {mode !== 'reset' && <><label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 12 : 1} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} />
          {mode === 'signup' && <small>Use at least 12 characters.</small>}
        </>}
        <button className="auth-primary" type="submit">{busy ? 'Please wait�' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
      </fieldset>
    </form>
    {error && <p className="auth-error" role="alert">{error}</p>}
    {notice && <p className="auth-notice" role="status">{notice}</p>}
    <div className="auth-links">
      <button disabled={busy} onClick={() => changeMode(mode === 'login' ? 'signup' : 'login')}>{mode === 'login' ? 'New here? Create an account' : 'Back to sign in'}</button>
      {mode === 'login' && <button disabled={busy} onClick={() => changeMode('reset')}>Forgot password?</button>}
    </div>
  </AuthFrame>
}

export function AuthCallback() {
  const navigate = useNavigate()
  const [error, setError] = useState(supabase ? '' : 'Sign-in is temporarily unavailable.')
  useEffect(() => {
    let active = true
    const target = new URLSearchParams(window.location.search).get('next') === 'reset' ? '/reset-password' : '/'
    if (!supabase) return
    // The SDK exchanges the PKCE code exactly once during initialization.
    void supabase.auth.getSession().then(({ data, error }) => {
      if (!active) return
      if (error || !data.session) setError('This sign-in link is invalid or expired. Request a new link and open it in the same browser.')
      else navigate(target, { replace: true })
    }).catch(() => { if (active) setError('Unable to complete sign-in. Please try again.') })
    return () => { active = false }
  }, [navigate])
  return <AuthFrame><h1>Completing sign-in</h1>{error ? <><p role="alert">{error}</p><Link to="/login">Return to sign in</Link></> : <p role="status">Please wait�</p>}</AuthFrame>
}

export function ResetPassword() {
  const { session, loading } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase || busy) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.updateUser({ password })
      if (error) throw error
      navigate('/', { replace: true })
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to update password.') }
    finally { setBusy(false) }
  }
  if (loading) return <AuthFrame><p role="status">Loading�</p></AuthFrame>
  if (!session) return <Navigate to="/login" replace />
  return <AuthFrame><h1>Choose a new password</h1><form onSubmit={submit}>
    <label htmlFor="new-password">New password</label>
    <input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} />
    <small>Use at least 12 characters.</small>
    <button className="auth-primary" disabled={busy}>{busy ? 'Saving�' : 'Save password'}</button>
  </form>{error && <p role="alert">{error}</p>}</AuthFrame>
}
